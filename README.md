# VN Stock Dashboard — Giám sát vùng giá cổ phiếu VN

Dashboard web (Streamlit) hiển thị vùng giá mua/bán cho danh mục cổ phiếu VN,
dựa trên chỉ báo kỹ thuật (RSI, MACD, Bollinger...) kết hợp điểm định giá cơ
bản (P/E, P/B so với lịch sử). Có trang cấu hình, trang chi tiết từng mã với
biểu đồ lịch sử, và nhật ký giao dịch để tự đối chiếu hiệu quả theo thời gian.

## Kiến trúc

```
vnstock (nguồn dữ liệu)
   → main.py (collector, chạy định kỳ qua GitHub Actions)
   → Postgres/Supabase (lưu lịch sử điểm số, cấu hình, nhật ký)
   → Streamlit app (Home.py + pages/, đọc/ghi cùng Postgres)
   → Người dùng (trình duyệt)
```

Cả collector (GitHub Actions) và web app (Streamlit Cloud) cùng kết nối vào
**một Postgres duy nhất** — không dùng SQLite/file cục bộ, vì filesystem của
Streamlit Cloud là tạm thời: mọi thứ ghi trực tiếp từ trang Cấu hình/Nhật ký
sẽ mất khi app khởi động lại nếu không lưu ở một DB nằm ngoài container.

## 1. Thiết lập Supabase (Postgres miễn phí)

1. Tạo tài khoản tại https://supabase.com → New Project (chọn vùng gần VN, vd Singapore).
2. Mở project vừa tạo, tìm nút **Connect** ở đầu trang dashboard (không còn nằm
   trong menu Settings nữa — Supabase đã đổi vị trí này qua nhiều lần cập nhật
   giao diện, nếu không thấy nút "Connect" hãy tìm theo từ khoá "connection string"
   trong thanh tìm kiếm của dashboard).
