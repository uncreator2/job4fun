import os
import sys
import json
import time
import re
from datetime import datetime
from playwright.sync_api import sync_playwright

# Setup paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(SCRIPT_DIR)
SHARED_DIR = os.path.join(PARENT_DIR, "shared")

for p in [SCRIPT_DIR, SHARED_DIR, PARENT_DIR]:
    if os.path.exists(p) and p not in sys.path:
        sys.path.append(p)

try:
    from proxy_utils import get_proxy_config
except ImportError:
    def get_proxy_config():
        return None

try:
    from playwright_stealth import Stealth
except ImportError:
    Stealth = None

try:
    from v24h_filter import is_target_management_job
except ImportError:
    from vieclam24h.v24h_filter import is_target_management_job

EXTRACTED_HISTORY_FILE = os.path.join(SCRIPT_DIR, "extracted_jobs_history.json")
EXTRACTED_HISTORY_TXT = os.path.join(SCRIPT_DIR, "extracted_jobs_history.txt")
APPLIED_HISTORY_FILE = os.path.join(SCRIPT_DIR, "applied_jobs_history.json")
APPLIED_HISTORY_TXT = os.path.join(SCRIPT_DIR, "applied_jobs_history.txt")
PROOFS_DIR = os.path.join(SCRIPT_DIR, "proofs")
ERRORS_DIR = os.path.join(SCRIPT_DIR, "errors")
os.makedirs(PROOFS_DIR, exist_ok=True)
os.makedirs(ERRORS_DIR, exist_ok=True)

APPLIED_PORTAL_URL = "https://vieclam24h.vn/ntv-trang-quan-tri-viec-lam-da-ung-tuyen.html"
DEFAULT_CV_NAME = "N_P_H_H_Quantum_Operations_Dossier_VI.pdf"

def safe_goto(page, url, wait_until="domcontentloaded", timeout=40000, max_retries=3):
    last_err = None
    for attempt in range(1, max_retries + 1):
        try:
            return page.goto(url, wait_until=wait_until, timeout=timeout)
        except Exception as e:
            last_err = e
            err_str = str(e)
            if any(k in err_str for k in ["ERR_CONNECTION_RESET", "ERR_TIMED_OUT", "ERR_NETWORK_CHANGED", "Timeout", "net::"]):
                print(f"⚠️ Gián đoạn mạng ({attempt}/{max_retries}) khi tải {url}: {e}")
                time.sleep(2 * attempt)
            else:
                raise e
    raise last_err

