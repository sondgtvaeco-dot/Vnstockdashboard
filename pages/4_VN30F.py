"""
Trang "VN30F": dashboard riêng cho phái sinh - dùng basis (chênh lệch giá
hợp đồng tương lai so với chỉ số VN30) thay cho P/E, P/B.
"""

import pandas as pd
import streamlit as st

import db
import indicator_explain
import vn_time
import config as cfg
from auth import require_login

st.set_page_config(page_title="VN30F - Phái sinh", layout="wide")
require_login()

st.title("VN30F - Phái sinh")
st.caption(
    "Điểm basis dựa trên giả định hồi quy về trung bình (mean-reversion), "
    "không phải quy luật chắc chắn. Công cụ hỗ trợ tham khảo, không phải khuyến nghị đầu tư."
)

with st.expander("Basis là gì?"):
    st.write(
        "Basis = giá hợp đồng tương lai VN30F trừ giá chỉ số VN30 tại cùng thời điểm. "
        "Basis dương lớn (hợp đồng đắt hơn chỉ số nhiều) thường phản ánh tâm lý lạc quan/"
        "đầu cơ mạnh. Basis âm lớn (hợp đồng rẻ hơn chỉ số nhiều) thường phản ánh tâm lý "
        "bi quan/hoảng loạn. Điểm basis trong hệ thống này chấm theo phân vị lịch sử: "
        "basis đang thấp so với lịch sử của chính nó → điểm cao (nghiêng vùng giá tốt)."
    )

ZONE_ICON = {
    "Vùng giá tốt / đáng cân nhắc": "🟢",
    "Trung lập": "🟡",
    "Vùng giá đắt / thận trọng": "🔴",
}

try:
    df = db.get_latest_futures_scores()
except Exception as e:  # noqa: BLE001
    st.error(f"Không kết nối được database: {e}")
    st.stop()

st.subheader("Tổng quan")
if df.empty:
    st.info(
        "Chưa có dữ liệu. Đợi GitHub Actions chạy `main_futures.py`, "
        "hoặc chạy local để nạp dữ liệu thử."
    )
else:
    df_display = df.copy()
    df_display.insert(0, "trạng thái", df_display["zone"].map(ZONE_ICON).fillna("⚪"))
    df_display["run_time"] = vn_time.to_vn_time_str(df_display["run_time"])
    df_display["tín hiệu"] = df_display.apply(
        lambda row: indicator_explain.build_signal(row, cfg)["label"], axis=1
    )
    df_display["xu hướng gần đây"] = df_display["symbol"].apply(
        lambda s: db.get_futures_score_trend(s, limit=20)
    )

    cols = ["trạng thái", "symbol", "tín hiệu", "xu hướng gần đây", "combined_score", "zone",
            "technical_score", "basis_score", "last_close", "basis", "basis_pct", "rsi", "mfi", "run_time"]
    st.dataframe(
        df_display[cols].rename(columns={
            "symbol": "Hợp đồng", "tín hiệu": "Tín hiệu", "combined_score": "Điểm tổng hợp", "zone": "Vùng giá",
            "technical_score": "Điểm kỹ thuật", "basis_score": "Điểm basis",
            "last_close": "Giá", "basis": "Basis", "basis_pct": "Basis (%)",
            "rsi": "RSI", "mfi": "MFI", "run_time": "Lần quét gần nhất (giờ VN)",
        }),
        column_config={
            "xu hướng gần đây": st.column_config.LineChartColumn(
                "Xu hướng gần đây", y_min=0, y_max=100, width="small",
            ),
        },
        width="stretch",
        hide_index=True,
    )

st.subheader("Chi tiết hợp đồng")
watchlist = db.get_futures_watchlist()
if not watchlist:
    st.info("Chưa có hợp đồng nào trong watchlist phái sinh. Thêm ở trang Cấu hình.")
    st.stop()

symbol = st.selectbox("Chọn hợp đồng", watchlist)
hist = db.get_futures_score_history(symbol)
if hist.empty:
    st.info(f"Chưa có dữ liệu lịch sử cho {symbol}.")
else:
    hist = hist.copy()
    hist["run_time"] = vn_time.to_vn_time(hist["run_time"])
    hist = hist.sort_values("run_time")

    latest = hist.iloc[-1]

    sig_col1, sig_col2 = st.columns(2)

    with sig_col1:
        st.markdown("**Tín hiệu Mean-Reversion** _(mua khi quá bán, bán khi quá mua)_")
        signal = indicator_explain.build_signal(latest, cfg)
        signal_text = f"**{signal['label']}** — {signal['confidence']}"
        if signal["reasons"]:
            signal_text += "\n\nLý do: " + ", ".join(signal["reasons"])
        if signal["label"] == "MUA":
            st.success(signal_text)
        elif signal["label"].startswith("BÁN"):
            st.error(signal_text)
        else:
            st.warning(signal_text)

    with sig_col2:
        st.markdown("**Tín hiệu Trend-Following** _(theo xu hướng dòng tiền mạnh)_")
        tf_signal = indicator_explain.build_trend_following_signal(hist, cfg)
        tf_text = f"**{tf_signal['label']}** — {tf_signal['confidence']}"
        if tf_signal["reasons"]:
            tf_text += "\n\nLý do: " + ", ".join(tf_signal["reasons"])
        if tf_signal["label"].startswith("MUA"):
            st.success(tf_text)
        elif tf_signal["label"].startswith("BÁN"):
            st.error(tf_text)
        else:
            st.warning(tf_text)

    st.caption(
        "2 trường phái có thể cho tín hiệu KHÁC NHAU hoặc thậm chí NGƯỢC NHAU trên cùng dữ liệu - "
        "đây là điều bình thường, không phải lỗi. Chọn trường phái phù hợp với phong cách giao dịch "
        "của bạn, không phải khuyến nghị đầu tư."
    )

    st.markdown("**Chi tiết chỉ báo (lượt quét gần nhất)**")
    indicator_rows = indicator_explain.build_indicator_table(latest, cfg)
    if indicator_rows:
        st.dataframe(indicator_rows, width="stretch", hide_index=True)
    else:
        st.info("Chưa có dữ liệu chỉ báo chi tiết cho lượt quét này.")

    st.markdown("**Lịch sử điểm số**")
    st.line_chart(hist.set_index("run_time")[["technical_score", "basis_score", "combined_score"]])

    st.markdown("**Giá & Basis**")
    st.line_chart(hist.set_index("run_time")[["last_close"]])
    st.line_chart(hist.set_index("run_time")[["basis_pct"]])

    if hist["macd_hist"].notna().any():
        st.markdown("**MACD Histogram theo thời gian**")
        st.bar_chart(hist.set_index("run_time")[["macd_hist"]])

    if hist["mfi"].notna().any():
        st.markdown("**MFI (dòng tiền) theo thời gian**")
        st.line_chart(hist.set_index("run_time")[["mfi"]])

    st.markdown("**Dữ liệu chi tiết**")
    st.dataframe(hist.sort_values("run_time", ascending=False), width="stretch", hide_index=True)
