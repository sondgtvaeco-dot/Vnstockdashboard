"""
Trang "Cấu hình": chỉnh watchlist, ngưỡng phân vùng, trọng số kỹ thuật/định giá
- lưu vào Postgres, áp dụng ở lượt quét (GitHub Actions) tiếp theo. Không cần
sửa code hay push lại Git.
"""

import streamlit as st

import db
from auth import require_login

st.set_page_config(page_title="Cấu hình", layout="wide")
require_login()

st.title("Cấu hình")
st.caption("Thay đổi ở đây sẽ áp dụng ở lượt quét tiếp theo (chạy định kỳ qua GitHub Actions).")

st.subheader("Danh sách mã theo dõi")
current_watchlist = db.get_watchlist()
watchlist_text = st.text_area(
    "Mỗi mã cách nhau bằng dấu phẩy hoặc xuống dòng",
    value=", ".join(current_watchlist),
    height=100,
)

st.subheader("Ngưỡng phân loại vùng giá")
st.caption("Điểm tổng hợp (0-100): ≥ ngưỡng 'tốt' → Vùng giá tốt. ≤ ngưỡng 'đắt' → Vùng giá đắt.")
thresholds = db.get_thresholds()
col1, col2 = st.columns(2)
cheap = col1.number_input("Ngưỡng 'vùng giá tốt' (≥)", min_value=0, max_value=100,
                           value=int(thresholds["cheap"]))
expensive = col2.number_input("Ngưỡng 'vùng giá đắt' (≤)", min_value=0, max_value=100,
                               value=int(thresholds["expensive"]))

st.subheader("Trọng số điểm tổng hợp")
st.caption("Điểm tổng hợp = Điểm kỹ thuật × trọng số kỹ thuật + Điểm định giá × trọng số định giá.")
weights = db.get_weights()
col3, col4 = st.columns(2)
w_tech = col3.slider("Trọng số kỹ thuật", 0.0, 1.0, float(weights["technical"]), step=0.05)
w_val = col4.slider("Trọng số định giá", 0.0, 1.0, float(weights["valuation"]), step=0.05)

if cheap <= expensive:
    st.warning("Ngưỡng 'vùng giá tốt' nên lớn hơn ngưỡng 'vùng giá đắt' để tránh chồng chéo phân loại.")

if st.button("Lưu cấu hình", type="primary"):
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
            db.set_weights(w_tech / total, w_val / total)  # chuẩn hoá tổng = 1
            st.success(f"Đã lưu. Watchlist hiện có {len(symbols)} mã: {', '.join(symbols)}")
