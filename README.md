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
| **Tổng quan** (`Home.py`) | Bảng tất cả mã theo dõi: đèn màu vùng giá, **cột Tín hiệu MUA/BÁN/GIỮ**, **sparkline xu hướng điểm số 20 lượt quét gần nhất** ngay trong bảng, sort theo điểm tổng hợp |
| **Chi tiết mã** | Chọn 1 mã, xem **tín hiệu MUA/BÁN/GIỮ kèm mức độ đồng thuận + lý do cụ thể**, bảng chi tiết từng chỉ báo, biểu đồ lịch sử điểm số/giá/MACD/MFI |
| **Cấu hình** | Ô **thêm/xoá nhanh 1 mã**, cộng với khung chỉnh hàng loạt watchlist/ngưỡng/trọng số kỹ thuật/định giá — lưu vào Postgres, áp dụng từ lượt quét tiếp theo, không cần sửa code |
| **Nhật ký** | Ghi lại quyết định mua/bán thật (mã, giá, khối lượng, ghi chú) kèm điểm số hệ thống tại thời điểm đó, để tự đối chiếu hiệu quả tín hiệu về sau |

## Cách đọc điểm số

| Cột | Ý nghĩa |
|---|---|
| `technical_score` | 0-100, từ RSI/MACD/Bollinger/hỗ trợ-kháng cự/xu hướng SMA dài hạn (mặc định SMA100, xem `TREND_SMA_PERIOD` trong `config.py`). Cao = tín hiệu kỹ thuật nghiêng về mua |
| `valuation_score` | 0-100, từ P/E/P/B hiện tại so với phân vị lịch sử của chính mã đó. Cao = đang "rẻ" tương đối so với lịch sử |
| `combined_score` | Trung bình có trọng số 2 điểm trên (chỉnh trọng số ở trang Cấu hình) |
| `zone` | ≥ ngưỡng "tốt" → Vùng giá tốt; ≤ ngưỡng "đắt" → Vùng giá đắt; còn lại → Trung lập |

**Cách dùng gợi ý:** xem `combined_score` như bộ lọc sơ bộ để rút ngắn danh
sách cần nghiên cứu kỹ hơn — không phải tín hiệu mua/bán tự động. Luôn kiểm
tra thêm tin tức/thanh khoản/câu chuyện doanh nghiệp, và đặt stop-loss khi
vào lệnh thật. Dùng trang Nhật ký để tự theo dõi xem tín hiệu này có thực sự
đáng tin theo thời gian hay không, trước khi tin tưởng hoàn toàn vào nó.

### Tín hiệu MUA/BÁN/GIỮ tổng hợp

Ngay đầu trang **Chi tiết mã** (và **VN30F**) có khối tín hiệu tổng hợp,
trả lời thẳng câu hỏi "mua/bán khi nào":

- **Nhãn gốc** lấy từ `zone`: `Vùng giá tốt` → **MUA**, `Vùng giá đắt` →
  **BÁN/CHỐT LỜI**, `Trung lập` → **GIỮ/CHỜ**.
- **Mức độ đồng thuận**: hệ thống đếm xem bao nhiêu chỉ báo riêng lẻ (RSI,
  MFI, MACD, Bollinger %B, OBV, vị trí so với hỗ trợ/kháng cự) đang cùng
  hướng với nhãn gốc. Nhiều chỉ báo đồng thuận → "Đồng thuận cao" (tín hiệu
  đáng tin hơn); các chỉ báo mâu thuẫn nhau → cảnh báo "nên chờ xác nhận
  thêm" thay vì hành động ngay.
- **Lý do cụ thể**: liệt kê đúng những chỉ báo nào đang ủng hộ nhãn tín hiệu,
  để tự kiểm tra lại thay vì tin mù quáng vào 1 con số.

### Xem chi tiết từng chỉ báo (không chỉ điểm gộp)

Trang **Chi tiết mã** (và **VN30F**) có mục "Chi tiết chỉ báo" hiển thị riêng
từng thành phần thay vì chỉ con số `technical_score` đã gộp:

| Chỉ báo | Cách đọc |
|---|---|
| MACD | MACD trên đường tín hiệu → nghiêng tăng; dưới → nghiêng giảm |
| Hỗ trợ/Kháng cự | Giá càng gần 0% (sát hỗ trợ) → vùng thường cân nhắc mua; càng gần 100% (sát kháng cự) → vùng thường cân nhắc chốt lời |
| Bollinger %B | ≤0.1 → sát dải dưới (có thể quá bán); ≥0.9 → sát dải trên (có thể quá mua) |
| MFI (dòng tiền) | Giống RSI nhưng có trọng số khối lượng giao dịch - dưới 20 quá bán, trên 80 quá mua |
| OBV (xu hướng dòng tiền) | Dòng tiền vào/ra dựa trên khối lượng cộng dồn theo chiều tăng/giảm giá - dùng để xác nhận hoặc nghi ngờ xu hướng giá hiện tại (vd giá tăng nhưng dòng tiền giảm = cảnh báo phân kỳ) |

