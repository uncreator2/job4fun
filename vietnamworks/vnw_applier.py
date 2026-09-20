import os
import sys
import json
import time
import re
from datetime import datetime
from playwright.sync_api import sync_playwright

# Path configuration
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(SCRIPT_DIR)
TOPCV_DIR = os.path.join(PARENT_DIR, "topcv")
SHARED_DIR = os.path.join(PARENT_DIR, "shared")

for p in [SCRIPT_DIR, TOPCV_DIR, SHARED_DIR]:
    if os.path.exists(p) and p not in sys.path:
        sys.path.append(p)

try:
    from proxy_utils import get_proxy_config
except ImportError:
    def get_proxy_config():
        proxy_str = os.environ.get("PROXY_SERVER", "").strip()
        if not proxy_str:
            return None
        m = re.match(r"^([a-zA-Z0-9.\-]+):(\d+):([^:@]+):([^:@]+)$", proxy_str)
        if m:
            host, port, user, pwd = m.groups()
            return {"server": f"http://{host}:{port}", "username": user, "password": pwd}
        return {"server": proxy_str}

EXTRACTED_HISTORY_FILE = os.path.join(SCRIPT_DIR, "extracted_jobs_history.json")
APPLIED_HISTORY_FILE = os.path.join(SCRIPT_DIR, "applied_jobs_history.json")
APPLIED_HISTORY_TXT = os.path.join(SCRIPT_DIR, "applied_jobs_history.txt")
ERRORS_DIR = os.path.join(SCRIPT_DIR, "errors")
os.makedirs(ERRORS_DIR, exist_ok=True)

MAX_APPLIES_DEFAULT = 100
DRY_RUN_DEFAULT = False

