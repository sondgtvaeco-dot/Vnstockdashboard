"""
Diễn giải các chỉ báo chi tiết (MACD, hỗ trợ/kháng cự, Bollinger %B, MFI, OBV)
thành bảng dễ đọc bằng tiếng Việt - dùng chung cho trang Chi tiết mã (cổ phiếu)
và VN30F (phái sinh), tránh lặp code giữa 2 trang.
"""

import pandas as pd

import scorer


def detect_divergence(hist: pd.DataFrame, indicator_col: str, lookback: int = 20, window: int = 3) -> dict:
    """
    Phát hiện phân kỳ (divergence) giữa giá và 1 chỉ báo dạng dao động (RSI/MACD)
    trong `lookback` lượt quét gần nhất:
    - Phân kỳ TĂNG (bullish): giá tạo đáy MỚI THẤP HƠN nhưng chỉ báo tạo đáy CAO HƠN
      -> đà giảm đang yếu đi, cảnh báo khả năng đảo chiều tăng.
    - Phân kỳ GIẢM (bearish): giá tạo đỉnh MỚI CAO HƠN nhưng chỉ báo tạo đỉnh THẤP HƠN
      -> đà tăng đang yếu đi, cảnh báo khả năng đảo chiều giảm.

    Đây là cách phát hiện đơn giản (so sánh 2 đỉnh/đáy cục bộ gần nhất), không thay
    thế phân tích biểu đồ thủ công - chỉ nên dùng làm 1 góc nhìn tham khảo thêm.
    """
    if hist is None or len(hist) < window * 2 + 1:
        return {"type": None, "detail": ""}

    sub = hist.tail(lookback).dropna(subset=["last_close", indicator_col]).reset_index(drop=True)
    if len(sub) < window * 2 + 1:
        return {"type": None, "detail": ""}

    price = sub["last_close"]
    ind = sub[indicator_col]

    is_min = price == price.rolling(window, center=True, min_periods=1).min()
    is_max = price == price.rolling(window, center=True, min_periods=1).max()
    min_idxs = price[is_min].index.tolist()
    max_idxs = price[is_max].index.tolist()

    # Phân kỳ tăng: 2 đáy giá gần nhất - giá thấp dần, chỉ báo cao dần
    if len(min_idxs) >= 2:
        i1, i2 = min_idxs[-2], min_idxs[-1]
        if i2 > i1 and price[i2] < price[i1] and ind[i2] > ind[i1]:
            return {
                "type": "bullish",
                "detail": (
                    f"giá đáy sau thấp hơn ({price[i1]:.2f}→{price[i2]:.2f}) nhưng "
                    f"{indicator_col.upper()} đáy sau cao hơn ({ind[i1]:.1f}→{ind[i2]:.1f})"
                ),
            }

    # Phân kỳ giảm: 2 đỉnh giá gần nhất - giá cao dần, chỉ báo thấp dần
    if len(max_idxs) >= 2:
        i1, i2 = max_idxs[-2], max_idxs[-1]
        if i2 > i1 and price[i2] > price[i1] and ind[i2] < ind[i1]:
            return {
                "type": "bearish",
                "detail": (
                    f"giá đỉnh sau cao hơn ({price[i1]:.2f}→{price[i2]:.2f}) nhưng "
                    f"{indicator_col.upper()} đỉnh sau thấp hơn ({ind[i1]:.1f}→{ind[i2]:.1f})"
                ),
            }

    return {"type": None, "detail": ""}


def check_rsi_macd_divergence(hist: pd.DataFrame) -> dict:
    """Kiểm tra phân kỳ trên cả RSI và MACD, gộp thành 2 danh sách bull/bear."""
    bull, bear = [], []

    rsi_div = detect_divergence(hist, "rsi")
    if rsi_div["type"] == "bullish":
        bull.append(f"Phân kỳ tăng RSI ({rsi_div['detail']})")
    elif rsi_div["type"] == "bearish":
        bear.append(f"Phân kỳ giảm RSI ({rsi_div['detail']})")

    macd_div = detect_divergence(hist, "macd")
    if macd_div["type"] == "bullish":
        bull.append(f"Phân kỳ tăng MACD ({macd_div['detail']})")
    elif macd_div["type"] == "bearish":
        bear.append(f"Phân kỳ giảm MACD ({macd_div['detail']})")

    return {"bull": bull, "bear": bear}


