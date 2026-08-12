"""
Trang "Chi tiết mã": chọn 1 mã, xem lịch sử điểm số / giá / RSI theo thời gian.
Tương tự trang xem log cảm biến của một thiết bị cụ thể.
"""

import pandas as pd
import streamlit as st

import db
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
hist["run_time"] = pd.to_datetime(hist["run_time"])
hist = hist.sort_values("run_time")

latest = hist.iloc[-1]
col1, col2, col3, col4 = st.columns(4)
col1.metric("Điểm tổng hợp", f"{latest['combined_score']:.1f}")
col2.metric("Vùng giá", latest["zone"])
col3.metric("Giá đóng cửa", f"{latest['last_close']:.2f}" if pd.notna(latest["last_close"]) else "—")
col4.metric("RSI", f"{latest['rsi']:.1f}" if pd.notna(latest["rsi"]) else "—")

st.subheader("Lịch sử điểm số")
st.line_chart(hist.set_index("run_time")[["technical_score", "valuation_score", "combined_score"]])

st.subheader("Giá đóng cửa")
st.line_chart(hist.set_index("run_time")[["last_close"]])

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
