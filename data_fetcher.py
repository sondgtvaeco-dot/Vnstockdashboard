"""
Lớp bọc (wrapper) quanh thư viện vnstock (Unified UI, bản >=4.0) để lấy:
  - Giá lịch sử OHLCV của cổ phiếu
  - Giá lịch sử chỉ số VNINDEX
  - Giá lịch sử hợp đồng tương lai VN30F
  - Báo cáo tỷ số tài chính (P/E, P/B...) phục vụ chấm điểm định giá

QUAN TRỌNG: vnstock cần kết nối internet tới các nguồn dữ liệu VN (KBS/VCI/MSN...).
Module này KHÔNG chạy được trong môi trường sandbox không có internet ra ngoài -
bạn cần chạy trên máy cá nhân/server có mạng thông thường.

Tham khảo cấu trúc API đầy đủ bằng lệnh:
    from vnstock import show_api
    show_api()
Vì đây là API đang phát triển, nếu tên hàm/tham số đổi khác so với dưới đây,
hãy chạy show_api() để cập nhật lại cách gọi.
"""

from datetime import datetime, timedelta

import pandas as pd


class VNDataFetcher:
    def __init__(self, api_key: str | None = None):
        # Import trong __init__ để module này vẫn "import" được (ví dụ để test
        # indicators.py bằng dữ liệu giả) ngay cả khi chưa cài vnstock.
        from vnstock import Market, Fundamental, Reference, register_user

        if api_key:
            register_user(api_key=api_key)

        self.market = Market()
        self.fundamental = Fundamental()
        self.reference = Reference()

    @staticmethod
    def _date_range(lookback_days: int):
        end = datetime.today().date()
        start = end - timedelta(days=lookback_days)
        return start.isoformat(), end.isoformat()

    def get_equity_ohlcv(self, symbol: str, lookback_days: int = 500, interval: str = "1D") -> pd.DataFrame:
        """
        Giá lịch sử OHLCV của một mã cổ phiếu.
        interval: '1D' (ngày, mặc định) hoặc khung phút '1m'/'5m'/'15m'/'1H' -
        LƯU Ý: khung phút thường chỉ khả dụng với tài khoản vnstock Premium/Pro.
        """
        start, end = self._date_range(lookback_days)
        df = self.market.equity(symbol).ohlcv(start=start, end=end, interval=interval)
        return self._standardize_ohlcv(df)

    def get_index_ohlcv(self, index_symbol: str = "VNINDEX", lookback_days: int = 500,
                         interval: str = "1D") -> pd.DataFrame:
        """Giá lịch sử chỉ số (VNINDEX, VN30...). Xem ghi chú interval ở get_equity_ohlcv."""
        start, end = self._date_range(lookback_days)
        df = self.market.index(index_symbol).ohlcv(start=start, end=end, interval=interval)
        return self._standardize_ohlcv(df)

    def get_futures_ohlcv(self, futures_symbol: str = "VN30F1M", lookback_days: int = 500,
                           interval: str = "1D") -> pd.DataFrame:
        """Giá lịch sử hợp đồng tương lai chỉ số VN30. Xem ghi chú interval ở get_equity_ohlcv."""
        start, end = self._date_range(lookback_days)
        df = self.market.futures(futures_symbol).ohlcv(start=start, end=end, interval=interval)
        return self._standardize_ohlcv(df)

    def get_ratios(self, symbol: str, period: str = "year") -> pd.DataFrame:
        """Bảng tỷ số tài chính (P/E, P/B, ROE...) phục vụ chấm điểm định giá."""
        df = self.fundamental.equity(symbol).ratios(period=period)
        return df

    @staticmethod
    def _standardize_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
        """
        Chuẩn hoá tên cột về dạng ['time','open','high','low','close','volume']
        vì các nguồn dữ liệu khác nhau (KBS/VCI/MSN) có thể đặt tên cột khác nhau.
        """
        rename_map = {
            "Date": "time", "date": "time", "TradingDate": "time",
            "Open": "open", "High": "high", "Low": "low",
            "Close": "close", "Volume": "volume", "volume_match": "volume",
        }
        df = df.rename(columns=rename_map)
        required = ["time", "open", "high", "low", "close", "volume"]
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise ValueError(
                f"Thiếu cột {missing} sau khi chuẩn hoá. Cột hiện có: {list(df.columns)}. "
                f"Hãy kiểm tra lại cấu trúc dữ liệu trả về từ vnstock (có thể đã đổi tên cột) "
                f"và cập nhật rename_map trong data_fetcher.py."
            )
        df["time"] = pd.to_datetime(df["time"])
        df = df.sort_values("time").reset_index(drop=True)
        return df[required]


def generate_synthetic_ohlcv(n_days: int = 300, start_price: float = 50.0, seed: int = 42) -> pd.DataFrame:
    """
    Sinh dữ liệu OHLCV giả lập (random walk) - CHỈ dùng để kiểm thử logic tính chỉ báo
    khi chưa có kết nối internet tới vnstock, KHÔNG dùng để ra quyết định giao dịch thật.
    """
    import numpy as np

    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(end=datetime.today().date(), periods=n_days)
    returns = rng.normal(loc=0.0003, scale=0.015, size=n_days)
    close = start_price * (1 + returns).cumprod()

    high = close * (1 + rng.uniform(0.0, 0.01, size=n_days))
    low = close * (1 - rng.uniform(0.0, 0.01, size=n_days))
    open_ = low + (high - low) * rng.uniform(0.3, 0.7, size=n_days)
    volume = rng.integers(100_000, 2_000_000, size=n_days)

    return pd.DataFrame({
        "time": dates, "open": open_, "high": high,
        "low": low, "close": close, "volume": volume,
    })
