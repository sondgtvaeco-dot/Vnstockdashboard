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

# ── Cấu hình mặc định cho phái sinh VN30F ──
# Danh sách hợp đồng theo dõi. VN30F1M = kỳ hạn gần nhất (thanh khoản cao nhất,
# thường được theo dõi nhiều nhất). Có thể thêm VN30F2M/F3M/F4M qua trang Cấu hình.
FUTURES_WATCHLIST = ["VN30F1M"]
# Chỉ số cơ sở dùng để tính basis (chênh lệch giá phái sinh - chỉ số cơ sở).
# VN30F định giá theo chỉ số VN30, KHÔNG phải VNINDEX.
FUTURES_UNDERLYING_INDEX = "VN30"

FUTURES_TECHNICAL_WEIGHT = 0.5
FUTURES_BASIS_WEIGHT = 0.5

FUTURES_ZONE_CHEAP_THRESHOLD = 65
FUTURES_ZONE_EXPENSIVE_THRESHOLD = 35

# Hệ số nhân hợp đồng VN30F: 1 điểm chỉ số = 100.000 VNĐ/hợp đồng (chuẩn phổ
# biến của VN30F trên HNX tại thời điểm viết code này). Kiểm tra lại quy định
# hiện hành trước khi dùng để tính lãi/lỗ thật - có thể thay đổi theo thời gian.
FUTURES_CONTRACT_MULTIPLIER = 100_000

# Số phiên NẾN NGÀY dùng làm bộ lọc xu hướng dài hạn (xem daily_trend_sma trong
# indicators.py). Mặc định 100 vì gói vnstock Community (miễn phí) giới hạn tối
# đa 100 bản ghi/lượt gọi bất kể lookback_days yêu cầu bao nhiêu - 200 sẽ luôn
# trả về None với gói này. Nếu đã nâng cấp gói trả phí, có thể tăng lại lên 200.
TREND_SMA_PERIOD = 100

LOOKBACK_DAYS = 500

# ── Khung nến (interval) ──
# '1D' = nến ngày (mặc định an toàn, ai cũng dùng được).
# Khung phút ('15m', '5m', '1m', '1H') THƯỜNG CHỈ KHẢ DỤNG VỚI TÀI KHOẢN
# VNSTOCK PREMIUM/PRO - hãy test với 1-2 mã trước khi đổi cả watchlist.
EQUITY_INTERVAL = "15m"
EQUITY_INTRADAY_LOOKBACK_DAYS = 30   # ~30 ngày x ~26 nến/phiên (15 phút) = đủ cho SMA200

FUTURES_INTERVAL = "5m"
FUTURES_INTRADAY_LOOKBACK_DAYS = 15  # ~15 ngày x ~75 nến/phiên (5 phút) = đủ cho SMA200

RATIO_PERIOD = "year"

# Độ trễ (giây) giữa mỗi mã khi quét - vnstock gói Community giới hạn 60
# request/phút; mỗi mã tốn ~3 request (giá + báo cáo tài chính + SMA dài hạn),
# nên giãn cách ra để không dồn cụm chạm giới hạn khi watchlist lớn dần.
API_CALL_DELAY_SECONDS = 2

RSI_PERIOD = 14
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70

MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

BOLLINGER_WINDOW = 20
BOLLINGER_STD = 2

SUPPORT_RESISTANCE_WINDOW = 20

# Chỉ báo dòng tiền
MFI_PERIOD = 14
MFI_OVERSOLD = 20
MFI_OVERBOUGHT = 80
OBV_WINDOW = 20  # số phiên để xác định xu hướng OBV (so với đường trung bình của chính nó)

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
