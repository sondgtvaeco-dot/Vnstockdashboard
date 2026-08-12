"""
Trang "Tổng quan": bảng tất cả mã trong watchlist với đèn trạng thái vùng giá,
tương tự bảng trạng thái thiết bị trong hệ thống giám sát bảo dưỡng.
"""

import streamlit as st

import db
from auth import require_login

st.set_page_config(page_title="VN Stock Dashboard - Tổng quan", layout="wide")
require_login()

st.title("Tổng quan vùng giá")
st.caption("Công cụ hỗ trợ tham khảo, không phải khuyến nghị đầu tư.")

ZONE_ICON = {
    "Vùng giá tốt / đáng cân nhắc": "🟢",
    "Trung lập": "🟡",
    "Vùng giá đắt / thận trọng": "🔴",
}

try:
    df = db.get_latest_scores()
except Exception as e:  # noqa: BLE001
    st.error(
        f"Không kết nối được database: {e}\n\n"
        "Kiểm tra secret DB_URL trong Settings → Secrets của Streamlit Cloud."
    )
    st.stop()

if df.empty:
    st.info(
        "Chưa có dữ liệu nào. Đợi GitHub Actions chạy lượt quét đầu tiên, "
        "hoặc chạy `python main.py` ở máy local để nạp dữ liệu thử."
    )
else:
    df = df.copy()
    df.insert(0, "trạng thái", df["zone"].map(ZONE_ICON).fillna("⚪"))
    df["run_time"] = df["run_time"].astype(str)

    display_cols = ["trạng thái", "symbol", "combined_score", "zone",
                     "technical_score", "valuation_score", "last_close",
                     "rsi", "current_pe", "current_pb", "run_time"]
    st.dataframe(
        df[display_cols].rename(columns={
            "symbol": "Mã", "combined_score": "Điểm tổng hợp", "zone": "Vùng giá",
            "technical_score": "Điểm kỹ thuật", "valuation_score": "Điểm định giá",
            "last_close": "Giá đóng cửa", "rsi": "RSI", "current_pe": "P/E",
            "current_pb": "P/B", "run_time": "Lần quét gần nhất (UTC)",
        }),
        width='stretch',
        hide_index=True,
    )

    n_good = (df["zone"] == "Vùng giá tốt / đáng cân nhắc").sum()
    n_bad = (df["zone"] == "Vùng giá đắt / thận trọng").sum()
    col1, col2, col3 = st.columns(3)
    col1.metric("🟢 Vùng giá tốt", int(n_good))
    col2.metric("🟡 Trung lập", int((df["zone"] == "Trung lập").sum()))
    col3.metric("🔴 Vùng giá đắt", int(n_bad))

    st.caption("Mở trang **Chi tiết mã** ở thanh bên để xem biểu đồ lịch sử điểm số của từng mã.")
