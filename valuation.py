"""
Chấm điểm định giá cơ bản: so sánh P/E, P/B hiện tại với phân vị lịch sử của
chính mã đó, dựa trên dữ liệu trả về từ Fundamental().equity(symbol).ratios().

Cấu trúc dữ liệu thực tế từ vnstock (bản Unified UI) là dạng "item theo hàng,
năm theo cột": cột 'item' chứa tên chỉ tiêu (vd P/E, P/B, ROE...), các cột còn
lại là năm ('2022','2023','2024','2025'...) chứa giá trị tương ứng.
"""

import unicodedata

import numpy as np
import pandas as pd

# Các biến thể tên gọi có thể gặp cho P/E và P/B (đã chuẩn hoá bỏ dấu, viết thường)
PE_KEYWORDS = ["p/e", "price to earning", "gia/loi nhuan", "gia tren loi nhuan"]
PB_KEYWORDS = ["p/b", "price to book", "gia/gia tri so sach", "gia tren gia tri so sach"]


def _normalize(text: str) -> str:
    text = str(text).lower().strip()
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if not unicodedata.combining(c))


def _find_item_row(ratio_df: pd.DataFrame, keywords):
    if "item" not in ratio_df.columns:
        return None
    normalized = ratio_df["item"].map(_normalize)
    mask = normalized.apply(lambda x: any(k in x for k in keywords))
    matches = ratio_df[mask]
    return matches.iloc[0] if not matches.empty else None


def _year_columns(ratio_df: pd.DataFrame) -> list:
    """Trả về danh sách cột năm (dạng số), sắp xếp tăng dần theo thời gian."""
    return sorted([c for c in ratio_df.columns if str(c).isdigit()], key=int)


def percentile_rank(current_value: float, history) -> float:
    """Trả về percentile (0-100) của current_value trong tập history."""
    history = pd.Series(history).dropna()
    if history.empty or pd.isna(current_value):
        return np.nan
    return float((history < current_value).mean() * 100)


def build_valuation_summary(symbol: str, ratio_df: pd.DataFrame) -> dict:
    year_cols = _year_columns(ratio_df)
    if not year_cols:
        return {
            "symbol": symbol, "current_pe": None, "current_pb": None,
            "valuation_score": 50.0,
            "note": f"Không tìm thấy cột năm dạng số. Cột hiện có: {list(ratio_df.columns)}.",
        }

    pe_row = _find_item_row(ratio_df, PE_KEYWORDS)
    pb_row = _find_item_row(ratio_df, PB_KEYWORDS)

    if pe_row is None and pb_row is None:
        unique_items = ratio_df["item"].dropna().unique().tolist() if "item" in ratio_df else []
        return {
            "symbol": symbol, "current_pe": None, "current_pb": None,
            "valuation_score": 50.0,
            "note": f"Không tìm thấy dòng P/E hoặc P/B. Các item hiện có: {unique_items}. "
                    f"Bổ sung nhãn đúng vào PE_KEYWORDS/PB_KEYWORDS trong valuation.py.",
        }

    percentiles = []
    current_pe = current_pb = None

    if pe_row is not None:
        pe_series = pe_row[year_cols].astype(float)
        current_pe = pe_series.iloc[-1]  # năm gần nhất (year_cols đã sort tăng dần)
        p = percentile_rank(current_pe, pe_series)
        if not np.isnan(p):
            percentiles.append(p)

    if pb_row is not None:
        pb_series = pb_row[year_cols].astype(float)
        current_pb = pb_series.iloc[-1]
        p = percentile_rank(current_pb, pb_series)
        if not np.isnan(p):
            percentiles.append(p)

    score = 100 - (sum(percentiles) / len(percentiles)) if percentiles else 50.0

    note = ""
    if len(year_cols) < 4:
        note = f"Chỉ có {len(year_cols)} năm dữ liệu - phân vị định giá có độ tin cậy thấp."

    return {
        "symbol": symbol,
        "current_pe": round(float(current_pe), 2) if current_pe is not None and not pd.isna(current_pe) else None,
        "current_pb": round(float(current_pb), 2) if current_pb is not None and not pd.isna(current_pb) else None,
        "valuation_score": round(float(score), 1),
        "note": note,
    }
