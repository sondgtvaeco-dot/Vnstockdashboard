"""
Cấu hình mặc định cho pipeline. Các giá trị dưới đây là DEFAULT/FALLBACK khi
database chưa có bản ghi nào (lần chạy đầu tiên). Sau khi hệ thống chạy, watchlist/
ngưỡng/trọng số THỰC TẾ được đọc và ghi qua trang "Cấu hình" trên web (lưu trong
Postgres, xem db.py) — chỉnh trên web sẽ không cần sửa file này hay push lại code.

QUAN TRỌNG VỀ BẢO MẬT: KHÔNG hardcode API key/connection string trực tiếp trong
file này. Toàn bộ secret đọc từ biến môi trường - xem README phần "Bảo mật".
"""

import os

# Tự nạp file .env cục bộ nếu có (dùng cho chạy local, KHÔNG ảnh hưởng GitHub
# Actions/Streamlit Cloud vì 2 nơi đó set biến môi trường/secrets theo cách
# riêng của họ, không cần file .env). File .env đã nằm trong .gitignore.
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv chưa cài -> vẫn chạy được nếu biến môi trường đã set theo cách khác

# ── Giá trị mặc định (dùng khi DB chưa có config) ──
WATCHLIST = ["VNM", "FPT", "VCB", "ACB", "HPG"]

FUTURES_SYMBOL = "VN30F1M"
MARKET_INDEX = "VNINDEX"

LOOKBACK_DAYS = 500
RATIO_PERIOD = "year"

RSI_PERIOD = 14
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70

MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

BOLLINGER_WINDOW = 20
BOLLINGER_STD = 2

SUPPORT_RESISTANCE_WINDOW = 20

TECHNICAL_WEIGHT = 0.5
VALUATION_WEIGHT = 0.5

ZONE_CHEAP_THRESHOLD = 65
ZONE_EXPENSIVE_THRESHOLD = 35

# ── SECRETS: đọc từ biến môi trường, KHÔNG hardcode giá trị thật ở đây ──
# vnstock API key: đăng ký miễn phí tại https://vnstocks.com/login
VNSTOCK_API_KEY = os.environ.get("VNSTOCK_API_KEY")

# Connection string Postgres (Supabase). Dùng chung cho cả collector (main.py)
# và Streamlit app. Set biến môi trường DB_URL khi chạy local, set GitHub
# Secret + Streamlit Cloud secret khi deploy - xem README.
DB_URL = os.environ.get("DB_URL")
