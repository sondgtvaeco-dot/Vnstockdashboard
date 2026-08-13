"""
DB luôn lưu thời gian dạng UTC (chuẩn, không đổi theo múi giờ) - module này chỉ
dùng để CHUYỂN ĐỔI HIỂN THỊ sang giờ Việt Nam trên dashboard, không ảnh hưởng
dữ liệu gốc hay logic thu thập.
"""

import pandas as pd

VN_TZ = "Asia/Ho_Chi_Minh"


def to_vn_time(series: pd.Series) -> pd.Series:
    """Trả về Series datetime (tz-aware) đã chuyển sang giờ Việt Nam."""
    return pd.to_datetime(series, utc=True).dt.tz_convert(VN_TZ)


def to_vn_time_str(series: pd.Series, fmt: str = "%Y-%m-%d %H:%M:%S") -> pd.Series:
    """Trả về Series chuỗi đã format theo giờ Việt Nam."""
    return to_vn_time(series).dt.strftime(fmt)
