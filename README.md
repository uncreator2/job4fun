# 🚀 Job4Fun: Multi-Platform Automated Job Application Pipeline

Hệ thống tự động hóa quét việc làm và nộp đơn hàng loạt (Auto-apply) đa nền tảng tuyển dụng hàng đầu Việt Nam qua **GitHub Actions CI/CD** và **Playwright Headless Browser**, vận hành mượt mà qua proxy dân cư VNPT và cơ chế bypass Cloudflare / Nginx WAF.

---

## 🏛️ Cấu Trúc Monorepo Đa Nền Tảng

```text
jobs/
│
├── run_pipeline.py                 # Bộ điều phối trung tâm (Master Orchestrator)
├── shared/                         # Thư viện dùng chung
│   └── proxy_utils.py              # Bộ phân giải proxy dân cư
│
├── topcv/                          # Phân hệ TopCV
│   ├── topcv_cron_runner.py        # Crawler quét việc làm TopCV
│   ├── topcv_applier.py            # Applier nộp đơn tự động TopCV
│   ├── search_urls.txt             # Danh sách URL tìm kiếm mục tiêu
│   ├── extracted_jobs_history.json # Sổ cái việc làm đã quét
│   ├── applied_jobs_history.json   # Sổ cái việc làm đã nộp thành công
│   └── errors/                     # Thư mục lưu lỗi & ảnh chụp sự cố
│
├── vietnamworks/                   # Phân hệ VietnamWorks
│   ├── vnw_crawler.py              # Crawler quét việc làm VietnamWorks
│   ├── vnw_applier.py              # Applier nộp đơn tự động VietnamWorks
│   ├── search_urls.txt             # Danh sách URL tìm kiếm mục tiêu
│   ├── extracted_jobs_history.json # Sổ cái việc làm đã quét (100 jobs)
│   ├── applied_jobs_history.json   # Sổ cái việc làm đã nộp thành công
│   └── errors/                     # Thư mục lưu lỗi & ảnh chụp sự cố
│
├── careerviet/                     # Phân hệ CareerViet (Đang phát triển)
├── vieclam24h/                     # Phân hệ Việc Làm 24h (Đang phát triển)
│
└── .github/workflows/
    └── multi_platform_pipeline.yml# Workflow GitHub Actions điều khiển toàn bộ
```

---

## ⚙️ Thiết Lập GitHub Actions Secrets

| Tên Secret | Mô Tả |
| :--- | :--- |
| `PROXY_SERVER` | Chuỗi proxy dân cư VNPT (`host:port:user:pass`) dùng chung cho mọi sàn |
| `COOKIES` | Session cookie JSON đã đăng nhập của TopCV |
| `ENV_TXT` | Email & Mật khẩu tài khoản TopCV (dùng khi cần relogin) |
| `VNW_COOKIES` | Session cookie JSON đã đăng nhập của VietnamWorks |
| `VNW_ENV` | Email & Mật khẩu tài khoản VietnamWorks |
| `V24H_COOKIES` | Session cookie JSON đã đăng nhập của Vieclam24h |
| `V24H_ENV` | Email & Mật khẩu tài khoản Vieclam24h |

---

## 🔄 Lịch Trình Tự Động (Automation Schedule)

* **Tần suất:** Vận hành **4 ca cố định mỗi ngày** (Thứ 2 - Thứ 6) với hạn mức **30 việc làm / sàn / ca**:
  - **Ca 1 (Đầu giờ sáng):** `08:30 AM VN` (`30 1 * * 1-5` UTC)
  - **Ca 2 (Đầu giờ chiều):** `01:30 PM VN` (`30 6 * * 1-5` UTC)
  - **Ca 3 (Cuối giờ chiều):** `04:30 PM VN` (`30 9 * * 1-5` UTC)
  - **Ca 4 (Tối):** `08:30 PM VN` (`30 13 * * 1-5` UTC)
* **Luồng chạy:** Tuần tự `TopCV -> VietnamWorks -> Vieclam24h`
  * Hoàn toàn độc lập, cách ly lỗi, không xung đột runner, tự động commit sổ cái và upload ảnh bằng chứng sau mỗi ca.

---

## 🏛️ Tài Liệu Kiến Trúc Chi Tiết

Xem sơ đồ thiết kế hệ thống, ma trận chịu lỗi, quy trình xử lý anti-bot và hướng dẫn tích hợp tại:
👉 **[ARCHITECTURE.md](ARCHITECTURE.md)**

