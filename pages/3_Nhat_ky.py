"""
Trang "Nhật ký giao dịch": ghi lại quyết định mua/bán thực tế (cả cổ phiếu lẫn
phái sinh VN30F) kèm điểm số hệ thống tại thời điểm đó - để sau này đối chiếu
xem tín hiệu có đáng tin không, tương tự lịch sử bảo trì + đánh giá hiệu quả
sau sửa chữa.
"""

from datetime import date

import streamlit as st

import db
from auth import require_login

st.set_page_config(page_title="Nhật ký giao dịch", layout="wide")
require_login()

st.title("Nhật ký giao dịch")

asset_type = st.radio("Loại tài sản", ["Cổ phiếu", "Phái sinh"], horizontal=True, key="journal_asset_type")

if asset_type == "Cổ phiếu":
    watchlist = db.get_watchlist()
    latest_scores = db.get_latest_scores()
    symbol_label = "Mã"
else:
    watchlist = db.get_futures_watchlist()
    latest_scores = db.get_latest_futures_scores()
    symbol_label = "Hợp đồng"

with st.form("trade_form"):
    col1, col2 = st.columns(2)
    symbol = col1.selectbox(symbol_label, watchlist) if watchlist else col1.text_input(symbol_label)
    action = col2.radio("Hành động", ["Mua", "Bán"], horizontal=True)

    col3, col4, col5 = st.columns(3)
    trade_date = col3.date_input("Ngày", value=date.today())
    price = col4.number_input("Giá", min_value=0.0, step=0.01)
    quantity = col5.number_input(
        "Khối lượng" if asset_type == "Cổ phiếu" else "Số hợp đồng", min_value=0.0, step=1.0,
    )

    note = st.text_area("Ghi chú (vd: lý do vào lệnh, cảm nhận thị trường...)")

    submitted = st.form_submit_button("Lưu giao dịch", type="primary")
    if submitted:
        if not symbol:
            st.error(f"Cần chọn/nhập {symbol_label.lower()}.")
        else:
            row = latest_scores[latest_scores["symbol"] == symbol] if not latest_scores.empty else None
            score_now = float(row["combined_score"].iloc[0]) if row is not None and not row.empty else None
            zone_now = row["zone"].iloc[0] if row is not None and not row.empty else None
            db.add_trade(symbol, action, trade_date.isoformat(), price, quantity, note,
                         score_now, zone_now, asset_type)
            st.success(
                f"Đã lưu: {action} {symbol} ({asset_type}) @ {price} — điểm hệ thống lúc ghi: "
                f"{score_now if score_now is not None else 'chưa có dữ liệu'}"
            )

st.subheader("Lịch sử giao dịch đã ghi")
trades = db.get_trades()
if trades.empty:
    st.info("Chưa có giao dịch nào được ghi.")
else:
    filter_type = st.selectbox("Lọc theo loại tài sản", ["Tất cả", "Cổ phiếu", "Phái sinh"])
    trades_display = trades.copy()
    if "asset_type" in trades_display.columns:
        trades_display["asset_type"] = trades_display["asset_type"].fillna("Cổ phiếu")
        if filter_type != "Tất cả":
            trades_display = trades_display[trades_display["asset_type"] == filter_type]
    else:
        trades_display["asset_type"] = "Cổ phiếu"

    st.dataframe(
        trades_display.rename(columns={
            "symbol": "Mã", "action": "Hành động", "trade_date": "Ngày",
            "price": "Giá", "quantity": "Khối lượng", "note": "Ghi chú",
            "combined_score_at_time": "Điểm hệ thống lúc đó",
            "zone_at_time": "Vùng giá lúc đó", "created_at": "Ghi lúc",
            "asset_type": "Loại tài sản",
        }),
        width='stretch',
        hide_index=True,
    )
    st.caption(
        "So sánh cột 'Điểm hệ thống lúc đó' với diễn biến giá sau này (xem trang Chi tiết mã "
        "hoặc VN30F tương ứng) để tự đánh giá độ tin cậy của tín hiệu theo thời gian."
    )
