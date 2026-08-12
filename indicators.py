"""
Tính toán các chỉ báo kỹ thuật phổ biến (giống chỉ báo hiển thị trên fireant/TradingView)
từ dữ liệu OHLCV thô, dùng pandas/numpy thuần - không phụ thuộc thư viện ngoài
để tránh rủi ro tương thích phiên bản.

Input chuẩn cho mọi hàm: DataFrame có ít nhất các cột
    ['time', 'open', 'high', 'low', 'close', 'volume']
đã được sắp xếp tăng dần theo thời gian (cũ -> mới).
"""

import numpy as np
import pandas as pd


def sma(series: pd.Series, window: int) -> pd.Series:
    """Đường trung bình động giản đơn."""
    return series.rolling(window=window, min_periods=window).mean()


def ema(series: pd.Series, span: int) -> pd.Series:
    """Đường trung bình động hàm mũ."""
    return series.ewm(span=span, adjust=False, min_periods=span).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Relative Strength Index (RSI) - công thức Wilder chuẩn."""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi_val = 100 - (100 / (1 + rs))
    # Khi avg_loss = 0 (giá chỉ tăng liên tục) -> RSI = 100
    rsi_val = rsi_val.where(avg_loss != 0, 100)
    return rsi_val


def macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    """MACD line, signal line và histogram."""
    ema_fast = ema(series, fast)
    ema_slow = ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = ema(macd_line, signal)
    histogram = macd_line - signal_line
    return pd.DataFrame({
        "macd": macd_line,
        "macd_signal": signal_line,
        "macd_hist": histogram,
    })


def bollinger_bands(series: pd.Series, window: int = 20, num_std: float = 2) -> pd.DataFrame:
    """Dải Bollinger: band giữa (SMA), band trên, band dưới."""
    mid = sma(series, window)
    std = series.rolling(window=window, min_periods=window).std()
    upper = mid + num_std * std
    lower = mid - num_std * std
    # %B: vị trí giá hiện tại trong dải (0 = chạm band dưới, 1 = chạm band trên)
    percent_b = (series - lower) / (upper - lower)
    return pd.DataFrame({
        "bb_mid": mid,
        "bb_upper": upper,
        "bb_lower": lower,
        "bb_percent_b": percent_b,
    })


def stochastic(df: pd.DataFrame, k_period: int = 14, d_period: int = 3) -> pd.DataFrame:
    """Stochastic Oscillator %K và %D."""
    low_min = df["low"].rolling(window=k_period, min_periods=k_period).min()
    high_max = df["high"].rolling(window=k_period, min_periods=k_period).max()
    percent_k = 100 * (df["close"] - low_min) / (high_max - low_min)
    percent_d = percent_k.rolling(window=d_period, min_periods=d_period).mean()
    return pd.DataFrame({"stoch_k": percent_k, "stoch_d": percent_d})


def support_resistance(df: pd.DataFrame, window: int = 20) -> pd.DataFrame:
    """
    Vùng hỗ trợ/kháng cự đơn giản dựa trên đáy/đỉnh cục bộ trong `window` phiên gần nhất.
    Đây là cách xấp xỉ; muốn chính xác hơn có thể dùng thuật toán pivot point/zigzag.
    """
    resistance = df["high"].rolling(window=window, min_periods=window).max()
    support = df["low"].rolling(window=window, min_periods=window).min()
    return pd.DataFrame({"support": support, "resistance": resistance})


def compute_all_indicators(df: pd.DataFrame, cfg) -> pd.DataFrame:
    """
    Gộp toàn bộ chỉ báo vào một DataFrame duy nhất, index/thời gian khớp với df gốc.
    `cfg` là module config.py (hoặc bất kỳ object nào có các thuộc tính tương ứng).
    """
    out = df.copy()
    out["rsi"] = rsi(out["close"], cfg.RSI_PERIOD)

    macd_df = macd(out["close"], cfg.MACD_FAST, cfg.MACD_SLOW, cfg.MACD_SIGNAL)
    out = pd.concat([out, macd_df], axis=1)

    bb_df = bollinger_bands(out["close"], cfg.BOLLINGER_WINDOW, cfg.BOLLINGER_STD)
    out = pd.concat([out, bb_df], axis=1)

    stoch_df = stochastic(out, k_period=14, d_period=3)
    out = pd.concat([out, stoch_df], axis=1)

    sr_df = support_resistance(out, cfg.SUPPORT_RESISTANCE_WINDOW)
    out = pd.concat([out, sr_df], axis=1)

    out["sma_20"] = sma(out["close"], 20)
    out["sma_50"] = sma(out["close"], 50)
    out["sma_200"] = sma(out["close"], 200)

    return out


def technical_score(row: pd.Series, cfg) -> float:
    """
    Chấm điểm kỹ thuật (0-100) cho MỘT dòng dữ liệu (thường là phiên gần nhất).
    Điểm càng cao = càng nghiêng về "vùng mua tốt" theo góc nhìn kỹ thuật.
    Đây là heuristic đơn giản, không phải công thức chuẩn hoá học thuật - có thể
    tinh chỉnh trọng số theo phong cách giao dịch của bạn.
    """
    score = 50.0  # điểm trung lập khởi điểm

    # RSI: càng gần/dưới vùng oversold thì cộng điểm, càng gần/trên overbought thì trừ điểm
    if pd.notna(row.get("rsi")):
        if row["rsi"] <= cfg.RSI_OVERSOLD:
            score += 20
        elif row["rsi"] >= cfg.RSI_OVERBOUGHT:
            score -= 20
        else:
            # nội suy tuyến tính giữa hai ngưỡng quanh điểm trung lập 50
            mid = (cfg.RSI_OVERSOLD + cfg.RSI_OVERBOUGHT) / 2
            score += (mid - row["rsi"]) / (mid - cfg.RSI_OVERSOLD) * 10

    # MACD histogram dương & đang tăng -> xu hướng tích cực
    if pd.notna(row.get("macd_hist")):
        score += 10 if row["macd_hist"] > 0 else -10

    # Giá so với dải Bollinger (%B thấp = gần band dưới = có thể quá bán)
    if pd.notna(row.get("bb_percent_b")):
        if row["bb_percent_b"] <= 0.1:
            score += 10
        elif row["bb_percent_b"] >= 0.9:
            score -= 10

    # Giá so với vùng hỗ trợ/kháng cự gần nhất
    if pd.notna(row.get("support")) and pd.notna(row.get("resistance")) and pd.notna(row.get("close")):
        band_range = row["resistance"] - row["support"]
        if band_range > 0:
            pos_in_range = (row["close"] - row["support"]) / band_range
            score += (0.5 - pos_in_range) * 20  # gần đáy vùng -> cộng điểm

    # Xu hướng dài hạn: giá trên SMA200 là tín hiệu uptrend, dưới là downtrend
    if pd.notna(row.get("sma_200")) and pd.notna(row.get("close")):
        score += 5 if row["close"] >= row["sma_200"] else -5

    return float(np.clip(score, 0, 100))
