"""
Diễn giải các chỉ báo chi tiết (MACD, hỗ trợ/kháng cự, Bollinger %B, MFI, OBV)
thành bảng dễ đọc bằng tiếng Việt - dùng chung cho trang Chi tiết mã (cổ phiếu)
và VN30F (phái sinh), tránh lặp code giữa 2 trang.
"""

import pandas as pd

import scorer


def build_signal(row: pd.Series, cfg) -> dict:
    """
    Tổng hợp zone (điểm gộp) + từng chỉ báo riêng lẻ thành 1 tín hiệu MUA/BÁN/GIỮ
    kèm mức độ đồng thuận và lý do cụ thể - trả lời thẳng câu hỏi "tín hiệu này
    có đáng tin không, vì sao" thay vì chỉ đưa 1 con số điểm.
    """
    zone = row.get("zone")
    if zone == scorer.ZONE_GOOD:
        base_label = "MUA"
    elif zone == scorer.ZONE_EXPENSIVE:
        base_label = "BÁN / CHỐT LỜI"
    else:
        base_label = "GIỮ / CHỜ"

    bull, bear = [], []

    if pd.notna(row.get("rsi")):
        if row["rsi"] <= cfg.RSI_OVERSOLD:
            bull.append("RSI quá bán")
        elif row["rsi"] >= cfg.RSI_OVERBOUGHT:
            bear.append("RSI quá mua")

    if pd.notna(row.get("mfi")):
        if row["mfi"] <= cfg.MFI_OVERSOLD:
            bull.append("MFI (dòng tiền) quá bán")
        elif row["mfi"] >= cfg.MFI_OVERBOUGHT:
            bear.append("MFI (dòng tiền) quá mua")

    if pd.notna(row.get("macd")) and pd.notna(row.get("macd_signal")):
        if row["macd"] > row["macd_signal"]:
            bull.append("MACD trên đường tín hiệu")
        else:
            bear.append("MACD dưới đường tín hiệu")

    if pd.notna(row.get("bb_percent_b")):
        if row["bb_percent_b"] <= 0.1:
            bull.append("Sát dải Bollinger dưới")
        elif row["bb_percent_b"] >= 0.9:
            bear.append("Sát dải Bollinger trên")

    if row.get("obv_trend") == "Dòng tiền vào (tăng)":
        bull.append("Dòng tiền vào (OBV tăng)")
    elif row.get("obv_trend") == "Dòng tiền ra (giảm)":
        bear.append("Dòng tiền ra (OBV giảm)")

    if (pd.notna(row.get("support")) and pd.notna(row.get("resistance"))
            and pd.notna(row.get("last_close"))):
        rng = row["resistance"] - row["support"]
        if rng > 0:
            pos = (row["last_close"] - row["support"]) / rng
            if pos <= 0.2:
                bull.append("Giá gần vùng hỗ trợ")
            elif pos >= 0.8:
                bear.append("Giá gần vùng kháng cự")

    if base_label == "MUA":
        if len(bull) >= 3 and len(bull) > len(bear):
            confidence = "Đồng thuận cao"
        elif len(bull) > len(bear):
            confidence = "Đồng thuận trung bình"
        else:
            confidence = "Tín hiệu mâu thuẫn - nên chờ xác nhận thêm trước khi mua"
        reasons = bull if bull else bear
    elif base_label.startswith("BÁN"):
        if len(bear) >= 3 and len(bear) > len(bull):
            confidence = "Đồng thuận cao"
        elif len(bear) > len(bull):
            confidence = "Đồng thuận trung bình"
        else:
            confidence = "Tín hiệu mâu thuẫn - nên chờ xác nhận thêm trước khi bán"
        reasons = bear if bear else bull
    else:
        confidence = f"{len(bull)} chỉ báo nghiêng tăng, {len(bear)} chỉ báo nghiêng giảm - chưa đủ rõ ràng"
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

    # 1. Xác nhận / phân kỳ giữa giá và OBV - yếu tố quan trọng nhất của trường phái này
    has_price = pd.notna(latest.get("last_close")) and pd.notna(prev.get("last_close"))
    price_up = has_price and latest["last_close"] > prev["last_close"]
    price_down = has_price and latest["last_close"] < prev["last_close"]
    obv_in = latest.get("obv_trend") == "Dòng tiền vào (tăng)"
    obv_out = latest.get("obv_trend") == "Dòng tiền ra (giảm)"

    if price_up and obv_in:
        bull.append("Giá tăng + OBV xác nhận dòng tiền vào (xu hướng thật)")
    elif price_up and obv_out:
        bear.append("Giá tăng nhưng OBV cho thấy dòng tiền ra - phân kỳ cảnh báo")
    elif price_down and obv_out:
        bear.append("Giá giảm + OBV xác nhận dòng tiền ra (xu hướng giảm thật)")
    elif price_down and obv_in:
        bull.append("Giá giảm nhưng OBV cho thấy dòng tiền vào - có thể đang tích luỹ")

    # 2. MFI theo HƯỚNG (không phải theo ngưỡng quá mua/quá bán như mean-reversion)
    if pd.notna(latest.get("mfi")) and pd.notna(prev.get("mfi")):
        if latest["mfi"] > 50 and latest["mfi"] > prev["mfi"]:
            bull.append(f"MFI trên 50 và đang tăng ({prev['mfi']:.0f}→{latest['mfi']:.0f}) - dòng tiền mua mạnh dần")
        elif latest["mfi"] < 50 and latest["mfi"] < prev["mfi"]:
            bear.append(f"MFI dưới 50 và đang giảm ({prev['mfi']:.0f}→{latest['mfi']:.0f}) - dòng tiền bán mạnh dần")
        elif prev["mfi"] >= 70 and latest["mfi"] < prev["mfi"]:
            bear.append(f"MFI đang giảm từ vùng cao ({prev['mfi']:.0f}→{latest['mfi']:.0f}) - dòng tiền bắt đầu rút")

    # 3. MACD Histogram - đà đang mạnh dần hay yếu đi (không phải cắt lên/xuống đơn thuần)
    if pd.notna(latest.get("macd_hist")) and pd.notna(prev.get("macd_hist")):
        if latest["macd_hist"] > 0 and latest["macd_hist"] > prev["macd_hist"]:
            bull.append("MACD Histogram dương và đang giãn ra - đà tăng mạnh dần")
        elif latest["macd_hist"] < 0 and latest["macd_hist"] < prev["macd_hist"]:
            bear.append("MACD Histogram âm và đang giãn ra - đà giảm mạnh dần")
        elif prev["macd_hist"] > 0 and latest["macd_hist"] < prev["macd_hist"]:
            bear.append("MACD Histogram đang co lại từ dương - đà tăng suy yếu")

    # 4. Breakout kháng cự / thủng hỗ trợ
    if pd.notna(latest.get("resistance")) and pd.notna(latest.get("last_close")):
        if latest["last_close"] >= latest["resistance"]:
            bull.append("Giá đã vượt vùng kháng cự gần nhất")
    if pd.notna(latest.get("support")) and pd.notna(latest.get("last_close")):
        if latest["last_close"] <= latest["support"]:
            bear.append("Giá đã thủng vùng hỗ trợ gần nhất")

    if len(bull) > len(bear):
        label = "MUA (theo xu hướng)"
        confidence = "Đồng thuận cao" if len(bull) >= 2 else "Đồng thuận trung bình"
        reasons = bull
    elif len(bear) > len(bull):
        label = "BÁN (theo xu hướng)"
        confidence = "Đồng thuận cao" if len(bear) >= 2 else "Đồng thuận trung bình"
        reasons = bear
    else:
        label = "GIỮ / CHỜ"
        confidence = f"{len(bull)} tín hiệu nghiêng tăng, {len(bear)} nghiêng giảm - chưa đủ rõ ràng"
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
