"""
Trang "Cấu hình": chỉnh watchlist, ngưỡng phân vùng, trọng số cho cả cổ phiếu
và phái sinh - lưu vào Postgres, áp dụng ở lượt quét (GitHub Actions) tiếp
theo. Không cần sửa code hay push lại Git.
"""

import streamlit as st

import db
from auth import require_login

st.set_page_config(page_title="Cấu hình", layout="wide")
require_login()

st.title("Cấu hình")
st.caption("Thay đổi ở đây sẽ áp dụng ở lượt quét tiếp theo (chạy định kỳ qua GitHub Actions).")

tab_equity, tab_futures = st.tabs(["Cổ phiếu", "Phái sinh (VN30F)"])

with tab_equity:
    st.subheader("Danh sách mã theo dõi")
    current_watchlist = db.get_watchlist()
    watchlist_text = st.text_area(
        "Mỗi mã cách nhau bằng dấu phẩy hoặc xuống dòng",
        value=", ".join(current_watchlist),
        height=100,
        key="equity_watchlist",
    )

    st.subheader("Ngưỡng phân loại vùng giá")
    st.caption("Điểm tổng hợp (0-100): ≥ ngưỡng 'tốt' → Vùng giá tốt. ≤ ngưỡng 'đắt' → Vùng giá đắt.")
    thresholds = db.get_thresholds()
    col1, col2 = st.columns(2)
    cheap = col1.number_input("Ngưỡng 'vùng giá tốt' (≥)", min_value=0, max_value=100,
                               value=int(thresholds["cheap"]), key="equity_cheap")
    expensive = col2.number_input("Ngưỡng 'vùng giá đắt' (≤)", min_value=0, max_value=100,
                                   value=int(thresholds["expensive"]), key="equity_expensive")

    st.subheader("Trọng số điểm tổng hợp")
    st.caption("Điểm tổng hợp = Điểm kỹ thuật × trọng số kỹ thuật + Điểm định giá × trọng số định giá.")
    weights = db.get_weights()
    col3, col4 = st.columns(2)
    w_tech = col3.slider("Trọng số kỹ thuật", 0.0, 1.0, float(weights["technical"]),
                          step=0.05, key="equity_w_tech")
    w_val = col4.slider("Trọng số định giá", 0.0, 1.0, float(weights["valuation"]),
                         step=0.05, key="equity_w_val")

    if cheap <= expensive:
        st.warning("Ngưỡng 'vùng giá tốt' nên lớn hơn ngưỡng 'vùng giá đắt' để tránh chồng chéo phân loại.")

    if st.button("Lưu cấu hình cổ phiếu", type="primary", key="save_equity"):
        symbols = [s.strip().upper() for s in watchlist_text.replace("\n", ",").split(",") if s.strip()]
        if not symbols:
            st.error("Watchlist không được để trống.")
        else:
            total = w_tech + w_val
            if total <= 0:
                st.error("Tổng trọng số phải lớn hơn 0.")
            else:
                db.set_watchlist(symbols)
                db.set_thresholds(cheap, expensive)
                db.set_weights(w_tech / total, w_val / total)
                st.success(f"Đã lưu. Watchlist hiện có {len(symbols)} mã: {', '.join(symbols)}")

with tab_futures:
    st.subheader("Danh sách hợp đồng theo dõi")
    st.caption(
        "Mã hợp đồng VN30F đổi theo tháng đáo hạn (VN30F1M = kỳ hạn gần nhất). "
        "Kiểm tra mã hợp đồng hiện hành trước khi thêm."
    )
    current_futures = db.get_futures_watchlist()
    futures_text = st.text_area(
        "Mỗi mã cách nhau bằng dấu phẩy hoặc xuống dòng",
        value=", ".join(current_futures),
        height=80,
        key="futures_watchlist",
    )

    st.subheader("Ngưỡng phân loại vùng giá")
    f_thresholds = db.get_futures_thresholds()
    col5, col6 = st.columns(2)
    f_cheap = col5.number_input("Ngưỡng 'vùng giá tốt' (≥)", min_value=0, max_value=100,
                                 value=int(f_thresholds["cheap"]), key="futures_cheap")
    f_expensive = col6.number_input("Ngưỡng 'vùng giá đắt' (≤)", min_value=0, max_value=100,
                                     value=int(f_thresholds["expensive"]), key="futures_expensive")

    st.subheader("Trọng số điểm tổng hợp")
    st.caption("Điểm tổng hợp = Điểm kỹ thuật × trọng số kỹ thuật + Điểm basis × trọng số basis.")
    f_weights = db.get_futures_weights()
    col7, col8 = st.columns(2)
    f_w_tech = col7.slider("Trọng số kỹ thuật", 0.0, 1.0, float(f_weights["technical"]),
                            step=0.05, key="futures_w_tech")
    f_w_basis = col8.slider("Trọng số basis", 0.0, 1.0, float(f_weights["basis"]),
                             step=0.05, key="futures_w_basis")

    if f_cheap <= f_expensive:
        st.warning("Ngưỡng 'vùng giá tốt' nên lớn hơn ngưỡng 'vùng giá đắt' để tránh chồng chéo phân loại.")

    if st.button("Lưu cấu hình phái sinh", type="primary", key="save_futures"):
        symbols = [s.strip().upper() for s in futures_text.replace("\n", ",").split(",") if s.strip()]
        if not symbols:
            st.error("Watchlist phái sinh không được để trống.")
        else:
            total = f_w_tech + f_w_basis
            if total <= 0:
                st.error("Tổng trọng số phải lớn hơn 0.")
            else:
                db.set_futures_watchlist(symbols)
                db.set_futures_thresholds(f_cheap, f_expensive)
                db.set_futures_weights(f_w_tech / total, f_w_basis / total)
                st.success(f"Đã lưu. Watchlist phái sinh hiện có: {', '.join(symbols)}")
