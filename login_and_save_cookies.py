import asyncio
import json
import os
import subprocess
import sys
from playwright.async_api import async_playwright

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_FILE = os.path.join(BASE_DIR, "env.txt")
COOKIES_FILE = os.path.join(BASE_DIR, "topcv_cookies.json")
SCREENSHOT_FILE = os.path.join(BASE_DIR, "login_proof.png")

def log(msg):
    print(msg, flush=True)

async def main():
    log("==================================================")
    log("🔐 TOPCV: ĐĂNG NHẬP & TRÍCH XUẤT SESSION COOKIES MỚI")
    log("==================================================")

    # 1. Đọc tài khoản từ env.txt hoặc biến môi trường
    email = os.environ.get("TOPCV_EMAIL", "").strip()
    password = os.environ.get("TOPCV_PASSWORD", "").strip()

    raw_env_txt = os.environ.get("ENV_TXT", "").strip()
    if raw_env_txt and (not email or not password):
        lines = [l.strip() for l in raw_env_txt.splitlines() if l.strip()]
        if len(lines) >= 2:
            email = email or lines[0]
            password = password or lines[1]

    if (not email or not password) and os.path.exists(ENV_FILE):
        with open(ENV_FILE, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f.readlines() if l.strip()]
            if len(lines) >= 2:
                email = email or lines[0]
                password = password or lines[1]

    if not email or not password:
        log(f"❌ Không tìm thấy thông tin đăng nhập trong {ENV_FILE} hoặc biến môi trường!")
        return

    log(f"👤 Tài khoản: {email}")

    # Flag kiểm tra xem muốn mở trình duyệt có giao diện (visible) hay chạy ngầm (headless)
    headless_mode = "--visible" not in sys.argv
    log(f"🖥️  Chế độ trình duyệt: {'Headless (chạy ngầm)' if headless_mode else 'Có giao diện (Visible UI)'}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=headless_mode,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage"
            ]
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 850},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="vi-VN",
            timezone_id="Asia/Ho_Chi_Minh"
        )
        page = await context.new_page()

        log("🌐 Điều hướng đến trang đăng nhập TopCV...")
        await page.goto("https://www.topcv.vn/login", wait_until="networkidle", timeout=35000)

        # 1. Tự động chấp nhận Cookie banner nếu có
        try:
            cookie_btn = await page.query_selector("button.btn-allow-all, button.btn-accept-all")
            if cookie_btn:
                log("🍪 Đã đóng banner cookie...")
                await cookie_btn.click()
        except Exception:
            pass

        # 2. Điền thông tin
        log("✍️  Điền email & mật khẩu...")
        await page.fill("input[name=email]", email)
        await page.fill("input[name=password]", password)
        await asyncio.sleep(1.0)

        # 3. Bấm Đăng nhập
        log("🚀 Nhấn nút 'Đăng nhập'...")
        await page.click("button.btn-sign, button.g-recaptcha")

        # Chờ điều hướng hoặc xử lý captcha
        log("⏳ Đang đợi TopCV xác thực và chuyển trang...")
        for i in range(12):
            await asyncio.sleep(1.0)
            url = page.url
            if "onboard" in url or "viec-lam" in url or (url.rstrip("/").endswith("topcv.vn") and not url.endswith("/login")):
                break

        final_url = page.url
        log(f"📍 URL hiện tại: {final_url}")

        is_success = "login" not in final_url or await page.evaluate("""() => {
            return !document.querySelector('a[href*="/login"]') &&
                   (!!document.querySelector('.dropdown-user, .user-avatar, [href*="/logout"]') ||
                    document.body.innerText.includes('Hoàng Hà') ||
                    document.body.innerText.includes('Chào mừng'));
        }""")

        await page.screenshot(path=SCREENSHOT_FILE)
        log(f"📸 Đã lưu ảnh chụp trạng thái: {SCREENSHOT_FILE}")

        if is_success:
            # 4. Trích xuất toàn bộ cookie phiên mới
            cookies = await context.cookies()
            with open(COOKIES_FILE, "w", encoding="utf-8") as f:
                json.dump(cookies, f, indent=2, ensure_ascii=False)

            log("==================================================")
            log(f"🎉 ĐĂNG NHẬP THÀNH CÔNG! Đã lưu {len(cookies)} cookies vào:")
            log(f"   📄 {COOKIES_FILE}")

            # Tự động copy vào clipboard nếu trên macOS
            if sys.platform == "darwin":
                try:
                    subprocess.run(["pbcopy"], input=json.dumps(cookies, indent=2).encode("utf-8"), check=True)
                    log("📋 ĐÃ TỰ ĐỘNG COPY COOKIES MỚI VÀO CLIPBOARD CỦA BẠN (Cmd + V)!")
                    log("   👉 Bạn chỉ cần mở GitHub Settings -> Secrets -> COOKIES và Paste là xong.")
                except Exception:
                    pass
            log("==================================================")
        else:
            log("❌ Đăng nhập chưa thành công hoặc cần giải Captcha.")
            log("💡 Mẹo: Chạy lại với cờ visible để tự giải captcha nếu cần:")
            log("   python3 login_and_save_cookies.py --visible")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