def build_signal(row: pd.Series, cfg, hist: pd.DataFrame = None) -> dict:
    """
    Tổng hợp zone (điểm gộp) + từng chỉ báo riêng lẻ thành 1 tín hiệu MUA/BÁN/GIỮ
    kèm mức độ đồng thuận và lý do cụ thể - trả lời thẳng câu hỏi "tín hiệu này
    có đáng tin không, vì sao" thay vì chỉ đưa 1 con số điểm.

    hist (tuỳ chọn): lịch sử điểm số đầy đủ của mã này (sort tăng dần theo
    run_time) - nếu có, sẽ kiểm tra thêm phân kỳ RSI/MACD (trọng số cao hơn 1
    chỉ báo đơn lẻ vì là tín hiệu đảo chiều tương đối mạnh). Không truyền vào
    (vd khi chấm điểm hàng loạt ở bảng tổng quan) thì bỏ qua bước này.
    """
    zone = row.get("zone")
    if zone == scorer.ZONE_GOOD:
        base_label = "MUA"
    elif zone == scorer.ZONE_EXPENSIVE:
        base_label = "BÁN / CHỐT LỜI"
    else:
        base_label = "GIỮ / CHỜ"

    bull, bear = [], []
    bull_weight, bear_weight = 0.0, 0.0

    if pd.notna(row.get("rsi")):
        if row["rsi"] <= cfg.RSI_OVERSOLD:
            bull.append("RSI quá bán"); bull_weight += 1
        elif row["rsi"] >= cfg.RSI_OVERBOUGHT:
            bear.append("RSI quá mua"); bear_weight += 1

    if pd.notna(row.get("mfi")):
        if row["mfi"] <= cfg.MFI_OVERSOLD:
            bull.append("MFI (dòng tiền) quá bán"); bull_weight += 1
        elif row["mfi"] >= cfg.MFI_OVERBOUGHT:
            bear.append("MFI (dòng tiền) quá mua"); bear_weight += 1

    if pd.notna(row.get("macd")) and pd.notna(row.get("macd_signal")):
        if row["macd"] > row["macd_signal"]:
            bull.append("MACD trên đường tín hiệu"); bull_weight += 1
        else:
            bear.append("MACD dưới đường tín hiệu"); bear_weight += 1

    if pd.notna(row.get("bb_percent_b")):
        if row["bb_percent_b"] <= 0.1:
            bull.append("Sát dải Bollinger dưới"); bull_weight += 1
        elif row["bb_percent_b"] >= 0.9:
            bear.append("Sát dải Bollinger trên"); bear_weight += 1

    if row.get("obv_trend") == "Dòng tiền vào (tăng)":
        bull.append("Dòng tiền vào (OBV tăng)"); bull_weight += 1
    elif row.get("obv_trend") == "Dòng tiền ra (giảm)":
        bear.append("Dòng tiền ra (OBV giảm)"); bear_weight += 1

    if (pd.notna(row.get("support")) and pd.notna(row.get("resistance"))
            and pd.notna(row.get("last_close"))):
        rng = row["resistance"] - row["support"]
        if rng > 0:
            pos = (row["last_close"] - row["support"]) / rng
            if pos <= 0.2:
                bull.append("Giá gần vùng hỗ trợ"); bull_weight += 1
            elif pos >= 0.8:
                bear.append("Giá gần vùng kháng cự"); bear_weight += 1

    if hist is not None:
        divergence = check_rsi_macd_divergence(hist)
        # Phân kỳ là tín hiệu đảo chiều tương đối mạnh - tính trọng số gấp đôi
        # 1 chỉ báo đơn lẻ, nhưng lý do chỉ hiện 1 lần (không lặp chữ).
        for reason in divergence["bull"]:
            bull.append(reason)
            bull_weight += 2
        for reason in divergence["bear"]:
            bear.append(reason)
            bear_weight += 2

    if base_label == "MUA":
        if bull_weight >= 3 and bull_weight > bear_weight:
            confidence = "Đồng thuận cao"
        elif bull_weight > bear_weight:
            confidence = "Đồng thuận trung bình"
        else:
            confidence = "Tín hiệu mâu thuẫn - nên chờ xác nhận thêm trước khi mua"
        reasons = bull if bull else bear
    elif base_label.startswith("BÁN"):
        if bear_weight >= 3 and bear_weight > bull_weight:
            confidence = "Đồng thuận cao"
        elif bear_weight > bull_weight:
            confidence = "Đồng thuận trung bình"
        else:
            confidence = "Tín hiệu mâu thuẫn - nên chờ xác nhận thêm trước khi bán"
        reasons = bear if bear else bull
    else:
        confidence = f"{bull_weight:.0f} điểm nghiêng tăng, {bear_weight:.0f} điểm nghiêng giảm - chưa đủ rõ ràng"
        reasons = bull + bear

    return {"label": base_label, "confidence": confidence, "reasons": reasons}