Trang Chi tiết mã cũng có biểu đồ lịch sử MACD Histogram và MFI theo thời
gian, ngoài biểu đồ điểm số/giá đã có từ trước.

**Lưu ý về nâng cấp dữ liệu cũ:** nếu bạn đã chạy hệ thống trước khi có tính
năng này, `db.init_db()` sẽ tự thêm các cột mới vào bảng đã có (không mất dữ
liệu cũ) — nhưng các lượt quét *trước* thời điểm nâng cấp sẽ không có dữ liệu
chỉ báo chi tiết (hiển thị "—"), chỉ các lượt quét *sau khi* nâng cấp mới có
đầy đủ.

### Hai trường phái tín hiệu song song

Trang **Chi tiết mã** và **VN30F** hiển thị **2 khối tín hiệu cạnh nhau**,
theo 2 trường phái giao dịch khác nhau trên cùng 1 bộ dữ liệu:

| | Mean-Reversion (khối trái) | Trend-Following (khối phải) |
|---|---|---|
| Logic | Mua khi quá bán, bán khi quá mua - kỳ vọng giá đảo chiều về trung bình | Mua khi dòng tiền đã xác nhận xu hướng, bán khi dòng tiền bắt đầu đảo chiều |
| MFI cao | Tín hiệu xấu (quá mua) | Có thể là tín hiệu tốt nếu đang tăng (dòng tiền mạnh) |
| Yếu tố chính | RSI, MFI theo ngưỡng, MACD cắt lên/xuống | OBV xác nhận/phân kỳ với giá, MFI theo hướng, MACD Histogram giãn/co, breakout |
| Cần dữ liệu | 1 lượt quét | Tối thiểu 2 lượt quét (so sánh xu hướng) |

**2 khối có thể ra tín hiệu khác nhau, thậm chí ngược nhau trên cùng 1 mã** -
đây là điều bình thường vì bản chất 2 triết lý khác nhau, không phải lỗi hệ
thống. Chọn trường phái phù hợp với phong cách giao dịch của bạn (mean-reversion
phù hợp giao dịch dao động trong biên độ; trend-following phù hợp bắt xu hướng
mạnh, chấp nhận vào trễ hơn để đổi lấy xác suất đúng cao hơn).

## Cấu trúc project

| File/thư mục | Chức năng |
|---|---|
| `config.py` | Giá trị mặc định (watchlist, tham số chỉ báo), đọc secrets từ env |
| `db.py` | Lớp truy cập Postgres dùng chung cho collector + dashboard |
| `data_fetcher.py` | Lấy OHLCV, chỉ số, VN30F, báo cáo tài chính qua vnstock |
| `indicators.py` | Tự tính RSI, MACD, Bollinger, Stochastic, hỗ trợ/kháng cự |
| `valuation.py` | Chấm điểm định giá cổ phiếu theo phân vị P/E, P/B lịch sử |
| `futures_analysis.py` | Chấm điểm phái sinh theo phân vị basis lịch sử |
| `indicator_explain.py` | Diễn giải chỉ báo chi tiết (MACD, hỗ trợ/kháng cự, MFI, OBV) thành bảng dễ đọc |
| `scorer.py` | Kết hợp điểm kỹ thuật + định giá/basis → nhãn vùng giá (dùng chung cổ phiếu & phái sinh) |
| `main.py` | Collector cổ phiếu: quét watchlist, ghi lịch sử vào Postgres |
| `main_futures.py` | Collector phái sinh VN30F: quét watchlist, ghi lịch sử vào Postgres |
| `auth.py` | Bảo vệ mật khẩu đơn giản cho dashboard |
| `Home.py` | Trang Tổng quan cổ phiếu (entry point của Streamlit app) |
| `pages/` | Chi tiết mã, Cấu hình (2 tab: cổ phiếu + phái sinh), Nhật ký, VN30F |
| `.github/workflows/scan.yml` | Lịch chạy collector tự động |

## Phái sinh VN30F

Dashboard có trang riêng cho phái sinh (`pages/4_VN30F.py`), chạy song song
với phần cổ phiếu nhưng dùng logic chấm điểm khác vì VN30F không có P/E:

- **`main_futures.py`** — collector riêng, chạy cùng lịch với `main.py` (cùng
  workflow `scan.yml`), ghi vào bảng `futures_scores_history`.
- **`futures_analysis.py`** — thay vì P/E/P/B, tính **basis** (chênh lệch giữa
  giá hợp đồng tương lai và chỉ số cơ sở VN30) và chấm điểm theo phân vị lịch
  sử của basis, cùng logic hồi quy-về-trung-bình như `valuation.py`.
