"""
Trang "Nhật ký giao dịch": theo dõi lãi/lỗ thật, không chỉ ghi chép đơn thuần.

- Cổ phiếu: ghi từng lệnh Mua/Bán như cũ, hệ thống TỰ ĐỘNG tính giá vốn bình
  quân, số lượng đang giữ, lãi/lỗ đã chốt (từ các lần bán) và lãi/lỗ chưa chốt
  (dựa trên giá hiện tại) - không cần tự "mở/đóng lệnh" vì cổ phiếu VN chỉ có
  chiều Long, tồn kho theo giá vốn bình quân là mô hình tự nhiên.
- Phái sinh: có chiều Long/Short nên cần MỞ LỆNH (chọn hướng, giá vào, số hợp
  đồng) rồi ĐÓNG LỆNH (nhập giá đóng) riêng biệt - hệ thống tính lãi/lỗ ngay
  khi đóng, và tính lãi/lỗ tạm tính cho các lệnh đang mở theo giá hiện tại.
"""

from datetime import date

import pandas as pd
import streamlit as st

import db
import pnl
import config as cfg
from auth import require_login

st.set_page_config(page_title="Nhật ký giao dịch", layout="wide")
require_login()

st.title("Nhật ký giao dịch")

asset_type = st.radio("Loại tài sản", ["Cổ phiếu", "Phái sinh"], horizontal=True, key="journal_asset_type")


# ═══════════════════════════════════════════ CỔ PHIẾU ═══════════════════════════════════════════
if asset_type == "Cổ phiếu":
    watchlist = db.get_watchlist()
    latest_scores = db.get_latest_scores()

    with st.form("equity_trade_form"):
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
                db.add_trade(symbol, action, trade_date.isoformat(), price, quantity, note,
                             score_now, zone_now, "Cổ phiếu")
                st.success(f"Đã lưu: {action} {symbol} @ {price} — điểm hệ thống lúc ghi: "
                           f"{score_now if score_now is not None else 'chưa có dữ liệu'}")
                st.rerun()

    st.subheader("Tổng hợp danh mục")
    all_trades = db.get_trades()
    equity_trades = all_trades[all_trades.get("asset_type", "Cổ phiếu").fillna("Cổ phiếu") == "Cổ phiếu"] \
        if not all_trades.empty else all_trades

    if equity_trades.empty:
        st.info("Chưa có giao dịch cổ phiếu nào được ghi.")
    else:
        holdings = pnl.compute_equity_holdings(equity_trades)
        holdings = pnl.add_unrealized_pnl(holdings, latest_scores)

        for _, r in holdings.iterrows():
            if r.get("note"):
                st.warning(f"{r['symbol']}: {r['note']}")

        total_realized = holdings["realized_pnl"].sum()
        total_unrealized = holdings["unrealized_pnl"].dropna().sum()
        col_a, col_b, col_c = st.columns(3)
        col_a.metric("Tổng lãi/lỗ đã chốt", f"{total_realized:,.0f} đ")
        col_b.metric("Tổng lãi/lỗ chưa chốt", f"{total_unrealized:,.0f} đ")
        col_c.metric("Tổng cộng", f"{total_realized + total_unrealized:,.0f} đ")

        st.dataframe(
            holdings[["symbol", "quantity_held", "avg_cost", "current_price",
                      "unrealized_pnl", "unrealized_pnl_pct", "realized_pnl"]].rename(columns={
                "symbol": "Mã", "quantity_held": "Đang giữ", "avg_cost": "Giá vốn BQ",
                "current_price": "Giá hiện tại", "unrealized_pnl": "Lãi/lỗ chưa chốt",
                "unrealized_pnl_pct": "Lãi/lỗ chưa chốt (%)", "realized_pnl": "Lãi/lỗ đã chốt",
            }),
            width="stretch", hide_index=True,
        )
        st.caption(
            "Giá vốn bình quân tự tính từ toàn bộ lịch sử Mua/Bán đã ghi (phương pháp average cost). "
            "Lãi/lỗ chưa chốt dùng giá đóng cửa gần nhất từ lượt quét hệ thống."
        )

    st.subheader("Lịch sử giao dịch đã ghi")
    if equity_trades.empty:
        st.info("Chưa có giao dịch nào.")
    else:
        st.dataframe(
            equity_trades.rename(columns={
                "symbol": "Mã", "action": "Hành động", "trade_date": "Ngày",
                "price": "Giá", "quantity": "Khối lượng", "note": "Ghi chú",
                "combined_score_at_time": "Điểm hệ thống lúc đó",
                "zone_at_time": "Vùng giá lúc đó", "created_at": "Ghi lúc",
            }),
            width="stretch", hide_index=True,
        )


