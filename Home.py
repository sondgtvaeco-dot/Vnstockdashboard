"""
Trang "Tổng quan": bảng tất cả mã trong watchlist với đèn trạng thái vùng giá,
tương tự bảng trạng thái thiết bị trong hệ thống giám sát bảo dưỡng.
"""

import streamlit as st

import db
import indicator_explain
import vn_time
import config as cfg
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
    df["run_time"] = vn_time.to_vn_time_str(df["run_time"])

    # Tín hiệu MUA/BÁN/GIỮ ngay trong bảng tổng quan (trước đây phải bấm vào từng mã mới thấy)
    df["tín hiệu"] = df.apply(lambda row: indicator_explain.build_signal(row, cfg)["label"], axis=1)

    # Xu hướng điểm tổng hợp gần đây (sparkline) - giúp bảng bớt "đơn điệu" và
    # thấy ngay mã nào đang cải thiện / xấu đi mà không cần mở từng trang chi tiết
    df["xu hướng gần đây"] = df["symbol"].apply(lambda s: db.get_score_trend(s, limit=20))

    display_cols = ["trạng thái", "symbol", "tín hiệu", "xu hướng gần đây", "combined_score", "zone",
                     "technical_score", "valuation_score", "last_close",
                     "rsi", "mfi", "current_pe", "current_pb", "run_time"]
    st.dataframe(
        df[display_cols].rename(columns={
            "symbol": "Mã", "tín hiệu": "Tín hiệu", "combined_score": "Điểm tổng hợp", "zone": "Vùng giá",
            "technical_score": "Điểm kỹ thuật", "valuation_score": "Điểm định giá",
            "last_close": "Giá đóng cửa", "rsi": "RSI", "mfi": "MFI", "current_pe": "P/E",
            "current_pb": "P/B", "run_time": "Lần quét gần nhất (giờ VN)",
        }),
        column_config={
            "xu hướng gần đây": st.column_config.LineChartColumn(
                "Xu hướng gần đây", y_min=0, y_max=100, width="small",
            ),
        },
        width='stretch',
        hide_index=True,
    )
    st.caption(
        "Tín hiệu ở đây theo trường phái Mean-Reversion. Trang Chi tiết mã có thêm "
        "tín hiệu Trend-Following và lý do cụ thể cho từng chỉ báo."
    )

    n_good = (df["zone"] == "Vùng giá tốt / đáng cân nhắc").sum()
    n_bad = (df["zone"] == "Vùng giá đắt / thận trọng").sum()
    col1, col2, col3 = st.columns(3)
    col1.metric("🟢 Vùng giá tốt", int(n_good))
    col2.metric("🟡 Trung lập", int((df["zone"] == "Trung lập").sum()))
    col3.metric("🔴 Vùng giá đắt", int(n_bad))

    st.caption("Mở trang **Chi tiết mã** ở thanh bên để xem biểu đồ lịch sử điểm số của từng mã.")