def build_trend_following_signal(hist: pd.DataFrame, cfg) -> dict:
    """
    Tín hiệu theo trường phái "theo xu hướng dòng tiền mạnh" (trend-following) -
    NGƯỢC với build_signal() ở trên (vốn theo logic mean-reversion: mua khi quá bán).

    Trường phái này: MUA khi dòng tiền ĐÃ xác nhận xu hướng tăng (không chờ giá
    giảm về mới mua), BÁN khi dòng tiền BẮT ĐẦU đảo chiều (không đợi "quá mua"
    mới bán) - đi theo xu hướng thay vì bắt đáy/đỉnh.

    hist: DataFrame lịch sử điểm số của 1 mã, đã sort theo run_time TĂNG DẦN,
    cần tối thiểu 2 dòng để so sánh xu hướng giữa 2 lượt quét gần nhất.
    """
    if len(hist) < 2:
        return {
            "label": "GIỮ / CHỜ",
            "confidence": "Chưa đủ lịch sử để so sánh xu hướng (cần ít nhất 2 lượt quét)",
            "reasons": [],
        }

    latest = hist.iloc[-1]
    prev = hist.iloc[-2]
    bull, bear = [], []
    bull_weight, bear_weight = 0.0, 0.0

    # 1. Xác nhận / phân kỳ giữa giá và OBV - yếu tố quan trọng nhất của trường phái này
    has_price = pd.notna(latest.get("last_close")) and pd.notna(prev.get("last_close"))
    price_up = has_price and latest["last_close"] > prev["last_close"]
    price_down = has_price and latest["last_close"] < prev["last_close"]
    obv_in = latest.get("obv_trend") == "Dòng tiền vào (tăng)"
    obv_out = latest.get("obv_trend") == "Dòng tiền ra (giảm)"

    if price_up and obv_in:
        bull.append("Giá tăng + OBV xác nhận dòng tiền vào (xu hướng thật)"); bull_weight += 1
    elif price_up and obv_out:
        bear.append("Giá tăng nhưng OBV cho thấy dòng tiền ra - phân kỳ cảnh báo"); bear_weight += 1
    elif price_down and obv_out:
        bear.append("Giá giảm + OBV xác nhận dòng tiền ra (xu hướng giảm thật)"); bear_weight += 1
    elif price_down and obv_in:
        bull.append("Giá giảm nhưng OBV cho thấy dòng tiền vào - có thể đang tích luỹ"); bull_weight += 1

    # 2. MFI theo HƯỚNG (không phải theo ngưỡng quá mua/quá bán như mean-reversion)
    if pd.notna(latest.get("mfi")) and pd.notna(prev.get("mfi")):
        if latest["mfi"] > 50 and latest["mfi"] > prev["mfi"]:
            bull.append(f"MFI trên 50 và đang tăng ({prev['mfi']:.0f}→{latest['mfi']:.0f}) - dòng tiền mua mạnh dần")
            bull_weight += 1
        elif latest["mfi"] < 50 and latest["mfi"] < prev["mfi"]:
            bear.append(f"MFI dưới 50 và đang giảm ({prev['mfi']:.0f}→{latest['mfi']:.0f}) - dòng tiền bán mạnh dần")
            bear_weight += 1
        elif prev["mfi"] >= 70 and latest["mfi"] < prev["mfi"]:
            bear.append(f"MFI đang giảm từ vùng cao ({prev['mfi']:.0f}→{latest['mfi']:.0f}) - dòng tiền bắt đầu rút")
            bear_weight += 1

    # 3. MACD Histogram - đà đang mạnh dần hay yếu đi (không phải cắt lên/xuống đơn thuần)
    if pd.notna(latest.get("macd_hist")) and pd.notna(prev.get("macd_hist")):
        if latest["macd_hist"] > 0 and latest["macd_hist"] > prev["macd_hist"]:
            bull.append("MACD Histogram dương và đang giãn ra - đà tăng mạnh dần"); bull_weight += 1
        elif latest["macd_hist"] < 0 and latest["macd_hist"] < prev["macd_hist"]:
            bear.append("MACD Histogram âm và đang giãn ra - đà giảm mạnh dần"); bear_weight += 1
        elif prev["macd_hist"] > 0 and latest["macd_hist"] < prev["macd_hist"]:
            bear.append("MACD Histogram đang co lại từ dương - đà tăng suy yếu"); bear_weight += 1

    # 4. Breakout kháng cự / thủng hỗ trợ
    if pd.notna(latest.get("resistance")) and pd.notna(latest.get("last_close")):
        if latest["last_close"] >= latest["resistance"]:
            bull.append("Giá đã vượt vùng kháng cự gần nhất"); bull_weight += 1
    if pd.notna(latest.get("support")) and pd.notna(latest.get("last_close")):
        if latest["last_close"] <= latest["support"]:
            bear.append("Giá đã thủng vùng hỗ trợ gần nhất"); bear_weight += 1

    # 5. Phân kỳ RSI/MACD - cảnh báo đảo chiều sớm, trọng số cao gấp đôi vì
    # trường phái trend-following coi đây là dấu hiệu XU HƯỚNG SẮP KẾT THÚC,
    # quan trọng hơn nhiều so với việc chỉ đọc mức RSI/MACD hiện tại.
    divergence = check_rsi_macd_divergence(hist)
    for reason in divergence["bull"]:
        bull.append(reason); bull_weight += 2
    for reason in divergence["bear"]:
        bear.append(reason); bear_weight += 2

    if bull_weight > bear_weight:
        label = "MUA (theo xu hướng)"
        confidence = "Đồng thuận cao" if bull_weight >= 2 else "Đồng thuận trung bình"
        reasons = bull
    elif bear_weight > bull_weight:
        label = "BÁN (theo xu hướng)"
        confidence = "Đồng thuận cao" if bear_weight >= 2 else "Đồng thuận trung bình"
        reasons = bear
    else:
        label = "GIỮ / CHỜ"
        confidence = f"{bull_weight:.0f} điểm nghiêng tăng, {bear_weight:.0f} điểm nghiêng giảm - chưa đủ rõ ràng"
        reasons = bull + bear

    return {"label": label, "confidence": confidence, "reasons": reasons}


