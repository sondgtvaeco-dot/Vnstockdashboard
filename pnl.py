"""
Tính lãi/lỗ (P&L) cho nhật ký giao dịch:
  - Cổ phiếu: phương pháp giá vốn bình quân (average cost) - vì thị trường VN
    không cho bán khống cổ phiếu, mọi vị thế đều là Long, tự động cộng dồn từ
    lịch sử Mua/Bán trong bảng trade_journal, không cần người dùng tự "mở/đóng lệnh".
  - Phái sinh: theo từng lệnh Long/Short riêng biệt (bảng futures_positions),
    người dùng chủ động mở lệnh rồi đóng lệnh, hệ thống tính lãi/lỗ khi đóng.
"""

import pandas as pd


def compute_equity_holdings(trades_df: pd.DataFrame) -> pd.DataFrame:
    """
    trades_df: các dòng trade_journal của cổ phiếu (asset_type='Cổ phiếu'),
    cần có cột symbol/action/price/quantity/created_at.

    Trả về DataFrame: symbol, quantity_held, avg_cost, realized_pnl (tổng
    lãi/lỗ ĐÃ CHỐT từ các lần bán, tính theo giá vốn bình quân tại thời điểm bán).
    """
    if trades_df.empty:
        return pd.DataFrame(columns=["symbol", "quantity_held", "avg_cost", "realized_pnl", "note"])

    results = []
    for symbol, group in trades_df.sort_values("created_at").groupby("symbol"):
        qty = 0.0
        avg_cost = 0.0
        realized_pnl = 0.0
        warning = ""

        for _, trade in group.iterrows():
            price = trade["price"] or 0.0
            quantity = trade["quantity"] or 0.0

            if trade["action"] == "Mua":
                new_qty = qty + quantity
                if new_qty > 0:
                    avg_cost = (qty * avg_cost + quantity * price) / new_qty
                qty = new_qty
            elif trade["action"] == "Bán":
                if quantity > qty:
                    warning = "Đã bán nhiều hơn số lượng đang giữ theo nhật ký - kiểm tra lại dữ liệu đã ghi."
                realized_pnl += (price - avg_cost) * min(quantity, qty) if qty > 0 else 0.0
                qty -= quantity

        results.append({
            "symbol": symbol, "quantity_held": qty, "avg_cost": round(avg_cost, 4),
            "realized_pnl": round(realized_pnl, 2), "note": warning,
        })

    return pd.DataFrame(results)


def add_unrealized_pnl(holdings_df: pd.DataFrame, latest_scores_df: pd.DataFrame) -> pd.DataFrame:
    """Ghép giá hiện tại (last_close từ scores_history mới nhất) và tính lãi/lỗ chưa chốt."""
    if holdings_df.empty:
        out = holdings_df.copy()
        out["current_price"] = []
        out["unrealized_pnl"] = []
        out["unrealized_pnl_pct"] = []
        return out

    price_map = dict(zip(latest_scores_df["symbol"], latest_scores_df["last_close"]))
    out = holdings_df.copy()
    out["current_price"] = out["symbol"].map(price_map)

    def _calc_pnl(row):
        if pd.isna(row["current_price"]) or row["quantity_held"] <= 0 or row["avg_cost"] <= 0:
            return pd.Series({"unrealized_pnl": None, "unrealized_pnl_pct": None})
        pnl = (row["current_price"] - row["avg_cost"]) * row["quantity_held"]
        pct = (row["current_price"] - row["avg_cost"]) / row["avg_cost"] * 100
        return pd.Series({"unrealized_pnl": round(pnl, 2), "unrealized_pnl_pct": round(pct, 2)})

    out = pd.concat([out, out.apply(_calc_pnl, axis=1)], axis=1)
    return out


def compute_futures_pnl(direction: str, entry_price: float, exit_price: float,
                         quantity: float, multiplier: float) -> float:
    """
    Lãi/lỗ 1 lệnh phái sinh đã đóng:
      Long:  (giá đóng - giá vào) x số hợp đồng x hệ số nhân
      Short: (giá vào - giá đóng) x số hợp đồng x hệ số nhân
    """
    if direction == "Long":
        return (exit_price - entry_price) * quantity * multiplier
    return (entry_price - exit_price) * quantity * multiplier


def add_futures_unrealized_pnl(open_positions_df: pd.DataFrame, latest_futures_scores_df: pd.DataFrame,
                                multiplier: float) -> pd.DataFrame:
    """Ghép giá hiện tại và tính lãi/lỗ tạm tính cho các lệnh phái sinh đang MỞ."""
    if open_positions_df.empty:
        return open_positions_df

    price_map = dict(zip(latest_futures_scores_df["symbol"], latest_futures_scores_df["last_close"]))
    out = open_positions_df.copy()
    out["current_price"] = out["symbol"].map(price_map)

    def _calc(row):
        if pd.isna(row["current_price"]):
            return None
        return round(compute_futures_pnl(
            row["direction"], row["entry_price"], row["current_price"], row["quantity"], multiplier,
        ), 2)

    out["unrealized_pnl"] = out.apply(_calc, axis=1)
    return out
