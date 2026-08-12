"""
Kết hợp điểm kỹ thuật + điểm định giá thành điểm tổng hợp và nhãn vùng giá.

`weights` và `thresholds` được truyền vào (không đọc thẳng từ config.py) vì
giờ đây người dùng có thể chỉnh 2 giá trị này qua trang "Cấu hình" trên web -
xem db.get_weights()/get_thresholds().

LƯU Ý QUAN TRỌNG: đây là công cụ hỗ trợ tham khảo dựa trên heuristic do người
dùng tự định nghĩa trọng số, KHÔNG phải khuyến nghị đầu tư.
"""

import pandas as pd

ZONE_GOOD = "Vùng giá tốt / đáng cân nhắc"
ZONE_EXPENSIVE = "Vùng giá đắt / thận trọng"
ZONE_NEUTRAL = "Trung lập"


def classify_zone(combined_score: float, thresholds: dict) -> str:
    if combined_score >= thresholds["cheap"]:
        return ZONE_GOOD
    elif combined_score <= thresholds["expensive"]:
        return ZONE_EXPENSIVE
    return ZONE_NEUTRAL


def score_symbol(symbol: str, technical_score: float, valuation_score: float,
                  weights: dict, thresholds: dict) -> dict:
    combined = (
        technical_score * weights["technical"]
        + valuation_score * weights["valuation"]
    )
    return {
        "symbol": symbol,
        "technical_score": round(technical_score, 1),
        "valuation_score": round(valuation_score, 1),
        "combined_score": round(combined, 1),
        "zone": classify_zone(combined, thresholds),
    }


def build_report(rows: list) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("combined_score", ascending=False).reset_index(drop=True)
    return df