3. Trong bảng hiện ra, chọn tab **Session pooler** (không chọn "Direct
   connection") — kết nối trực tiếp của Supabase mặc định chỉ hỗ trợ IPv6,
   trong khi GitHub Actions/Streamlit Cloud cần IPv4. Copy chuỗi dạng:
   `postgresql://postgres.xxxxx:[YOUR-PASSWORD]@aws-x-xxxx.pooler.supabase.com:5432/postgres`
4. Thay `[YOUR-PASSWORD]` bằng mật khẩu database thật (đặt lúc tạo project;
   quên thì vào **Project Settings → Database** để reset).
5. Không cần tạo bảng thủ công — `db.init_db()` trong `main.py` tự tạo bảng
   (`CREATE TABLE IF NOT EXISTS`) ở lần chạy đầu tiên.

## 2. Chạy local để kiểm thử

```bash
pip install -r requirements.txt

# macOS/Linux
export DB_URL="postgresql://...connection-string-từ-supabase..."
export VNSTOCK_API_KEY="vnstock_xxx..."   # đăng ký tại vnstocks.com/login

# Windows PowerShell
$env:DB_URL = "postgresql://...connection-string-từ-supabase..."
$env:VNSTOCK_API_KEY = "vnstock_xxx..."

python main.py            # chạy 1 lượt quét, ghi vào Postgres
streamlit run Home.py     # mở dashboard tại http://localhost:8501
```

Chạy thử không cần internet/DB (dữ liệu giả lập, chỉ kiểm thử logic chỉ báo):
```bash
python main.py --demo
```

Để test dashboard local với mật khẩu bật/tắt: copy `.streamlit/secrets.toml.example`
thành `.streamlit/secrets.toml` (đã có trong `.gitignore`, không bị commit),
điền `APP_PASSWORD` và `DB_URL` thật.

## 3. Đẩy lên GitHub

```bash
git init
git add .
git commit -m "Init VN stock dashboard"
git branch -M main
git remote add origin https://github.com/<username>/<ten-repo>.git
git push -u origin main
```

`config.py` không chứa secret nào (đọc từ biến môi trường), nên repo có thể để
public. Nếu trước đó bạn từng hardcode API key thật vào file `.py` nào rồi
commit, coi như key đó đã lộ — tạo key mới và đảm bảo lịch sử git sạch (tạo
repo mới nếu cần) trước khi để public.

## 4. Cấu hình GitHub Actions (bộ thu thập dữ liệu)

Vào repo → **Settings → Secrets and variables → Actions → New repository secret**:

| Tên secret | Giá trị |
|---|---|
| `VNSTOCK_API_KEY` | API key từ vnstocks.com/login |
| `DB_URL` | Connection string Supabase (bước 1) |

`.github/workflows/scan.yml` sẽ tự chạy `main.py` mỗi 30 phút trong giờ giao
dịch VN (9:00-15:00, Thứ 2-6). Có thể bấm chạy tay ở tab **Actions → VN Stock
Scan → Run workflow** để nạp dữ liệu ngay mà không cần đợi lịch.

**Về độ "real-time":** đây là polling 30 phút/lần, không phải dữ liệu tick-by-tick
tức thời, và GitHub Actions free tier không đảm bảo giờ chạy tuyệt đối (có
thể trễ vài phút). Muốn dày hơn, sửa `cron` trong `scan.yml` (tối thiểu 5 phút).

## 5. Deploy dashboard lên Streamlit Community Cloud

1. Vào https://share.streamlit.io → **New app** → chọn repo GitHub vừa push.
2. Main file path: `Home.py`.
3. Vào **Settings → Secrets** của app, dán:
   ```toml
   APP_PASSWORD = "mật khẩu bạn tự chọn"
   DB_URL = "postgresql://...connection-string-từ-supabase..."
   ```
4. Deploy. Mỗi lần push code mới lên GitHub, app tự deploy lại.

`APP_PASSWORD` là bảo vệ đơn giản (1 mật khẩu chung) — đủ dùng vì đây là công
cụ cá nhân, không phải hệ thống nhiều người dùng với phân quyền.

## Các trang trong dashboard

| Trang | Chức năng |
|---|---|
| **Tổng quan** (`Home.py`) | Bảng tất cả mã theo dõi, đèn màu theo vùng giá (🟢 tốt / 🟡 trung lập / 🔴 đắt), sort theo điểm tổng hợp |
| **Chi tiết mã** | Chọn 1 mã, xem biểu đồ lịch sử điểm kỹ thuật/định giá/tổng hợp, giá đóng cửa, P/E-P/B theo thời gian |
| **Cấu hình** | Sửa watchlist, ngưỡng phân vùng, trọng số kỹ thuật/định giá — lưu vào Postgres, áp dụng từ lượt quét tiếp theo, không cần sửa code |
| **Nhật ký** | Ghi lại quyết định mua/bán thật (mã, giá, khối lượng, ghi chú) kèm điểm số hệ thống tại thời điểm đó, để tự đối chiếu hiệu quả tín hiệu về sau |

## Cách đọc điểm số

| Cột | Ý nghĩa |
|---|---|
| `technical_score` | 0-100, từ RSI/MACD/Bollinger/hỗ trợ-kháng cự/xu hướng SMA200. Cao = tín hiệu kỹ thuật nghiêng về mua |
| `valuation_score` | 0-100, từ P/E/P/B hiện tại so với phân vị lịch sử của chính mã đó. Cao = đang "rẻ" tương đối so với lịch sử |
| `combined_score` | Trung bình có trọng số 2 điểm trên (chỉnh trọng số ở trang Cấu hình) |
| `zone` | ≥ ngưỡng "tốt" → Vùng giá tốt; ≤ ngưỡng "đắt" → Vùng giá đắt; còn lại → Trung lập |

**Cách dùng gợi ý:** xem `combined_score` như bộ lọc sơ bộ để rút ngắn danh
sách cần nghiên cứu kỹ hơn — không phải tín hiệu mua/bán tự động. Luôn kiểm
tra thêm tin tức/thanh khoản/câu chuyện doanh nghiệp, và đặt stop-loss khi
vào lệnh thật. Dùng trang Nhật ký để tự theo dõi xem tín hiệu này có thực sự
đáng tin theo thời gian hay không, trước khi tin tưởng hoàn toàn vào nó.

## Cấu trúc project

| File/thư mục | Chức năng |
|---|---|
| `config.py` | Giá trị mặc định (watchlist, tham số chỉ báo), đọc secrets từ env |
| `db.py` | Lớp truy cập Postgres dùng chung cho collector + dashboard |
| `data_fetcher.py` | Lấy OHLCV, chỉ số, VN30F, báo cáo tài chính qua vnstock |
| `indicators.py` | Tự tính RSI, MACD, Bollinger, Stochastic, hỗ trợ/kháng cự |
| `valuation.py` | Chấm điểm định giá theo phân vị P/E, P/B lịch sử |
| `scorer.py` | Kết hợp điểm kỹ thuật + định giá → nhãn vùng giá |
| `main.py` | Collector: quét watchlist, ghi lịch sử vào Postgres (chạy qua Actions) |
| `auth.py` | Bảo vệ mật khẩu đơn giản cho dashboard |
| `Home.py` | Trang Tổng quan (entry point của Streamlit app) |
| `pages/` | 3 trang còn lại: Chi tiết mã, Cấu hình, Nhật ký |
| `.github/workflows/scan.yml` | Lịch chạy collector tự động |

## Mở rộng sang phái sinh VN30F

`data_fetcher.get_futures_ohlcv("VN30F1M")` đã có sẵn để lấy giá hợp đồng
tương lai VN30. Có thể thêm một bảng `futures_scores_history` tương tự và 1
trang dashboard riêng cho phái sinh theo cùng mô hình này. Lưu ý mã hợp đồng
(VN30F1M/F2M...) đổi theo tháng đáo hạn, cần cập nhật `config.py` định kỳ.

## Những điều cần lưu ý

- **Không phải khuyến nghị đầu tư.** Điểm số là heuristic tự định nghĩa
  trọng số/ngưỡng — không có công thức nào đúng tuyệt đối.
- vnstock là dự án cộng đồng, dữ liệu có thể trễ hoặc không đầy đủ; giấy phép
  hướng tới cá nhân/nghiên cứu, phi thương mại.
- Supabase free tier có giới hạn (dung lượng, số kết nối) — quy mô dùng cá
  nhân trong hệ thống này (vài chục mã, quét 30 phút/lần) nằm rất xa giới hạn đó.
