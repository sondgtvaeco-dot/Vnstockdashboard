"""
Trang "Nhật ký giao dịch": ghi lại quyết định mua/bán thực tế kèm điểm số tại
thời điểm đó - để sau này đối chiếu xem tín hiệu của hệ thống có đáng tin
không, tương tự lịch sử bảo trì + đánh giá hiệu quả sau sửa chữa.
"""

from datetime import date

import streamlit as st

import db
from auth import require_login

st.set_page_config(page_title="Nhật ký giao dịch", layout="wide")
require_login()

st.title("Nhật ký giao dịch")

watchlist = db.get_watchlist()
latest_scores = db.get_latest_scores()

with st.form("trade_form"):
    col1, col2 = st.columns(2)
    symbol = col1.selectbox("Mã", watchlist) if watchlist else col1.text_input("Mã")
    action = col2.radio("Hành động", ["Mua", "Bán"], horizontal=True)

    col3, col4, col5 = st.columns(3)
    trade_date = col3.date_input("Ngày", value=date.today())
    price = col4.number_input("Giá", min_value=0.0, step=0.01)
    quantity = col5.number_input("Khối lượng", min_value=0.0, step=1.0)

    note = st.text_area("Ghi chú (vd: lý do vào lệnh, cảm nhận thị trường...)")

    submitted = st.form_submit_button("Lưu giao dịch", type="primary")
    if submitted:
        if not symbol:
            st.error("Cần chọn/nhập mã.")
        else:
            row = latest_scores[latest_scores["symbol"] == symbol] if not latest_scores.empty else None
            score_now = float(row["combined_score"].iloc[0]) if row is not None and not row.empty else None
            zone_now = row["zone"].iloc[0] if row is not None and not row.empty else None
            db.add_trade(symbol, action, trade_date.isoformat(), price, quantity, note, score_now, zone_now)
            st.success(
                f"Đã lưu: {action} {symbol} @ {price} — điểm hệ thống lúc ghi: "
                f"{score_now if score_now is not None else 'chưa có dữ liệu'}"
            )

st.subheader("Lịch sử giao dịch đã ghi")
trades = db.get_trades()
if trades.empty:
    st.info("Chưa có giao dịch nào được ghi.")
else:
    st.dataframe(
        trades.rename(columns={
            "symbol": "Mã", "action": "Hành động", "trade_date": "Ngày",
            "price": "Giá", "quantity": "Khối lượng", "note": "Ghi chú",
            "combined_score_at_time": "Điểm hệ thống lúc đó",
            "zone_at_time": "Vùng giá lúc đó", "created_at": "Ghi lúc",
        }),
        width='stretch',
        hide_index=True,
    )
    st.caption(
        "So sánh cột 'Điểm hệ thống lúc đó' với diễn biến giá sau này (xem trang Chi tiết mã) "
        "để tự đánh giá độ tin cậy của tín hiệu theo thời gian."
    )
