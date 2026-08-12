"""
Bảo vệ dashboard bằng 1 mật khẩu đơn giản (đủ dùng cho công cụ cá nhân, không
phải hệ thống multi-user). Đặt APP_PASSWORD trong Streamlit secrets để bật.
Nếu không đặt secret này, dashboard mở tự do (phù hợp khi chỉ chạy local).
"""

import streamlit as st


def require_login() -> None:
    try:
        password = st.secrets.get("APP_PASSWORD")
    except Exception:
        password = None

    if not password:
        return  # chưa cấu hình mật khẩu -> bỏ qua (vd chạy local để tự kiểm thử)

    if st.session_state.get("authenticated"):
        return

    st.title("Đăng nhập")
    pwd = st.text_input("Mật khẩu", type="password")
    if st.button("Đăng nhập"):
        if pwd == password:
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Sai mật khẩu.")
    st.stop()
