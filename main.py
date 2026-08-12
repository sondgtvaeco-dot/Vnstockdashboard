"""
Collector: chạy định kỳ (qua GitHub Actions) để:
  1. Đọc watchlist/ngưỡng/trọng số hiện tại từ DB (có thể đã bị người dùng chỉnh
     qua trang "Cấu hình" trên web) - nếu DB chưa có gì thì dùng mặc định trong
     config.py.
  2. Lấy dữ liệu giá + báo cáo tài chính từ vnstock cho từng mã.
  3. Tính chỉ báo kỹ thuật + điểm định giá + điểm tổng hợp.
  4. Ghi THÊM (append, không ghi đè) một lượt kết quả mới vào bảng scores_history
     trong Postgres - đây là dữ liệu mà Streamlit dashboard sẽ đọc để vẽ biểu đồ
     lịch sử và bảng trạng thái.

Cách chạy:
    python main.py                  # dùng dữ liệu thật từ vnstock (cần internet + DB_URL)
    python main.py --demo           # dùng dữ liệu giả lập, không cần internet/DB
"""

import argparse
import os
import sys

import pandas as pd

import config as cfg
import db
import indicators
import valuation
import scorer
from data_fetcher import VNDataFetcher, generate_synthetic_ohlcv


def analyze_symbol_demo(symbol: str, weights: dict, thresholds: dict) -> dict:
    """Chạy pipeline kỹ thuật với dữ liệu giả lập (không cần internet/DB)."""
    df = generate_synthetic_ohlcv(n_days=300, seed=hash(symbol) % 1000)
    df_ind = indicators.compute_all_indicators(df, cfg)
    last_row = df_ind.iloc[-1]
    tech_score = indicators.technical_score(last_row, cfg)

    val_score = 50.0  # không có dữ liệu định giá thật ở chế độ demo

    result = scorer.score_symbol(symbol, tech_score, val_score, weights, thresholds)
    result["last_close"] = round(float(last_row["close"]), 2)
    result["rsi"] = round(float(last_row["rsi"]), 1) if pd.notna(last_row["rsi"]) else None
    result["current_pe"] = None
    result["current_pb"] = None
    result["note"] = "DEMO: dữ liệu giả lập, chỉ dùng kiểm thử logic."
    result.update(indicators.extract_indicator_detail(last_row, cfg))
    return result


def analyze_symbol_live(fetcher: VNDataFetcher, symbol: str, weights: dict, thresholds: dict) -> dict:
    """Chạy pipeline với dữ liệu thật từ vnstock."""
    df = fetcher.get_equity_ohlcv(
        symbol, lookback_days=cfg.EQUITY_INTRADAY_LOOKBACK_DAYS, interval=cfg.EQUITY_INTERVAL,
    )
    df_ind = indicators.compute_all_indicators(df, cfg)
    last_row = df_ind.iloc[-1].copy()

    # SMA200 "dài hạn" không có ý nghĩa nếu tính trên khung phút (200 kỳ x 15 phút
    # chỉ ~2 ngày) - lấy riêng từ nến NGÀY rồi ghi đè vào trước khi chấm điểm.
    if cfg.EQUITY_INTERVAL != "1D":
        try:
            daily_df = fetcher.get_equity_ohlcv(symbol, lookback_days=cfg.LOOKBACK_DAYS, interval="1D")
            last_row["sma_200"] = indicators.daily_trend_sma(daily_df, period=200)
        except Exception:  # noqa: BLE001
            last_row["sma_200"] = None
    tech_score = indicators.technical_score(last_row, cfg)

    try:
        ratio_df = fetcher.get_ratios(symbol, period=cfg.RATIO_PERIOD)
        val_summary = valuation.build_valuation_summary(symbol, ratio_df)
        val_score = val_summary["valuation_score"]
        current_pe = val_summary["current_pe"]
        current_pb = val_summary["current_pb"]
        note = val_summary["note"]
    except Exception as e:  # noqa: BLE001
        val_score = 50.0
        current_pe = current_pb = None
        note = f"Không lấy được dữ liệu định giá: {e}"

    result = scorer.score_symbol(symbol, tech_score, val_score, weights, thresholds)
    result["last_close"] = round(float(last_row["close"]), 2)
    result["rsi"] = round(float(last_row["rsi"]), 1) if pd.notna(last_row["rsi"]) else None
    result["current_pe"] = current_pe
    result["current_pb"] = current_pb
    result["note"] = note
    result.update(indicators.extract_indicator_detail(last_row, cfg))
    return result


def main():
    parser = argparse.ArgumentParser(description="Collector: quét watchlist, ghi kết quả vào DB")
    parser.add_argument("--demo", action="store_true",
                         help="Chạy với dữ liệu giả lập, không cần internet/vnstock/DB")
    parser.add_argument("--output", default=None,
                         help="Nếu set, cũng xuất báo cáo ra file CSV (tuỳ chọn, để debug local)")
    args = parser.parse_args()

    if args.demo:
        watchlist = cfg.WATCHLIST
        weights = {"technical": cfg.TECHNICAL_WEIGHT, "valuation": cfg.VALUATION_WEIGHT}
        thresholds = {"cheap": cfg.ZONE_CHEAP_THRESHOLD, "expensive": cfg.ZONE_EXPENSIVE_THRESHOLD}
        print("=== CHẾ ĐỘ DEMO (dữ liệu giả lập, chỉ kiểm thử logic) ===\n")
        rows = [analyze_symbol_demo(s, weights, thresholds) for s in watchlist]
    else:
        db.init_db()
        watchlist = db.get_watchlist()
        weights = db.get_weights()
        thresholds = db.get_thresholds()

        api_key = cfg.VNSTOCK_API_KEY or os.environ.get("VNSTOCK_API_KEY")
        try:
            fetcher = VNDataFetcher(api_key=api_key)
        except ImportError:
            print("Chưa cài vnstock. Chạy: pip install -r requirements.txt", file=sys.stderr)
            sys.exit(1)

        rows = []
        for symbol in watchlist:
            print(f"Đang xử lý {symbol}...")
            try:
                rows.append(analyze_symbol_live(fetcher, symbol, weights, thresholds))
            except Exception as e:  # noqa: BLE001
                print(f"  Lỗi khi xử lý {symbol}: {e}", file=sys.stderr)

    report = scorer.build_report(rows)
    if report.empty:
        print("Không có dữ liệu để báo cáo.")
        return

    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 120)
    print("\n=== KẾT QUẢ LƯỢT QUÉT ===")
    print(report.to_string(index=False))

    if args.output:
        report.to_csv(args.output, index=False, encoding="utf-8-sig")
        print(f"\nĐã lưu báo cáo CSV (tuỳ chọn): {args.output}")

    if not args.demo:
        db.insert_scores(report.to_dict(orient="records"))
        print("\nĐã ghi lượt quét mới vào Postgres (scores_history).")

    print("\nLưu ý: đây là công cụ hỗ trợ tham khảo, không phải khuyến nghị đầu tư.")


if __name__ == "__main__":
    main()