def load_cookies():
    env_cookies = os.environ.get("VNW_COOKIES", "") or os.environ.get("COOKIES", "")
    if env_cookies:
        try:
            return json.loads(env_cookies)
        except Exception:
            pass

    for fname in os.listdir(SCRIPT_DIR):
        if fname.endswith(".json") and "vietnamworks" in fname.lower():
            try:
                with open(os.path.join(SCRIPT_DIR, fname), "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
    return []

def format_cookies_for_playwright(raw_cookies):
    cookies = []
    for c in raw_cookies:
        cookie = {
            "name": c["name"],
            "value": c["value"],
            "domain": c.get("domain", ".vietnamworks.com"),
            "path": c.get("path", "/"),
        }
        if "secure" in c:
            cookie["secure"] = c["secure"]
        if "httpOnly" in c:
            cookie["httpOnly"] = c["httpOnly"]
        cookies.append(cookie)
    return cookies

def load_applied_history():
    applied = {}
    if os.path.exists(APPLIED_HISTORY_FILE):
        try:
            with open(APPLIED_HISTORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    for item in data:
                        url = item.get("url")
                        if url:
                            applied[url] = item
                elif isinstance(data, dict):
                    applied = data
        except Exception as e:
            print(f"⚠️ Lỗi đọc applied history JSON: {e}")

    # Fallback to TXT ledger
    if os.path.exists(APPLIED_HISTORY_TXT):
        try:
            with open(APPLIED_HISTORY_TXT, "r", encoding="utf-8") as f:
                for line in f:
                    url = line.strip()
                    if url and url not in applied:
                        applied[url] = {"url": url, "applied_at": "unknown"}
        except Exception as e:
            print(f"⚠️ Lỗi đọc applied history TXT: {e}")
    return applied

def save_applied_history(applied_dict):
    try:
        with open(APPLIED_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(list(applied_dict.values()), f, ensure_ascii=False, indent=2)
        with open(APPLIED_HISTORY_TXT, "w", encoding="utf-8") as f:
            for url in applied_dict.keys():
                f.write(f"{url}\n")
    except Exception as e:
        print(f"⚠️ Lỗi lưu applied history: {e}")

def handle_experience_modal(page):
    try:
        modal_btn = page.locator('button:has-text("Tiếp tục với Vietnamworks")')
        if modal_btn.count() > 0 and modal_btn.first.is_visible():
            modal_btn.first.click()
            page.wait_for_timeout(1000)
            return True
    except Exception:
        pass
    return False

def verify_and_ensure_login(page):
    print("🔍 Đang kiểm tra trạng thái đăng nhập VietnamWorks...")
    try:
        page.goto("https://www.vietnamworks.com/", wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(2000)
        handle_experience_modal(page)

        profile_btn = page.locator('button[aria-label="profile-button"]')
        if profile_btn.count() > 0 and profile_btn.first.is_visible():
            print("✅ Đã xác thực đăng nhập thành công vào tài khoản VietnamWorks.")
            return True
    except Exception as e:
        print(f"⚠️ Kiểm tra đăng nhập gặp lỗi: {e}")

    # Fallback login attempt
    env_file = os.path.join(SCRIPT_DIR, "env.txt")
    if os.path.exists(env_file):
        try:
            with open(env_file, "r", encoding="utf-8") as f:
                lines = [l.strip() for l in f if l.strip()]
            if len(lines) >= 2:
                user, pwd = lines[0], lines[1]
                print("🔐 Thử đăng nhập tự động bằng tài khoản env.txt...")
                page.goto("https://www.vietnamworks.com/login", wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(2000)
                handle_experience_modal(page)

                email_input = page.locator('input[type="email"], input[name="email"], input[placeholder*="email"]')
                if email_input.count() > 0:
                    email_input.first.fill(user)
                    pwd_input = page.locator('input[type="password"], input[name="password"]')
                    pwd_input.first.fill(pwd)
                    submit_login = page.locator('button[type="submit"], button:has-text("Đăng nhập")')
                    submit_login.first.click()
                    page.wait_for_timeout(5000)
                    handle_experience_modal(page)
                    return True
        except Exception as e:
            print(f"❌ Thử đăng nhập tự động thất bại: {e}")
    return False

def sync_vnw_applied_history(page, applied_dict):
    """
    Scrapes https://www.vietnamworks.com/quan-ly-nghe-nghiep/viec-lam-cua-toi
    to synchronize already-applied jobs into our ledger.
    """
    print("🔄 Đang đồng bộ lịch sử ứng tuyển từ VietnamWorks...")
    try:
        history_url = "https://www.vietnamworks.com/quan-ly-nghe-nghiep/viec-lam-cua-toi"
        page.goto(history_url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(3000)
        handle_experience_modal(page)

        applied_links = page.evaluate("""() => {
            const links = Array.from(document.querySelectorAll('a[href*="-jv"]')).map(a => a.href.split('?')[0]);
            return Array.from(new Set(links));
        }""")

        synced_count = 0
        for url in applied_links:
            if url not in applied_dict:
                applied_dict[url] = {
                    "url": url,
                    "status": "ALREADY_APPLIED_PORTAL",
                    "synced_at": datetime.now().isoformat()
                }
                synced_count += 1

        print(f"✅ Đã đồng bộ {len(applied_links)} việc làm từ cổng VietnamWorks (+{synced_count} mới).")
        save_applied_history(applied_dict)
    except Exception as e:
        print(f"⚠️ Đồng bộ lịch sử tuyển dụng gặp lỗi: {e}")

def check_daily_limit(page):
    """
    Kiểm tra xem VietnamWorks có thông báo đạt giới hạn nộp hồ sơ / số lượt nộp trong ngày hay không.
    Trả về (True, message) nếu đạt giới hạn, ngược lại (False, None).
    """
    keywords = [
        "đạt giới hạn", "hết lượt", "vượt quá số lần", "vượt quá số lượt",
        "giới hạn nộp", "giới hạn ứng tuyển", "ứng tuyển trong ngày",
        "tối đa trong ngày", "lượt nộp đơn trong ngày",
        "application limit", "daily limit", "reached limit", "limit exceeded"
    ]
    try:
        # 1. Kiểm tra toast / notification / alert
        elements = page.locator('[role="alert"], [class*="toast"], [class*="Toast"], [class*="notification"], .ant-message, .ant-notification, .alert')
        count = elements.count()
        for i in range(count):
            try:
                el = elements.nth(i)
                if el.is_visible():
                    text = el.inner_text().strip()
                    text_lower = text.lower()
                    for kw in keywords:
                        if kw in text_lower:
                            return True, text
            except Exception:
                continue

        # 2. Kiểm tra modal hoặc dialog cảnh báo giới hạn
        dialogs = page.locator('[role="dialog"], .modal, [class*="Modal"]')
        if dialogs.count() > 0:
            for i in range(dialogs.count()):
                try:
                    d = dialogs.nth(i)
                    if d.is_visible():
                        text = d.inner_text().strip()
                        text_lower = text.lower()
                        for kw in keywords:
                            if kw in text_lower:
                                return True, text
                except Exception:
                    continue

        # 3. Kiểm tra thông báo đỏ / error / warning text trên trang
        err_elements = page.locator('[class*="error"], [class*="danger"], [class*="warning"]')
        for i in range(min(err_elements.count(), 10)):
            try:
                e = err_elements.nth(i)
                if e.is_visible():
                    t = e.inner_text().strip()
                    for kw in keywords:
                        if kw in t.lower():
                            return True, t
            except Exception:
                continue

    except Exception:
        pass

    return False, None

def apply_job(page, job, dry_run=False):
    url = job.get("url")
    title = job.get("title", "")
    job_id = job.get("id") or str(int(time.time()))

    print(f"\n🎯 BẮT ĐẦU XỬ LÝ VIETNAMWORKS: {title}")
    print(f"   URL: {url}")

    try:
        resp = page.goto(url, wait_until="domcontentloaded", timeout=35000)
        page.wait_for_timeout(2500)
        handle_experience_modal(page)

        current_url = page.url
        if "viec-lam" not in current_url and "-jv" not in current_url:
            print(f"⚠️ Việc làm đã bị chuyển hướng hoặc đóng: {current_url}")
            return {"status": "EXPIRED", "submitted": False, "reason": "Redirected"}

        # Look for Apply Button
        apply_btn = page.locator('button:has-text("Nộp đơn")')
        if apply_btn.count() == 0:
            # Check if already applied
            applied_badge = page.locator('button:has-text("Đã nộp đơn"), button:has-text("Đã ứng tuyển"), button[disabled]:has-text("Nộp đơn")')
            if applied_badge.count() > 0 or page.locator(':text-matches("Đã ứng tuyển|Đã nộp đơn")').count() > 0:
                print("ℹ️ Việc làm này ĐÃ ỨNG TUYỂN trước đó.")
                return {"status": "ALREADY_APPLIED", "submitted": True}

            print("⚠️ Không tìm thấy nút 'Nộp đơn' (có thể việc làm đã hết hạn).")
            # Save error snapshot
            err_shot = os.path.join(ERRORS_DIR, f"error_no_btn_{job_id}.png")
            page.screenshot(path=err_shot)
            return {"status": "NO_BUTTON", "submitted": False, "screenshot": err_shot}

        print("🚀 Nhấn nút 'Nộp đơn'...")
        apply_btn.first.click(timeout=8000)
        page.wait_for_timeout(2000)

        # Check if daily limit was triggered right after clicking apply
        is_limit, limit_msg = check_daily_limit(page)
        if is_limit:
            print(f"🛑 PHÁT HIỆN ĐẠT GIỚI HẠN NỘP HỒ SƠ TRONG NGÀY: {limit_msg}")
            limit_shot = os.path.join(ERRORS_DIR, f"daily_limit_{job_id}.png")
            try:
                page.screenshot(path=limit_shot)
            except Exception:
                pass
            return {"status": "DAILY_LIMIT_REACHED", "submitted": False, "reason": limit_msg, "proof": limit_shot}

        # Check AI Upsell Modal: "Bạn có muốn tối ưu lợi thế cạnh tranh trước khi ứng tuyển?"
        ai_btn = page.locator('button:has-text("Tiếp tục ứng tuyển")')
        if ai_btn.count() > 0 and ai_btn.first.is_visible():
            print("✨ Vượt qua Popup AI: Nhấn 'Tiếp tục ứng tuyển'...")
            ai_btn.first.click(timeout=5000)
            page.wait_for_timeout(2500)

        # Wait for actual modal: "Ứng tuyển công việc"
        dialog = page.locator('div:has-text("Ứng tuyển công việc"), [role="dialog"]')
        page.wait_for_timeout(1500)

        # Check privacy policy checkbox if present
        try:
            privacy_chk = page.locator('input[type="checkbox"], label:has-text("Tôi đồng ý với Quy định bảo mật")')
            if privacy_chk.count() > 0:
                chk = privacy_chk.first
                try:
                    if not chk.is_checked():
                        chk.click()
                except Exception:
                    chk.click()
                page.wait_for_timeout(500)
        except Exception:
            pass

        proof_path = os.path.join(SCRIPT_DIR, f"apply_proof_vnw_{job_id}.png")

        if dry_run:
            print("🧪 [DRY-RUN] Chụp ảnh xác thực form sẵn sàng (Không bấm nộp thật)...")
            page.screenshot(path=proof_path)
            # Close modal
            close_btn = page.locator('button[aria-label="Close"], button.close, [class*="Modal"] button:has-text("✕")')
            if close_btn.count() > 0:
                close_btn.first.click()
            return {"status": "DRY_RUN_READY", "submitted": False, "proof": proof_path}

        # Real Application Submit
        submit_btn = page.locator('[role="dialog"] button:has-text("Ứng tuyển"), .modal button:has-text("Ứng tuyển"), button.btn-primary:has-text("Ứng tuyển")')
        if submit_btn.count() > 0 and submit_btn.first.is_visible():
            print("📤 Bấm nút 'Ứng tuyển' (Nộp đơn thật)...")
            submit_btn.first.click(timeout=8000)
            page.wait_for_timeout(4000)

            # Check if daily limit was triggered upon submission
            is_limit, limit_msg = check_daily_limit(page)
            if is_limit:
                print(f"🛑 PHÁT HIỆN ĐẠT GIỚI HẠN NỘP HỒ SƠ TRONG NGÀY (SAU KHI BẤM NỘP): {limit_msg}")
                limit_shot = os.path.join(ERRORS_DIR, f"daily_limit_{job_id}.png")
                try:
                    page.screenshot(path=limit_shot)
                except Exception:
                    pass
                return {"status": "DAILY_LIMIT_REACHED", "submitted": False, "reason": limit_msg, "proof": limit_shot}

            page.screenshot(path=proof_path)
            print(f"📸 Đã lưu ảnh kết quả nộp: {proof_path}")
            return {"status": "SUBMITTED", "submitted": True, "proof": proof_path}
        else:
            print("⚠️ Không tìm thấy nút xác nhận nộp trong modal.")
            err_shot = os.path.join(ERRORS_DIR, f"error_no_submit_{job_id}.png")
            page.screenshot(path=err_shot)
            return {"status": "MODAL_ERROR", "submitted": False, "screenshot": err_shot}

    except Exception as e:
        print(f"❌ Lỗi khi xử lý việc làm {title}: {e}")
        err_shot = os.path.join(ERRORS_DIR, f"error_exception_{job_id}.png")
        try:
            page.screenshot(path=err_shot)
        except Exception:
            pass
        return {"status": "ERROR", "submitted": False, "error": str(e)}

def run_applier(max_applies=MAX_APPLIES_DEFAULT, dry_run=DRY_RUN_DEFAULT):
    print(f"\n================ BẮT ĐẦU VNW APPLIER: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ================")
    print(f"⚙️ Cấu hình: MAX_APPLIES = {max_applies} | DRY_RUN = {dry_run}")

    # Load extracted jobs
    if not os.path.exists(EXTRACTED_HISTORY_FILE):
        print("❌ Chưa có file extracted_jobs_history.json. Vui lòng chạy vnw_crawler.py trước.")
        return 0

    with open(EXTRACTED_HISTORY_FILE, "r", encoding="utf-8") as f:
        extracted_jobs = json.load(f)

    applied_dict = load_applied_history()
    print(f"📦 Tổng việc đã quét: {len(extracted_jobs)} | Đã nộp trong lịch sử: {len(applied_dict)}")

    # Filter unapplied jobs
    unapplied_jobs = [j for j in extracted_jobs if j.get("url") not in applied_dict]
    print(f"🎯 Số việc làm CHƯA NỘP còn lại: {len(unapplied_jobs)}")

    if not unapplied_jobs:
        print("🎉 Bạn đã nộp toàn bộ việc làm hiện có trên VietnamWorks! Không có việc mới.")
        return 0

    proxy_cfg = get_proxy_config()
    raw_cookies = load_cookies()
    formatted_cookies = format_cookies_for_playwright(raw_cookies)

    jobs_to_process = unapplied_jobs[:max_applies]
    applied_count = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            proxy=proxy_cfg
        )
        context = browser.new_context(
            viewport={"width": 1366, "height": 768},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            extra_http_headers={"referer": "https://www.vietnamworks.com/"}
        )
        if formatted_cookies:
            context.add_cookies(formatted_cookies)

        page = context.new_page()

        # Check Login & Sync Portal History
        verify_and_ensure_login(page)
        sync_vnw_applied_history(page, applied_dict)

        # Re-filter in case sync found some applied
        jobs_to_process = [j for j in jobs_to_process if j.get("url") not in applied_dict]
        print(f"📋 Danh sách nộp sau khi đồng bộ: {len(jobs_to_process)} việc làm.")

        for idx, job in enumerate(jobs_to_process, 1):
            print(f"\n[{idx}/{len(jobs_to_process)}] ----------------------------------------")
            res = apply_job(page, job, dry_run=dry_run)

            url = job.get("url")
            status = res.get("status")

            if status in ["SUBMITTED", "ALREADY_APPLIED", "DRY_RUN_READY"]:
                applied_dict[url] = {
                    "id": job.get("id"),
                    "title": job.get("title"),
                    "company": job.get("company"),
                    "salary": job.get("salary"),
                    "url": url,
                    "applied_at": datetime.now().isoformat(),
                    "status": status,
                    "proof": res.get("proof", "")
                }
                save_applied_history(applied_dict)
                applied_count += 1
            else:
                # Log error
                err_info = {
                    "job": job,
                    "result": res,
                    "timestamp": datetime.now().isoformat()
                }
                err_file = os.path.join(ERRORS_DIR, f"error_{job.get('id', 'unknown')}.json")
                try:
                    with open(err_file, "w", encoding="utf-8") as f:
                        json.dump(err_info, f, ensure_ascii=False, indent=2)
                except Exception:
                    pass

                # If VietnamWorks reached daily application limit, skip the rest of the day
                if status == "DAILY_LIMIT_REACHED":
                    print("\n" + "🛑" * 38)
                    print("🛑 VIETNAMWORKS: ĐÃ ĐẠT GIỚI HẠN NỘP HỒ SƠ TRONG NGÀY (DAILY LIMIT)!")
                    print(f"🛑 Chi tiết thông báo: {res.get('reason')}")
                    print("🛑 Tự động dừng ca nộp hôm nay và bỏ qua các công việc còn lại.")
                    print("🛑" * 38 + "\n")
                    break

            time.sleep(2)

        browser.close()

    print(f"\n================ HOÀN THÀNH CA NỘP ĐƠN VIETNAMWORKS ================")
    print(f"✅ Đã xử lý thành công: {applied_count} việc làm")
    print(f"📊 Tổng số việc làm đã nộp tích lũy: {len(applied_dict)}")
    print(f"=====================================================================")
    return applied_count

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--max", type=int, default=MAX_APPLIES_DEFAULT)
    parser.add_argument("--dry-run", action="store_true", default=DRY_RUN_DEFAULT)
    args = parser.parse_args()

    run_applier(max_applies=args.max, dry_run=args.dry_run)