- Điểm kỹ thuật (RSI/MACD/Bollinger) tái dùng nguyên `indicators.py` — không
  cần code riêng.
- Watchlist/ngưỡng/trọng số phái sinh chỉnh ở tab **"Phái sinh (VN30F)"**
  trong trang Cấu hình, độc lập với phần cổ phiếu.

**Lưu ý quan trọng:** mã hợp đồng (`VN30F1M`, `VN30F2M`...) đổi theo tháng
đáo hạn — kiểm tra mã hợp đồng đang giao dịch trước khi thêm vào watchlist,
và cập nhật lại định kỳ khi hợp đồng cũ đáo hạn. Basis-score dựa trên giả
định hồi quy về trung bình — không phải quy luật chắc chắn, đặc biệt trong
các giai đoạn thị trường xu hướng mạnh, basis có thể duy trì lệch pha trong
thời gian dài mà không đảo chiều ngay.

## Khung nến intraday (15 phút cổ phiếu, 5 phút phái sinh)

Mặc định hệ thống giờ dùng nến **15 phút** cho cổ phiếu và nến **5 phút** cho
VN30F (thay vì nến ngày như bản đầu), quét mỗi **5 phút** trong giờ giao dịch.

**⚠️ Cảnh báo quan trọng trước khi bật tính năng này:** theo tài liệu chính
thức của vnstock, dữ liệu khung phút (`1m`/`5m`/`15m`/`1H`) **thường chỉ khả
dụng với tài khoản Premium/Pro**, tuỳ nguồn dữ liệu — API key miễn phí có thể
không truy cập được. **Hãy test với 1-2 mã trước khi mở rộng ra cả danh mục
nhiều ngành:**

```bash
python main.py        # xem log - nếu báo lỗi khi lấy OHLCV, khả năng do giới hạn tài khoản
```

Nếu gặp lỗi quyền truy cập, có 2 lựa chọn: nâng cấp tài khoản vnstock, hoặc
đổi lại `EQUITY_INTERVAL`/`FUTURES_INTERVAL` trong `config.py` về `"1D"` để
quay lại nến ngày (không cần Premium).

**Đã xác nhận qua thực tế sử dụng:** gói vnstock Community (miễn phí) trả về
tối đa **100 bản ghi/lượt gọi**, bất kể `lookback_days` yêu cầu bao nhiêu -
vì vậy `TREND_SMA_PERIOD` mặc định đặt ở 100 (không phải 200 như chuẩn phổ
biến) để luôn tính được với gói miễn phí. Nếu nâng cấp gói trả phí, có thể
tăng `TREND_SMA_PERIOD` lên 200 trong `config.py`.

**Về việc mở rộng watchlist nhiều ngành + quét 5 phút/lần cùng lúc:** đây là
tổ hợp rủi ro thực tế nhất — nhiều mã × quét dày × khung phút = nhiều lượt
gọi API trong thời gian ngắn, dễ chạm rate limit hoặc khiến 1 lượt quét chạy
lâu hơn 5 phút. Workflow đã có cơ chế `concurrency` để tự xếp hàng (không chạy
chồng lấp) nếu việc này xảy ra, nhưng nên **tăng dần watchlist từng bước**
(vd 10 mã → 30 mã → cả danh mục) thay vì bật hết cùng lúc, để phát hiện sớm
nếu chạm giới hạn.

**Đã xác nhận qua sự cố thực tế:** khi chạm rate-limit 60 request/phút, thư
viện vnstock (gói Community) **tự gọi `sys.exit()`** thay vì raise một
`Exception` bình thường - nếu không bắt riêng `SystemExit`, cả lượt quét sẽ
sập ngay tại mã đang xử lý, mất dữ liệu của mọi mã còn lại trong watchlist.
`main.py`/`main_futures.py` đã xử lý việc này: bắt riêng `SystemExit` để bỏ
qua đúng mã bị chặn và tiếp tục các mã còn lại, đồng thời chờ
`API_CALL_DELAY_SECONDS` (mặc định 2 giây) giữa mỗi mã để giãn tải, giảm khả
năng chạm giới hạn ngay từ đầu. Đây là giảm thiểu rủi ro, không phải đảm bảo
tuyệt đối - watchlist càng lớn, khả năng chạm giới hạn vẫn càng cao.

## Những điều cần lưu ý

- **Không phải khuyến nghị đầu tư.** Điểm số là heuristic tự định nghĩa
  trọng số/ngưỡng — không có công thức nào đúng tuyệt đối.
- vnstock là dự án cộng đồng, dữ liệu có thể trễ hoặc không đầy đủ; giấy phép
  hướng tới cá nhân/nghiên cứu, phi thương mại.
- Supabase free tier có giới hạn (dung lượng, số kết nối) — quy mô dùng cá
  nhân trong hệ thống này (vài chục mã, quét 30 phút/lần) nằm rất xa giới hạn đó.