# ═══════════════════════════════════════════ PHÁI SINH ═══════════════════════════════════════════
else:
    futures_watchlist = db.get_futures_watchlist()
    latest_futures_scores = db.get_latest_futures_scores()

    tab_open, tab_close = st.tabs(["Mở lệnh mới", "Đóng lệnh"])

    with tab_open:
        with st.form("open_position_form"):
            col1, col2 = st.columns(2)
            symbol = col1.selectbox("Hợp đồng", futures_watchlist) if futures_watchlist \
                else col1.text_input("Hợp đồng")
            direction = col2.radio("Hướng lệnh", ["Long", "Short"], horizontal=True)

            col3, col4, col5 = st.columns(3)
            entry_date = col3.date_input("Ngày vào lệnh", value=date.today())
            entry_price = col4.number_input("Giá vào", min_value=0.0, step=0.1)
            quantity = col5.number_input("Số hợp đồng", min_value=0.0, step=1.0)

            note = st.text_area("Ghi chú", key="open_note")

            submitted = st.form_submit_button("Mở lệnh", type="primary")
            if submitted:
                if not symbol:
                    st.error("Cần chọn/nhập hợp đồng.")
                else:
                    row = latest_futures_scores[latest_futures_scores["symbol"] == symbol] \
                        if not latest_futures_scores.empty else None
                    score_now = float(row["combined_score"].iloc[0]) if row is not None and not row.empty else None
                    zone_now = row["zone"].iloc[0] if row is not None and not row.empty else None
                    db.open_futures_position(symbol, direction, entry_price, quantity,
                                             entry_date.isoformat(), note, score_now, zone_now)
                    st.success(f"Đã mở lệnh {direction} {symbol} @ {entry_price}, {quantity} hợp đồng.")
                    st.rerun()

    with tab_close:
        open_positions = db.get_futures_positions(status="Mở")
        if open_positions.empty:
            st.info("Không có lệnh nào đang mở.")
        else:
            options = {
                f"#{r['id']} — {r['direction']} {r['symbol']} @ {r['entry_price']} "
                f"({r['quantity']} hợp đồng, mở {r['entry_date']})": r["id"]
                for _, r in open_positions.iterrows()
            }
            choice = st.selectbox("Chọn lệnh cần đóng", list(options.keys()))
            with st.form("close_position_form"):
                col1, col2 = st.columns(2)
                exit_date = col1.date_input("Ngày đóng", value=date.today())
                exit_price = col2.number_input("Giá đóng", min_value=0.0, step=0.1)
                submitted = st.form_submit_button("Đóng lệnh", type="primary")
                if submitted:
                    position_id = options[choice]
                    db.close_futures_position(position_id, exit_price, exit_date.isoformat())
                    st.success(f"Đã đóng lệnh #{position_id} @ {exit_price}.")
                    st.rerun()

    st.subheader("Lệnh đang mở")
    open_positions = db.get_futures_positions(status="Mở")
    if open_positions.empty:
        st.info("Không có lệnh nào đang mở.")
    else:
        open_positions = pnl.add_futures_unrealized_pnl(
            open_positions, latest_futures_scores, cfg.FUTURES_CONTRACT_MULTIPLIER,
        )
        total_unrealized = open_positions["unrealized_pnl"].dropna().sum() if "unrealized_pnl" in open_positions else 0
        st.metric("Tổng lãi/lỗ tạm tính (các lệnh đang mở)", f"{total_unrealized:,.0f} đ")
        st.dataframe(
            open_positions[["id", "symbol", "direction", "entry_price", "current_price",
                            "quantity", "entry_date", "unrealized_pnl", "note"]].rename(columns={
                "id": "ID", "symbol": "Hợp đồng", "direction": "Hướng", "entry_price": "Giá vào",
                "current_price": "Giá hiện tại", "quantity": "Số hợp đồng", "entry_date": "Ngày vào",
                "unrealized_pnl": "Lãi/lỗ tạm tính", "note": "Ghi chú",
            }),
            width="stretch", hide_index=True,
        )
        st.caption(f"Hệ số nhân hợp đồng đang dùng: {cfg.FUTURES_CONTRACT_MULTIPLIER:,.0f} đ/điểm/hợp đồng.")

    st.subheader("Lệnh đã đóng")
    closed_positions = db.get_futures_positions(status="Đã đóng")
    if closed_positions.empty:
        st.info("Chưa có lệnh nào được đóng.")
    else:
        closed_positions = closed_positions.copy()
        closed_positions["realized_pnl"] = closed_positions.apply(
            lambda r: round(pnl.compute_futures_pnl(
                r["direction"], r["entry_price"], r["exit_price"], r["quantity"],
                cfg.FUTURES_CONTRACT_MULTIPLIER,
            ), 2),
            axis=1,
        )
        total_realized = closed_positions["realized_pnl"].sum()
        st.metric("Tổng lãi/lỗ đã chốt (các lệnh đã đóng)", f"{total_realized:,.0f} đ")
        st.dataframe(
            closed_positions[["id", "symbol", "direction", "entry_price", "exit_price",
                              "quantity", "entry_date", "exit_date", "realized_pnl", "note"]].rename(columns={
                "id": "ID", "symbol": "Hợp đồng", "direction": "Hướng", "entry_price": "Giá vào",
                "exit_price": "Giá đóng", "quantity": "Số hợp đồng", "entry_date": "Ngày vào",
                "exit_date": "Ngày đóng", "realized_pnl": "Lãi/lỗ đã chốt", "note": "Ghi chú",
            }),
            width="stretch", hide_index=True,
        )

    # Nhật ký phái sinh cũ (trước khi có hệ thống mở/đóng lệnh) - vẫn hiển thị để không mất dữ liệu
    all_trades = db.get_trades()
    old_futures_trades = all_trades[all_trades.get("asset_type") == "Phái sinh"] if not all_trades.empty else all_trades
    if not old_futures_trades.empty:
        with st.expander("Nhật ký phái sinh cũ (ghi trước khi có hệ thống mở/đóng lệnh)"):
            st.dataframe(
                old_futures_trades.rename(columns={
                    "symbol": "Mã", "action": "Hành động", "trade_date": "Ngày",
                    "price": "Giá", "quantity": "Khối lượng", "note": "Ghi chú",
                    "combined_score_at_time": "Điểm hệ thống lúc đó",
                    "zone_at_time": "Vùng giá lúc đó", "created_at": "Ghi lúc",
                }),
                width="stretch", hide_index=True,
            )
            st.caption("Các dòng này không có thông tin Long/Short nên không tính được lãi/lỗ.")