def load_cookies():
    env_cookies = os.environ.get("V24H_COOKIES", "").strip()
    if env_cookies:
        try:
            return json.loads(env_cookies)
        except Exception as e:
            print(f"⚠️ Không giải mã được V24H_COOKIES từ biến môi trường: {e}")

    preferred = os.path.join(SCRIPT_DIR, "vieclam24h_cookies.json")
    if os.path.exists(preferred):
        try:
            with open(preferred, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    for fname in sorted(os.listdir(SCRIPT_DIR)):
        if fname.endswith(".json") and "vieclam24h" in fname.lower() and "history" not in fname.lower():
            try:
                with open(os.path.join(SCRIPT_DIR, fname), "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
    return []

def format_cookies(raw_cookies):
    cookies = []
    if isinstance(raw_cookies, dict):
        if "cookies" in raw_cookies and isinstance(raw_cookies["cookies"], list):
            raw_cookies = raw_cookies["cookies"]
        else:
            raw_cookies = [raw_cookies]
    elif not isinstance(raw_cookies, list):
        return []

    for c in raw_cookies:
        if not isinstance(c, dict):
            continue
        name = c.get("name")
        value = c.get("value")
        if not name or value is None:
            continue
        domain = c.get("domain", ".vieclam24h.vn")
        cookie = {
            "name": str(name),
            "value": str(value),
            "domain": domain,
            "path": c.get("path", "/"),
        }
        if "secure" in c and isinstance(c["secure"], bool):
            cookie["secure"] = c["secure"]
        if "httpOnly" in c and isinstance(c["httpOnly"], bool):
            cookie["httpOnly"] = c["httpOnly"]
        cookies.append(cookie)
    return cookies

def load_credentials():
    env_data = os.environ.get("V24H_ENV", "").strip()
    if env_data:
        lines = [l.strip() for l in env_data.split("\n") if l.strip()]
        if len(lines) >= 2:
            return lines[0], lines[1]

    env_path = os.path.join(SCRIPT_DIR, "env.txt")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f if l.strip()]
        if len(lines) >= 2:
            return lines[0], lines[1]

    return None, None

def load_applied_history():
    history = {}
    if os.path.exists(APPLIED_HISTORY_FILE):
        try:
            with open(APPLIED_HISTORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    for item in data:
                        u = item.get("url")
                        if u:
                            history[u] = item
                elif isinstance(data, dict):
                    history = data
        except Exception as e:
            print(f"⚠️ Lỗi đọc applied history JSON: {e}")

    if os.path.exists(APPLIED_HISTORY_TXT):
        try:
            with open(APPLIED_HISTORY_TXT, "r", encoding="utf-8") as f:
                for line in f:
                    u = line.strip()
                    if u and u not in history:
                        history[u] = {"url": u, "applied_at": "unknown"}
        except Exception as e:
            print(f"⚠️ Lỗi đọc applied history TXT: {e}")

    return history

def save_applied_history(history_dict):
    try:
        with open(APPLIED_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(list(history_dict.values()), f, ensure_ascii=False, indent=2)

        with open(APPLIED_HISTORY_TXT, "w", encoding="utf-8") as f:
            for u in sorted(history_dict.keys()):
                f.write(f"{u}\n")
    except Exception as e:
        print(f"❌ Lỗi ghi applied history: {e}")

def check_login_status(page):
    try:
        header = page.locator("header")
        if header.count() == 0:
            return False

        # If header has login button visible, definitely not logged in
        login_btn = header.locator(":text('Đăng ký/Đăng nhập'), :text('Đăng nhập')")
        if login_btn.count() > 0:
            for i in range(login_btn.count()):
                if login_btn.nth(i).is_visible():
                    return False

        # Check presence of user identifier in header
        header_text = header.inner_text()
        if "\nHa\n" in header_text or "Hoang Ha" in header_text or "Đăng xuất" in header_text or header.locator('[data-component-name="UserHeaderDropdown"], .svicon-user').count() > 0:
            return True
    except Exception:
        pass
    return False

def perform_form_login(page, context):
    email, password = load_credentials()
    if not email or not password:
        print("⚠️ Không có thông tin tài khoản (V24H_ENV hoặc env.txt) để thực hiện đăng nhập lại.")
        return False

    print(f"🔐 ĐANG ĐĂNG NHẬP LẠI VIECLAM24H (Email: {email})...")
    try:
        safe_goto(page, "https://vieclam24h.vn/", wait_until="domcontentloaded", timeout=35000)
        page.wait_for_timeout(2000)

        # 1. Click Login button in header
        login_btn = page.locator("header").locator(":text('Đăng ký/Đăng nhập'), :text('Đăng nhập')").first
        if login_btn.count() > 0 and login_btn.is_visible():
            login_btn.click()
            page.wait_for_timeout(2000)

        # 2. Click "Đăng nhập bằng Email" tab in modal
        email_tab = page.locator(":text('Đăng nhập bằng Email')").first
        if email_tab.count() > 0 and email_tab.is_visible():
            email_tab.click()
            page.wait_for_timeout(1500)

        # 3. Fill email in modal (specifically seeker_email)
        email_input = page.locator("[role=dialog] input[name='seeker_email'], input[name='seeker_email']").first
        if email_input.count() > 0 and email_input.is_visible():
            email_input.fill(email)
            page.wait_for_timeout(500)

            next_btn = page.locator("[role=dialog] button:has-text('Tiếp tục'), form button:has-text('Tiếp tục')").first
            if next_btn.count() > 0:
                next_btn.click()
                page.wait_for_timeout(2500)

        # 4. Click "Đăng nhập bằng mật khẩu" on OTP screen
        pwd_switch = page.locator(":text('Đăng nhập bằng mật khẩu')").first
        if pwd_switch.count() > 0 and pwd_switch.is_visible():
            pwd_switch.click()
            page.wait_for_timeout(1500)

        # 5. Fill password in modal
        pwd_input = page.locator("[role=dialog] input[type='password'], input[name='password']").first
        if pwd_input.count() > 0 and pwd_input.is_visible():
            pwd_input.fill(password)
            page.wait_for_timeout(500)

            submit_btn = page.locator("[role=dialog] button:has-text('Tiếp tục'), [role=dialog] button[type='submit']").first
            if submit_btn.count() > 0:
                submit_btn.click()
                page.wait_for_timeout(4000)

        if check_login_status(page):
            print("🎉 Đăng nhập biểu mẫu Vieclam24h THÀNH CÔNG!")
            # Save fresh cookies
            fresh_cookies = context.cookies()
            try:
                with open(os.path.join(SCRIPT_DIR, "vieclam24h_cookies.json"), "w", encoding="utf-8") as f:
                    json.dump(fresh_cookies, f, indent=2, ensure_ascii=False)
            except Exception:
                pass
            return True
        else:
            print("❌ Đăng nhập biểu mẫu không thành công.")
            return False
    except Exception as e:
        print(f"❌ Ngoại lệ khi đăng nhập biểu mẫu: {e}")
        return False

def sync_portal_applied_history(page, applied_dict):
    print(f"\n🔄 ĐANG ĐỒNG BỘ LỊCH SỬ ỨNG TUYỂN TỪ CỔNG VIECLAM24H...")
    synced_count = 0
    try:
        safe_goto(page, APPLIED_PORTAL_URL, wait_until="domcontentloaded", timeout=40000)
        try:
            page.wait_for_selector('a[href*="id"]', timeout=8000)
        except Exception:
            pass
        page.wait_for_timeout(2000)

        portal_jobs = page.evaluate("""() => {
            const anchors = Array.from(document.querySelectorAll('a')).filter(a => /id\\d+\\.html/.test(a.href));
            const seen = new Set();
            const list = [];
            for (const a of anchors) {
                const u = a.href.split('?')[0];
                if (!seen.has(u)) {
                    seen.add(u);
                    const m = u.match(/id(\\d+)\\.html/);
                    list.push({
                        url: u,
                        id: m ? m[1] : "",
                        title: a.innerText.trim().split('\\n')[0]
                    });
                }
            }
            return list;
        }""")

        for j in portal_jobs:
            u = j.get("url")
            if u and u not in applied_dict:
                applied_dict[u] = {
                    "url": u,
                    "id": j.get("id"),
                    "title": j.get("title"),
                    "applied_at": "portal_sync",
                    "status": "APPLIED_PORTAL"
                }
                synced_count += 1

        print(f"✅ Đã tìm thấy {len(portal_jobs)} việc làm đã nộp trên cổng (+{synced_count} mới).")
        if synced_count > 0:
            save_applied_history(applied_dict)
    except Exception as e:
        print(f"⚠️ Đồng bộ lịch sử tuyển dụng gặp lỗi: {e}")

def check_daily_limit(page):
    """
    Kiểm tra xem Vieclam24h có hiển thị cảnh báo hết lượt nộp / đạt giới hạn ngày hay không.
    """
    keywords = [
        "hết lượt", "đạt giới hạn", "vượt quá số lần", "vượt quá số lượt",
        "giới hạn nộp", "giới hạn ứng tuyển", "ứng tuyển trong ngày",
        "tối đa trong ngày", "lượt nộp đơn trong ngày",
        "application limit", "daily limit", "reached limit"
    ]
    try:
        # Check toast / alerts / modals
        elements = page.locator('[role="alert"], [class*="toast"], [class*="Toast"], [class*="notification"], .alert, [role="dialog"], [class*="modal" i]')
        count = elements.count()
        for i in range(min(count, 8)):
            try:
                el = elements.nth(i)
                if el.is_visible():
                    text = el.inner_text().strip()
                    for kw in keywords:
                        if kw in text.lower():
                            return True, text
            except Exception:
                continue

        # Check error text spans
        err_spans = page.locator('span[class*="error"], p[class*="error"], div[class*="error"]')
        for i in range(min(err_spans.count(), 6)):
            try:
                e = err_spans.nth(i)
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

def apply_single_job(page, job, dry_run=False):
    url = job.get("url")
    title = job.get("title", "")
    job_id = job.get("id") or str(int(time.time()))

    print(f"\n🎯 XỬ LÝ VIỆC LÀM: {title}")
    print(f"   URL: {url}")

    try:
        safe_goto(page, url, wait_until="domcontentloaded", timeout=35000)
        page.wait_for_timeout(2500)

        # Check if already applied
        applied_badge = page.locator('button:has-text("Đã ứng tuyển"), button:has-text("Đã nộp hồ sơ"), button[disabled]:has-text("Đã")')
        if applied_badge.count() > 0 and applied_badge.first.is_visible():
            print("ℹ️ Việc làm này ĐÃ ỨNG TUYỂN trước đó trên trang.")
            return {"status": "ALREADY_APPLIED", "submitted": True}

        # Check login status before applying
        if not check_login_status(page):
            print("⚠️ Phát hiện tài khoản chưa đăng nhập hoặc phiên hết hạn. Đang đăng nhập lại...")
            perform_form_login(page, page.context)
            safe_goto(page, url, wait_until="domcontentloaded", timeout=35000)
            page.wait_for_timeout(2500)

        # Ensure page is interactive
        page.wait_for_timeout(2000)

        # Look for Apply Button
        apply_btn = page.locator('button:has-text("Ứng tuyển ngay"), button:has-text("Nộp hồ sơ ngay")').first
        if apply_btn.count() == 0 or not apply_btn.is_visible():
            print("⚠️ Không tìm thấy nút 'Ứng tuyển ngay' (việc làm có thể đã đóng hoặc hết hạn).")
            err_shot = os.path.join(ERRORS_DIR, f"v24h_no_btn_{job_id}.png")
            try:
                page.screenshot(path=err_shot)
            except Exception:
                pass
            return {"status": "NO_BUTTON", "submitted": False, "proof": err_shot}

        # Click apply button with retry loop to guarantee React hydration has completed
        modal_opened = False
        for attempt in range(1, 4):
            print(f"👉 Bấm nút 'Ứng tuyển ngay' (lần {attempt})...")
            try:
                apply_btn.scroll_into_view_if_needed()
                apply_btn.click(timeout=5000)
                page.wait_for_timeout(1200)
            except Exception as e:
                print(f"⚠️ Lỗi click nút: {e}")

            # Check immediate daily limit
            is_limit, limit_msg = check_daily_limit(page)
            if is_limit:
                print(f"🛑 [DAILY_LIMIT_REACHED] ĐẠT GIỚI HẠN ỨNG TUYỂN TRONG NGÀY: {limit_msg}")
                limit_shot = os.path.join(ERRORS_DIR, f"v24h_daily_limit_{job_id}.png")
                page.screenshot(path=limit_shot)
                return {"status": "DAILY_LIMIT_REACHED", "submitted": False, "reason": limit_msg, "proof": limit_shot}

            # Check if login modal opened instead of application modal
            login_modal = page.locator('[role="dialog"]:has-text("Đăng nhập"), [role="dialog"]:has-text("Người tìm việc"), [role="dialog"]:has-text("Đăng ký")')
            if login_modal.count() > 0 and login_modal.first.is_visible():
                print("⚠️ Modal Đăng nhập xuất hiện khi bấm Ứng tuyển! Tiến hành đăng nhập lại...")
                perform_form_login(page, page.context)
                safe_goto(page, url, wait_until="domcontentloaded", timeout=35000)
                page.wait_for_timeout(2500)
                apply_btn = page.locator('button:has-text("Ứng tuyển ngay"), button:has-text("Nộp hồ sơ ngay")').first
                if apply_btn.count() > 0 and apply_btn.is_visible():
                    apply_btn.click(timeout=5000)
                    page.wait_for_timeout(2000)

            # Check if intermediate confirmation popup appears: "Việc làm này đang chờ kiểm duyệt"
            confirm_btn = page.locator('button:has-text("Tiếp tục nộp")')
            if confirm_btn.count() > 0 and confirm_btn.first.is_visible():
                print("⚠️ Phát hiện popup cảnh báo 'Việc làm đang chờ kiểm duyệt': Bấm 'Tiếp tục nộp'...")
                confirm_btn.first.click(timeout=5000)
                page.wait_for_timeout(2500)
                modal_opened = True
                break

            # Wait for application modal dialog or submit button
            try:
                page.wait_for_selector('div:has-text("Hồ sơ ứng tuyển"), button:has-text("Nộp hồ sơ ngay")', timeout=4000)
                modal_opened = True
                break
            except Exception:
                print("⏳ Modal chưa mở, đợi thêm 2s để hydration hoàn tất rồi thử lại...")
                page.wait_for_timeout(2000)

        if not modal_opened:
            print("❌ Không mở được modal ứng tuyển sau 3 lần thử!")
            err_shot = os.path.join(ERRORS_DIR, f"v24h_modal_failed_{job_id}.png")
            try:
                page.screenshot(path=err_shot)
            except Exception:
                pass
            return {"status": "MODAL_FAILED", "submitted": False, "proof": err_shot}

        page.wait_for_timeout(1000)

        # Check again if intermediate confirmation popup appears: "Việc làm này đang chờ kiểm duyệt"
        confirm_btn = page.locator('button:has-text("Tiếp tục nộp")')
        if confirm_btn.count() > 0 and confirm_btn.first.is_visible():
            print("⚠️ Phát hiện popup cảnh báo 'Việc làm đang chờ kiểm duyệt': Bấm 'Tiếp tục nộp'...")
            confirm_btn.first.click(timeout=5000)
            page.wait_for_timeout(2500)

        # Modal interaction: Wait for CV and submit button hydration
        print("⏳ Đang chờ modal tải hoàn tất danh sách CV và nút nộp...")
        try:
            page.wait_for_selector('button:has-text("Nộp hồ sơ ngay")', timeout=10000, state="attached")
        except Exception:
            # Fallback: click CV tab if required
            cv_option = page.locator('[data-test-id="apply-method-selector__option-cv"], div:has-text("Ứng tuyển với CV")').first
            if cv_option.count() > 0 and cv_option.is_visible():
                try:
                    cv_option.click()
                    page.wait_for_timeout(1500)
                    page.wait_for_selector('button:has-text("Nộp hồ sơ ngay")', timeout=6000, state="attached")
                except Exception:
                    pass

        # Verify CV presence: The file name in DOM is split across spans, so check container with :has-text
        cv_item = page.locator('[data-test-id="unified-apply__cv-item"]:has-text("Quantum_Operations"), [data-test-id="unified-apply__cv-item"]:has-text("Dossier_VI"), :text("Quantum_Operations")')
        if cv_item.count() > 0:
            print(f"📄 Hồ sơ ứng tuyển mặc định đã sẵn sàng: {DEFAULT_CV_NAME}")
        else:
            print(f"ℹ️ Không thấy nhãn file {DEFAULT_CV_NAME}, tiếp tục với CV mặc định của hệ thống.")

        # Toggle off "Nhận thông báo việc làm tương tự" if present
        try:
            switch = page.locator('[data-test-id="common__switch"]').first
            if switch.count() > 0 and switch.is_visible():
                classes = switch.get_attribute("class") or ""
                if "bg-primary" in classes:
                    switch.click()
                    page.wait_for_timeout(500)
        except Exception:
            pass

        # Verify submit button is ready and scroll into view
        modal_submit = page.locator('button:has-text("Nộp hồ sơ ngay")').last
        if modal_submit.count() > 0:
            try:
                modal_submit.scroll_into_view_if_needed()
                page.wait_for_timeout(800)
            except Exception:
                pass

        if modal_submit.count() == 0 or not modal_submit.is_visible():
            print("❌ Không tìm thấy nút 'Nộp hồ sơ ngay' trong modal sau khi chờ hydration!")
            err_shot = os.path.join(ERRORS_DIR, f"v24h_no_submit_btn_{job_id}.png")
            try:
                page.screenshot(path=err_shot)
            except Exception:
                pass
            return {"status": "NO_SUBMIT_BTN", "submitted": False, "proof": err_shot}

        if dry_run:
            dryrun_shot = os.path.join(PROOFS_DIR, f"dryrun_proof_v24h_{job_id}.png")
            page.screenshot(path=dryrun_shot)
            print(f"📸 [DRY-RUN] Lưu ảnh minh chứng modal: {dryrun_shot}")

            # Close modal
            close_btn = page.locator('.svicon-close, [data-test-id*="close"], button:has([class*="close"]), i[class*="close"]').first
            if close_btn.count() > 0 and close_btn.is_visible():
                close_btn.click()
                page.wait_for_timeout(1000)

            return {"status": "DRY_RUN_SUCCESS", "submitted": True, "proof": dryrun_shot}

        # Real Application Submission
        print("🚀 ĐANG NỘP HỒ SƠ THỰC TẾ: Bấm 'Nộp hồ sơ ngay'...")
        try:
            modal_submit.scroll_into_view_if_needed()
            modal_submit.click(timeout=8000)
        except Exception as click_err:
            print(f"⚠️ Standard click bị chặn, thử fallback evaluate click: {click_err}")
            page.evaluate("""() => {
                const btn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Nộp hồ sơ ngay'));
                if (btn) btn.click();
            }""")

        page.wait_for_timeout(3500)

        # Post-submission check for daily limit
        is_limit, limit_msg = check_daily_limit(page)
        if is_limit:
            print(f"🛑 [DAILY_LIMIT_REACHED] Sau khi nộp, phát hiện hết lượt: {limit_msg}")
            limit_shot = os.path.join(ERRORS_DIR, f"v24h_daily_limit_{job_id}.png")
            page.screenshot(path=limit_shot)
            return {"status": "DAILY_LIMIT_REACHED", "submitted": False, "reason": limit_msg, "proof": limit_shot}

        # Dismiss success modal/toast if open so it does not interfere with future page state
        try:
            close_btn = page.locator('.svicon-close, [data-test-id*="close"], button:has-text("Đóng"), button:has-text("Hoàn tất")').first
            if close_btn.count() > 0 and close_btn.is_visible():
                close_btn.click()
                page.wait_for_timeout(1000)
        except Exception:
            pass

        # Save success proof screenshot
        proof_shot = os.path.join(PROOFS_DIR, f"apply_proof_v24h_{job_id}.png")
        page.screenshot(path=proof_shot)
        print(f"📸 Lưu ảnh minh chứng nộp thành công: {proof_shot}")

        return {"status": "APPLIED_SUCCESS", "submitted": True, "proof": proof_shot}

    except Exception as e:
        print(f"❌ Lỗi khi xử lý nộp việc làm {job_id}: {e}")
        err_shot = os.path.join(ERRORS_DIR, f"v24h_exception_{job_id}.png")
        try:
            page.screenshot(path=err_shot)
        except Exception:
            pass
        return {"status": "ERROR", "submitted": False, "reason": str(e), "proof": err_shot}

def run_applier(max_applies=20, dry_run=False):
    print(f"\n================ BẮT ĐẦU VIECLAM24H APPLIER: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ================")
    print(f"⚙️ Chế độ: {'DRY-RUN (Thử nghiệm an toàn)' if dry_run else 'THỰC TẾ (Nộp hồ sơ thật)'}")
    print(f"🎯 Giới hạn nộp phiên này: {max_applies} việc làm")

    applied_dict = load_applied_history()
    print(f"📚 Sổ cái lịch sử đã nộp: {len(applied_dict)} việc làm.")

    # Load extracted jobs to apply
    if not os.path.exists(EXTRACTED_HISTORY_FILE):
        print(f"⚠️ Chưa có file việc làm đã quét: {EXTRACTED_HISTORY_FILE}. Vui lòng chạy crawler trước.")
        return 0

    with open(EXTRACTED_HISTORY_FILE, "r", encoding="utf-8") as f:
        all_crawled_jobs = json.load(f)

    # Filter unapplied jobs and strictly enforce management roles
    candidate_jobs = []
    for j in all_crawled_jobs:
        u = j.get("url")
        t = j.get("title", "")
        if u and u not in applied_dict:
            if is_target_management_job(t, u):
                candidate_jobs.append(j)

    print(f"📊 Tổng số việc làm đã quét: {len(all_crawled_jobs)}")
    print(f"🆕 Số việc làm QUẢN LÝ CHƯA ỨNG TUYỂN chờ nộp: {len(candidate_jobs)}")

    if not candidate_jobs:
        print("✅ Tất cả việc làm đã được nộp hoặc không còn việc mới. Hoàn tất!")
        return 0

    proxy_cfg = get_proxy_config()
    raw_cookies = load_cookies()

    applied_count = 0
    daily_limit_hit = False

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, proxy=proxy_cfg)
            context = browser.new_context(
                viewport={"width": 1440, "height": 900},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                locale="vi-VN"
            )

            if raw_cookies:
                try:
                    formatted = format_cookies(raw_cookies)
                    if formatted:
                        context.add_cookies(formatted)
                except Exception as e:
                    print(f"⚠️ Không thể nạp cookies vào context: {e}")

            page = context.new_page()
            if Stealth:
                try:
                    Stealth().apply_stealth_sync(page)
                except Exception:
                    pass

            # Verify login
            print("🌐 Kiểm tra trạng thái đăng nhập trên Vieclam24h...")
            is_logged_in = False
            try:
                safe_goto(page, "https://vieclam24h.vn/", wait_until="domcontentloaded", timeout=40000)
                page.wait_for_timeout(2500)
                is_logged_in = check_login_status(page)
            except Exception as e:
                print(f"⚠️ Kiểm tra đăng nhập bằng cookie gặp lỗi kết nối: {e}")

            if not is_logged_in:
                print("⚠️ Chưa đăng nhập hoặc cookie hết hạn. Tiến hành fallback đăng nhập biểu mẫu...")
                try:
                    is_logged_in = perform_form_login(page, context)
                except Exception as e:
                    print(f"⚠️ Đăng nhập biểu mẫu gặp lỗi: {e}")

            if not is_logged_in:
                print("❌ Không thể xác thực tài khoản Vieclam24h. Dừng applier.")
                browser.close()
                return 0

            print("✅ Xác thực tài khoản Vieclam24h thành công!")

            # Sync portal history
            sync_portal_applied_history(page, applied_dict)

            # Refresh candidate list after sync and enforce management roles
            candidate_jobs = [
                j for j in candidate_jobs
                if j.get("url") not in applied_dict and is_target_management_job(j.get("title", ""), j.get("url", ""))
            ]
            max_eval_attempts = min(len(candidate_jobs), max_applies * 2)
            eval_candidates = candidate_jobs[:max_eval_attempts]
            print(f"📋 Danh sách việc làm mục tiêu cần nộp: {len(candidate_jobs)} (Tối đa duyệt ca này: {len(eval_candidates)}, Chỉ tiêu nộp: {max_applies})")

            consecutive_errors = 0
            MAX_CONSECUTIVE_ERRORS = 5

            for idx, job in enumerate(eval_candidates, 1):
                if applied_count >= max_applies:
                    print(f"\n🛑 Đã đạt số lượng nộp tối đa theo phiên: {max_applies} việc làm.")
                    break

                if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                    print(f"\n⚠️ NGẮT MẠCH BẢO VỆ: Đã gặp {consecutive_errors} lỗi liên tiếp (modal/submit). Tạm dừng ca nộp để bảo vệ tài nguyên.")
                    break

                print(f"\n[{idx}/{len(eval_candidates)}] (Đã nộp thành công: {applied_count}/{max_applies}) Đang tiến hành:")
                result = apply_single_job(page, job, dry_run=dry_run)

                status = result.get("status")
                u = job.get("url")

                if status == "DAILY_LIMIT_REACHED":
                    print(f"\n🛑 PHÁT HIỆN HẾT HẠN MỨC ỨNG TUYỂN HÔM NAY (DAILY_LIMIT_REACHED).")
                    print(f"Lý do: {result.get('reason')}")
                    daily_limit_hit = True
                    break

                if result.get("submitted"):
                    applied_count += 1
                    consecutive_errors = 0  # Reset on any successful submission or dry-run
                    if status in ["APPLIED_SUCCESS", "ALREADY_APPLIED"]:
                        applied_dict[u] = {
                            "url": u,
                            "id": job.get("id"),
                            "title": job.get("title"),
                            "company": job.get("company"),
                            "salary": job.get("salary"),
                            "location": job.get("location"),
                            "status": status,
                            "applied_at": datetime.now().isoformat(),
                            "proof": result.get("proof")
                        }
                        save_applied_history(applied_dict)
                else:
                    if status in ["NO_SUBMIT_BTN", "MODAL_FAILED", "ERROR"]:
                        consecutive_errors += 1

                # Sleep between applications to avoid anti-spam
                sleep_sec = 4 if not dry_run else 1
                time.sleep(sleep_sec)

            browser.close()

    except Exception as e:
        import traceback
        print(f"❌ LỖI KHÔNG MONG MUỐN TRONG VIECLAM24H APPLIER: {e}")
        traceback.print_exc()

    save_applied_history(applied_dict)

    print(f"\n================ HOÀN TẤT VIECLAM24H APPLIER ================")
    print(f"📊 Đã xử lý nộp thành công: {applied_count} việc làm.")
    print(f"📦 Tổng số việc làm đã nộp trong sổ cái: {len(applied_dict)}")
    if daily_limit_hit:
        print("⚠️ GHI CHÚ: Quá trình dừng do đạt giới hạn ứng tuyển trong ngày của Vieclam24h.")
    print(f"=============================================================\n")

    return applied_count

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Vieclam24h Automated Applier")
    parser.add_argument("--max", type=int, default=20, help="Max jobs to apply in this run")
    parser.add_argument("--dry-run", action="store_true", help="Simulate applying without clicking submit")
    args = parser.parse_args()

    run_applier(max_applies=args.max, dry_run=args.dry_run)
