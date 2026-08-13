"""
Trang "Chi tiết mã": chọn 1 mã, xem lịch sử điểm số / giá / RSI theo thời gian.
Tương tự trang xem log cảm biến của một thiết bị cụ thể.
"""

import pandas as pd
import streamlit as st

import db
import indicator_explain
import vn_time
import config as cfg
from auth import require_login

st.set_page_config(page_title="Chi tiết mã", layout="wide")
require_login()

st.title("Chi tiết mã")

watchlist = db.get_watchlist()
if not watchlist:
    st.info("Watchlist đang trống. Vào trang Cấu hình để thêm mã theo dõi.")
    st.stop()

symbol = st.selectbox("Chọn mã", watchlist)

hist = db.get_score_history(symbol)
if hist.empty:
    st.info(f"Chưa có dữ liệu lịch sử cho {symbol}. Đợi lượt quét tiếp theo từ GitHub Actions.")
    st.stop()

hist = hist.copy()
hist["run_time"] = vn_time.to_vn_time(hist["run_time"])
hist = hist.sort_values("run_time")

latest = hist.iloc[-1]
col1, col2, col3, col4 = st.columns(4)
col1.metric("Điểm tổng hợp", f"{latest['combined_score']:.1f}")
col2.metric("Vùng giá", latest["zone"])
col3.metric("Giá đóng cửa", f"{latest['last_close']:.2f}" if pd.notna(latest["last_close"]) else "—")
col4.metric("RSI", f"{latest['rsi']:.1f}" if pd.notna(latest["rsi"]) else "—")

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

st.subheader("Chi tiết chỉ báo (lượt quét gần nhất)")
indicator_rows = indicator_explain.build_indicator_table(latest, cfg)
if indicator_rows:
    st.dataframe(indicator_rows, width="stretch", hide_index=True)
else:
    st.info("Chưa có dữ liệu chỉ báo chi tiết cho lượt quét này (có thể do quét trước khi tính năng này được thêm).")

st.subheader("Lịch sử điểm số")
st.line_chart(hist.set_index("run_time")[["technical_score", "valuation_score", "combined_score"]])

st.subheader("Giá đóng cửa")
st.line_chart(hist.set_index("run_time")[["last_close"]])

if hist["macd_hist"].notna().any():
    st.subheader("MACD Histogram theo thời gian")
    st.bar_chart(hist.set_index("run_time")[["macd_hist"]])

if hist["mfi"].notna().any():
    st.subheader("MFI (dòng tiền) theo thời gian")
    st.line_chart(hist.set_index("run_time")[["mfi"]])

if hist["current_pe"].notna().any() or hist["current_pb"].notna().any():
    st.subheader("P/E, P/B theo thời gian")
    st.line_chart(hist.set_index("run_time")[["current_pe", "current_pb"]])

st.subheader("Dữ liệu chi tiết")
st.dataframe(
    hist.sort_values("run_time", ascending=False),
    width='stretch',
    hide_index=True,
)

if latest.get("note"):
    st.caption(f"Ghi chú lượt quét gần nhất: {latest['note']}")
