# TopCV Automated Cron Job & Session Manager

Dự án tự động hóa TopCV bằng Playwright, chạy trên GitHub Actions (miễn phí, không giới hạn trên repo Public) hoặc máy cá nhân.

---

## 📁 Cấu trúc thư mục

- `login_and_save_cookies.py`: Tool đăng nhập tự động trên máy và trích xuất session cookies mới khi cần.
- `topcv_cron_runner.py`: Script worker chạy định kỳ trên GitHub Actions (hoặc local).
- `env.txt`: File chứa email (dòng 1) và mật khẩu (dòng 2) — **được gitignore hoàn toàn, không bao giờ lộ**.
- `topcv_cookies.json`: File chứa session cookies sau khi đăng nhập — **được gitignore**.
- `.github/workflows/topcv_cron.yml`: Cấu hình GitHub Actions chạy tự động theo lịch cron.

---

## 🚀 Cách sử dụng

### 1. Đăng nhập lại khi cookie hết hạn (Chạy trên máy)
Chỉ cần chạy lệnh sau:
```bash
python3 login_and_save_cookies.py
```
- Script sẽ tự động lấy tài khoản từ `env.txt`, đăng nhập, lưu file `topcv_cookies.json`.
- Tự động copy nội dung cookie mới vào Clipboard của bạn (`Cmd + V`).
- Nếu cần hiện giao diện để giải captcha thủ công:
```bash
python3 login_and_save_cookies.py --visible
```

### 2. Cấu hình GitHub Secrets (Trên Repo Public)
Vào **Settings -> Secrets and variables -> Actions**, thêm 2 secrets:
1. `COOKIES`: Dán toàn bộ nội dung của `topcv_cookies.json` (hoặc `Cmd + V` sau khi chạy script 1).
2. `ENV_TXT`: Dán 2 dòng email và password để làm fallback tự động khi cần.

### 3. Chạy thử kiểm tra phiên trên máy
```bash
python3 topcv_cron_runner.py
```
