"""
Cổ phiếu dùng P/E, P/B để đánh giá "đắt/rẻ" (xem valuation.py). Hợp đồng tương
lai VN30F không có P/E - thay vào đó dùng "basis": chênh lệch giữa giá hợp
đồng tương lai và chỉ số cơ sở VN30.

    basis = giá VN30F - giá VN30
    basis_pct = basis / giá VN30 * 100

Basis dương lớn (hợp đồng đắt hơn nhiều so với chỉ số) thường phản ánh tâm lý
lạc quan/đầu cơ mạnh - có thể là vùng quá nóng. Basis âm lớn (hợp đồng rẻ hơn
nhiều) thường phản ánh tâm lý bi quan/hoảng loạn - có thể là vùng quá bán.
Cách chấm điểm ở đây theo logic tương tự valuation.py: basis đang ở vùng thấp
so với lịch sử của chính nó -> điểm cao (nghiêng về "vùng giá tốt").

LƯU Ý QUAN TRỌNG: đây là giả định theo trường phái "hồi quy về trung bình"
(mean-reversion), KHÔNG phải quy luật chắc chắn - basis cũng phản ánh chi phí
vốn/kỳ vọng cổ tức hợp lý, và trong xu hướng mạnh, basis có thể duy trì lệch
pha trong thời gian dài mà không đảo chiều ngay. Chỉ nên dùng làm một góc
nhìn tham khảo, không phải tín hiệu giao dịch độc lập.
"""

import numpy as np
import pandas as pd


def compute_basis_series(futures_df: pd.DataFrame, index_df: pd.DataFrame) -> pd.DataFrame:
    """
    Ghép giá đóng cửa futures và chỉ số cơ sở theo ngày (inner join), tính basis.
    futures_df/index_df: DataFrame chuẩn hoá từ data_fetcher (['time','close',...]).
    """
    f = futures_df[["time", "close"]].rename(columns={"close": "futures_close"})
    i = index_df[["time", "close"]].rename(columns={"close": "index_close"})
    merged = pd.merge(f, i, on="time", how="inner").sort_values("time")
    merged["basis"] = merged["futures_close"] - merged["index_close"]
    merged["basis_pct"] = merged["basis"] / merged["index_close"] * 100
    return merged


def percentile_rank(current_value: float, history: pd.Series) -> float:
    history = history.dropna()
    if history.empty or pd.isna(current_value):
        return np.nan
    return float((history < current_value).mean() * 100)


def build_basis_summary(symbol: str, futures_df: pd.DataFrame, index_df: pd.DataFrame) -> dict:
    merged = compute_basis_series(futures_df, index_df)
    if merged.empty:
        return {
            "symbol": symbol, "basis": None, "basis_pct": None, "basis_score": 50.0,
            "note": "Không ghép được dữ liệu futures và chỉ số cơ sở theo ngày (có thể lệch lịch giao dịch).",
        }

    current_basis_pct = merged["basis_pct"].iloc[-1]
    score = 100 - percentile_rank(current_basis_pct, merged["basis_pct"])
    if pd.isna(score):
        score = 50.0

    note = ""
    if len(merged) < 30:
        note = f"Chỉ có {len(merged)} phiên dữ liệu chung - phân vị basis có độ tin cậy thấp."

    return {
        "symbol": symbol,
        "basis": round(float(merged["basis"].iloc[-1]), 2),
        "basis_pct": round(float(current_basis_pct), 3),
        "basis_score": round(float(score), 1),
        "note": note,
    }
