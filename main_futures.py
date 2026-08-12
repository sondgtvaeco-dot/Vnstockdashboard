"""
Collector cho phái sinh VN30F - chạy song song với main.py (collector cổ
phiếu), cùng lịch, cùng DB, nhưng tách file riêng vì logic chấm điểm khác
(basis thay cho P/E, không cần fetch báo cáo tài chính).

Cách chạy:
    python main_futures.py
    python main_futures.py --demo    # dữ liệu giả lập, không cần internet/DB
"""

import argparse
import os
import sys

import pandas as pd

import config as cfg
import db
import indicators
import futures_analysis
import scorer
from data_fetcher import VNDataFetcher, generate_synthetic_ohlcv


def analyze_futures_demo(symbol: str, weights: dict, thresholds: dict) -> dict:
    fut_df = generate_synthetic_ohlcv(n_days=300, start_price=1300, seed=hash(symbol) % 1000)
    idx_df = generate_synthetic_ohlcv(n_days=300, start_price=1290, seed=(hash(symbol) + 1) % 1000)

    df_ind = indicators.compute_all_indicators(fut_df, cfg)
    last_row = df_ind.iloc[-1]
    tech_score = indicators.technical_score(last_row, cfg)

    basis_summary = futures_analysis.build_basis_summary(symbol, fut_df, idx_df)

    result = scorer.score_symbol(
        symbol, tech_score, basis_summary["basis_score"],
        {"technical": weights["technical"], "valuation": weights["basis"]}, thresholds,
    )
    result["last_close"] = round(float(last_row["close"]), 2)
    result["rsi"] = round(float(last_row["rsi"]), 1) if pd.notna(last_row["rsi"]) else None
    result["basis"] = basis_summary["basis"]
    result["basis_pct"] = basis_summary["basis_pct"]
    result["note"] = "DEMO: dữ liệu giả lập, chỉ dùng kiểm thử logic."
    result.update(indicators.extract_indicator_detail(last_row, cfg))
    return result


def analyze_futures_live(fetcher: VNDataFetcher, symbol: str, weights: dict, thresholds: dict) -> dict:
    fut_df = fetcher.get_futures_ohlcv(
        symbol, lookback_days=cfg.FUTURES_INTRADAY_LOOKBACK_DAYS, interval=cfg.FUTURES_INTERVAL,
    )
    idx_df = fetcher.get_index_ohlcv(
        cfg.FUTURES_UNDERLYING_INDEX, lookback_days=cfg.FUTURES_INTRADAY_LOOKBACK_DAYS,
        interval=cfg.FUTURES_INTERVAL,
    )

    df_ind = indicators.compute_all_indicators(fut_df, cfg)
    last_row = df_ind.iloc[-1].copy()

    # Tương tự cổ phiếu: SMA200 tính từ nến ngày riêng, không dùng nến phút.
    # LƯU Ý RIÊNG CHO PHÁI SINH: một hợp đồng như VN30F1M thường chỉ tồn tại
    # 1-3 tháng trước khi đáo hạn, nên hiếm khi có đủ 200 phiên lịch sử - kết
    # quả None ở đây là BÌNH THƯỜNG với phái sinh, không phải lỗi.
    if cfg.FUTURES_INTERVAL != "1D":
        try:
            daily_fut_df = fetcher.get_futures_ohlcv(symbol, lookback_days=cfg.LOOKBACK_DAYS, interval="1D")
            last_row["sma_200"] = indicators.daily_trend_sma(daily_fut_df, period=200)
        except Exception:  # noqa: BLE001
            last_row["sma_200"] = None
    tech_score = indicators.technical_score(last_row, cfg)

    basis_summary = futures_analysis.build_basis_summary(symbol, fut_df, idx_df)

    result = scorer.score_symbol(
        symbol, tech_score, basis_summary["basis_score"],
        {"technical": weights["technical"], "valuation": weights["basis"]}, thresholds,
    )
    result["last_close"] = round(float(last_row["close"]), 2)
    result["rsi"] = round(float(last_row["rsi"]), 1) if pd.notna(last_row["rsi"]) else None
    result["basis"] = basis_summary["basis"]
    result["basis_pct"] = basis_summary["basis_pct"]
    result["note"] = basis_summary["note"]
    result.update(indicators.extract_indicator_detail(last_row, cfg))
    return result


def main():
    parser = argparse.ArgumentParser(description="Collector phái sinh VN30F")
    parser.add_argument("--demo", action="store_true")
    args = parser.parse_args()

    if args.demo:
        watchlist = cfg.FUTURES_WATCHLIST
        weights = {"technical": cfg.FUTURES_TECHNICAL_WEIGHT, "basis": cfg.FUTURES_BASIS_WEIGHT}
        thresholds = {"cheap": cfg.FUTURES_ZONE_CHEAP_THRESHOLD, "expensive": cfg.FUTURES_ZONE_EXPENSIVE_THRESHOLD}
        print("=== CHẾ ĐỘ DEMO PHÁI SINH (dữ liệu giả lập) ===\n")
        rows = [analyze_futures_demo(s, weights, thresholds) for s in watchlist]
    else:
        db.init_db()
        watchlist = db.get_futures_watchlist()
        weights = db.get_futures_weights()
        thresholds = db.get_futures_thresholds()

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
                rows.append(analyze_futures_live(fetcher, symbol, weights, thresholds))
            except Exception as e:  # noqa: BLE001
                print(f"  Lỗi khi xử lý {symbol}: {e}", file=sys.stderr)

    report = scorer.build_report(rows)
    if report.empty:
        print("Không có dữ liệu để báo cáo.")
        return

    report = report.rename(columns={"valuation_score": "basis_score"})
    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 120)
    print("\n=== KẾT QUẢ QUÉT PHÁI SINH ===")
    print(report.to_string(index=False))

    if not args.demo:
        db.insert_futures_scores(report.to_dict(orient="records"))
        print("\nĐã ghi lượt quét mới vào Postgres (futures_scores_history).")

    print("\nLưu ý: basis-score dựa trên giả định hồi quy về trung bình, không phải quy luật chắc chắn.")


if __name__ == "__main__":
    main()
