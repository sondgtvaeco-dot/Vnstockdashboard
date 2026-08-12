"""
Trang "VN30F": dashboard riêng cho phái sinh - dùng basis (chênh lệch giá
hợp đồng tương lai so với chỉ số VN30) thay cho P/E, P/B.
"""

import pandas as pd
import streamlit as st

import db
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
    df_display["run_time"] = df_display["run_time"].astype(str)

    cols = ["trạng thái", "symbol", "combined_score", "zone", "technical_score",
            "basis_score", "last_close", "basis", "basis_pct", "rsi", "run_time"]
    st.dataframe(
        df_display[cols].rename(columns={
            "symbol": "Hợp đồng", "combined_score": "Điểm tổng hợp", "zone": "Vùng giá",
            "technical_score": "Điểm kỹ thuật", "basis_score": "Điểm basis",
            "last_close": "Giá", "basis": "Basis", "basis_pct": "Basis (%)",
            "rsi": "RSI", "run_time": "Lần quét gần nhất (UTC)",
        }),
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
    hist["run_time"] = pd.to_datetime(hist["run_time"])
    hist = hist.sort_values("run_time")

    st.markdown("**Lịch sử điểm số**")
    st.line_chart(hist.set_index("run_time")[["technical_score", "basis_score", "combined_score"]])

    st.markdown("**Giá & Basis**")
    st.line_chart(hist.set_index("run_time")[["last_close"]])
    st.line_chart(hist.set_index("run_time")[["basis_pct"]])

    st.markdown("**Dữ liệu chi tiết**")
    st.dataframe(hist.sort_values("run_time", ascending=False), width="stretch", hide_index=True)