def build_indicator_table(row: pd.Series, cfg) -> list:
    """
    row: một dòng dữ liệu lấy từ scores_history/futures_scores_history (đã có
    các cột macd, macd_signal, bb_percent_b, support, resistance, mfi, obv_trend...).
    Trả về list[dict] sẵn sàng đưa vào st.dataframe/st.table.
    """
    items = []

    if pd.notna(row.get("macd")) and pd.notna(row.get("macd_signal")):
        if row["macd"] > row["macd_signal"]:
            cross = "MACD trên đường tín hiệu - nghiêng về xu hướng tăng"
        else:
            cross = "MACD dưới đường tín hiệu - nghiêng về xu hướng giảm"
        items.append({
            "Chỉ báo": "MACD",
            "Giá trị": f"{row['macd']:.3f} / tín hiệu {row['macd_signal']:.3f}",
            "Diễn giải": cross,
        })

    if (pd.notna(row.get("support")) and pd.notna(row.get("resistance"))
            and pd.notna(row.get("last_close"))):
        rng = row["resistance"] - row["support"]
        if rng > 0:
            pos = (row["last_close"] - row["support"]) / rng * 100
            pos_text = f"Giá đang ở {pos:.0f}% trong vùng hỗ trợ-kháng cự (0% = sát hỗ trợ, 100% = sát kháng cự)"
        else:
            pos_text = "—"
        items.append({
            "Chỉ báo": "Hỗ trợ / Kháng cự",
            "Giá trị": f"{row['support']:.2f} / {row['resistance']:.2f}",
            "Diễn giải": pos_text,
        })

    if pd.notna(row.get("bb_percent_b")):
        b = row["bb_percent_b"]
        if b <= 0.1:
            bb_text = "Sát dải Bollinger dưới - có thể đang quá bán"
        elif b >= 0.9:
            bb_text = "Sát dải Bollinger trên - có thể đang quá mua"
        else:
            bb_text = "Đang ở vùng trung tính của dải Bollinger"
        items.append({"Chỉ báo": "Bollinger %B", "Giá trị": f"{b:.2f}", "Diễn giải": bb_text})

    if pd.notna(row.get("mfi")):
        mfi = row["mfi"]
        if mfi <= cfg.MFI_OVERSOLD:
            mfi_text = "Dòng tiền bán chiếm ưu thế mạnh - có thể đang quá bán"
        elif mfi >= cfg.MFI_OVERBOUGHT:
            mfi_text = "Dòng tiền mua chiếm ưu thế mạnh - có thể đang quá mua"
        else:
            mfi_text = "Dòng tiền mua/bán tương đối cân bằng"
        items.append({"Chỉ báo": "MFI (dòng tiền)", "Giá trị": f"{mfi:.1f}", "Diễn giải": mfi_text})

    if row.get("obv_trend"):
        items.append({
            "Chỉ báo": "OBV (xu hướng dòng tiền)",
            "Giá trị": "—",
            "Diễn giải": row["obv_trend"],
        })

    return items
