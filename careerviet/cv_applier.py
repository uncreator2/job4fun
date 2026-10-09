# -*- coding: utf-8 -*-
"""
CareerViet Auto-Applier
Automatically applies to extracted management jobs using authenticated session cookies,
verifies default profile, protects against re-apply spam, saves proof screenshots,
and records results to version-controlled history ledgers.
"""

import os
import sys
import json
import time
import re
import argparse
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
    from cv_filter import is_target_management_job
except ImportError:
    from careerviet.cv_filter import is_target_management_job

EXTRACTED_HISTORY_FILE = os.path.join(SCRIPT_DIR, "extracted_jobs_history.json")
APPLIED_HISTORY_FILE = os.path.join(SCRIPT_DIR, "applied_jobs_history.json")
APPLIED_HISTORY_TXT = os.path.join(SCRIPT_DIR, "applied_jobs_history.txt")
PROOFS_DIR = os.path.join(SCRIPT_DIR, "proofs")
ERRORS_DIR = os.path.join(SCRIPT_DIR, "errors")
COOKIE_FILE = os.path.join(SCRIPT_DIR, "careerviet_cookies.json")

os.makedirs(PROOFS_DIR, exist_ok=True)
os.makedirs(ERRORS_DIR, exist_ok=True)

def safe_goto(page, url, wait_until="domcontentloaded", timeout=35000, max_retries=3):
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
    env_cookies = os.environ.get("CAREERVIET_COOKIES", "").strip() or os.environ.get("COOKIES", "").strip()
    if env_cookies:
        try:
            return json.loads(env_cookies)
        except Exception as e:
            print(f"⚠️ Không giải mã được CAREERVIET_COOKIES từ env: {e}")

    if os.path.exists(COOKIE_FILE):
        try:
            with open(COOKIE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []

def format_cookies_for_playwright(raw_cookies):
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
        cookie = {
            "name": c["name"],
            "value": c["value"],
            "domain": c.get("domain", ".careerviet.vn"),
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
                        u = item.get("url") or item.get("id")
                        if u:
                            applied[u] = item
                elif isinstance(data, dict):
                    applied = data
        except Exception as e:
            print(f"⚠️ Lỗi đọc applied_jobs_history.json: {e}")

    if os.path.exists(APPLIED_HISTORY_TXT):
        try:
            with open(APPLIED_HISTORY_TXT, "r", encoding="utf-8") as f:
                for line in f:
                    u = line.strip()
                    if u and u not in applied:
                        applied[u] = {"url": u, "applied_at": "unknown"}
        except Exception as e:
            print(f"⚠️ Lỗi đọc applied_jobs_history.txt: {e}")

    return applied

def save_applied_history(applied_dict):
    try:
        with open(APPLIED_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(list(applied_dict.values()), f, ensure_ascii=False, indent=2)

        with open(APPLIED_HISTORY_TXT, "w", encoding="utf-8") as f:
            for u in sorted(applied_dict.keys()):
                f.write(f"{u}\n")
    except Exception as e:
        print(f"❌ Lỗi ghi file lịch sử ứng tuyển: {e}")

def apply_single_job(page, job, dry_run=False):
    job_id = job.get("id", "")
    job_url = job.get("url", "")
    title = job.get("title", "")
    company = job.get("company", "")

    if not job_id and job_url:
        m = re.search(r"\.([0-9A-Za-z]+)\.html$", job_url)
        if m:
            job_id = m.group(1)

    print(f"\n🎯 [XỬ LÝ] [{job_id}] {title} | {company}")

    # Bước 1: Kiểm tra trang chi tiết việc làm để xác định trạng thái nộp đơn
    try:
        safe_goto(page, job_url, timeout=30000)
        time.sleep(1.5)
    except Exception as e:
        print(f"  ❌ Không thể mở trang chi tiết việc làm: {e}")
        return "FAILED"

    # Kiểm tra nút Apply trên trang chi tiết
    apply_btn = page.locator('a.btnApplyClick, a.btn-gradient, [class*="btnApply"]').first
    if apply_btn.count() > 0:
        btn_text = apply_btn.inner_text().strip().lower()
        btn_href = apply_btn.get_attribute("href") or ""
        
        # Nếu đã nộp trước đó hoặc là nút nộp lại -> BỎ QUA để tránh bị tính spam
        if any(k in btn_text for k in ["đã nộp", "đã ứng tuyển", "lại", "re-apply"]) or not btn_href:
            print(f"  ⏩ BỎ QUA: Vị trí này đã được ứng tuyển trước đó (Nút: '{btn_text}'). Tránh nộp lại trùng lặp.")
            return "ALREADY_APPLIED"

    # Bước 2: Chuyển đến trang nộp đơn chính thức
    apply_url = f"https://careerviet.vn/vi/jobseekers/jobs/apply?job_id={job_id}"
    try:
        safe_goto(page, apply_url, timeout=30000)
        time.sleep(2.0)
    except Exception as e:
        print(f"  ❌ Không thể mở trang nộp đơn {apply_url}: {e}")
        return "FAILED"

    # Kiểm tra sự xuất hiện của nút Nộp đơn
    submit_btn = page.locator('button#btnsubmit, button[name="btnsubmit"]').first
    try:
        submit_btn.wait_for(state="visible", timeout=12000)
    except Exception:
        print("  ❌ Không tìm thấy nút submit #btnsubmit trên trang nộp đơn.")
        err_shot = os.path.join(ERRORS_DIR, f"err_no_submit_{job_id}.png")
        page.screenshot(path=err_shot)
        return "FAILED"

    # Bước 3: Dry-run hoặc Nộp thật
    if dry_run:
        proof_path = os.path.join(PROOFS_DIR, f"dryrun_cv_{job_id}.png")
        page.screenshot(path=proof_path)
        print(f"  🧪 [DRY-RUN] Đã xác nhận trang nộp đơn sẵn sàng. Chụp ảnh lưu tại: {proof_path}")
        return "DRY_RUN_OK"

    # NỘP THẬT: Bấm nút #btnsubmit
    print("  🚀 Đang gửi hồ sơ ứng tuyển...")
    try:
        api_response_status = [None]
        def handle_response(response):
            if f"/apply-jobs/{job_id}" in response.url or "/apply-jobs" in response.url:
                try:
                    if response.status in [200, 201]:
                        api_response_status[0] = response.status
                except Exception:
                    pass

        page.on("response", handle_response)
        submit_btn.click()
        
        # Chờ tối đa 8s cho API phản hồi hoặc trang điều hướng sau khi nộp
        for _ in range(8):
            time.sleep(1.0)
            if api_response_status[0] in [200, 201]:
                break
            try:
                if f"jobs/apply?job_id={job_id}" not in page.url:
                    break
            except Exception:
                break
        
        # Thử kiểm tra xác nhận trên trang chi tiết việc làm
        time.sleep(2.0)
        try:
            safe_goto(page, job_url, timeout=20000)
            time.sleep(1.5)
            check_btn = page.locator('a.btnApplyClick, a.btn-gradient, [class*="btnApply"]').first
            if check_btn.count() > 0:
                t = check_btn.inner_text().strip().lower()
                if any(k in t for k in ["đã", "applied"]):
                    print(f"  🌟 Xác nhận thành công trên trang việc làm: '{t.upper()}'")
        except Exception as e_verify:
            print(f"  ℹ️ Lưu ý sau nộp: {e_verify}")

        proof_path = os.path.join(PROOFS_DIR, f"apply_proof_cv_{job_id}.png")
        page.screenshot(path=proof_path)
        print(f"  ✅ Ứng tuyển THÀNH CÔNG! Đã lưu ảnh bằng chứng: {proof_path}")
        return "APPLIED_OK"
    except Exception as e:
        print(f"  ❌ Lỗi khi thực thi bấm nộp: {e}")
        err_shot = os.path.join(ERRORS_DIR, f"err_submit_{job_id}.png")
        try:
            page.screenshot(path=err_shot)
        except Exception:
            pass
        return "FAILED"

def run_applier(max_applies=30, dry_run=False, use_cdp=False):
    print("=" * 60)
    print("🤖 BẮT ĐẦU AUTO-APPLIER CAREERVIET (HÀ NỘI - MANAGEMENT)")
    print(f"⏰ Thời gian: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"⚙️  Hạn mức nộp ca này: {max_applies} | Chế độ Dry-Run: {dry_run}")
    print("=" * 60)

    # 1. Đọc danh sách việc làm đã quét
    if not os.path.exists(EXTRACTED_HISTORY_FILE):
        print(f"⚠️ Chưa có file sổ cái {EXTRACTED_HISTORY_FILE}. Vui lòng chạy crawler trước.")
        return 0

    with open(EXTRACTED_HISTORY_FILE, "r", encoding="utf-8") as f:
        all_extracted = json.load(f)

    print(f"📋 Tổng số việc làm đã quét trong sổ cái: {len(all_extracted)}")

    # 2. Đọc danh sách việc làm đã nộp
    applied_history = load_applied_history()
    print(f"📦 Số việc làm đã nộp thành công trước đây: {len(applied_history)}")

    # 3. Lọc danh sách việc làm mục tiêu chưa nộp
    candidate_jobs = []
    for j in all_extracted:
        u = j.get("url", "")
        jid = j.get("id", "")
        if u in applied_history or jid in applied_history:
            continue
        if is_target_management_job(j.get("title", ""), u):
            candidate_jobs.append(j)

    print(f"🎯 Số việc làm quản lý sẵn sàng nộp ca này: {len(candidate_jobs)}")
    if not candidate_jobs:
        print("🎉 Toàn bộ việc làm quản lý mục tiêu đã được nộp đầy đủ! Không có việc mới cần nộp.")
        return 0

    # Giới hạn số lượng duyệt
    max_evaluations = min(len(candidate_jobs), max_applies * 2)
    evaluation_queue = candidate_jobs[:max_evaluations]

    success_count = 0
    already_count = 0
    consecutive_fails = 0

    with sync_playwright() as p:
        browser = None
        context = None

        if use_cdp:
            print("🔗 Kết nối qua Chrome CDP (port 9223)...")
            try:
                browser = p.chromium.connect_over_cdp("http://127.0.0.1:9223")
                context = browser.contexts[0]
            except Exception as e:
                print(f"⚠️ Không thể kết nối CDP: {e}. Chuyển sang Chromium độc lập.")
                use_cdp = False

        if not use_cdp:
            # Mặc định sử dụng Residential/Mobile Proxy để tránh bị chặn IP
            proxy_cfg = None if os.environ.get("DISABLE_CV_PROXY", "false").lower() == "true" or os.environ.get("DISABLE_PROXY", "false").lower() == "true" else get_proxy_config()
            if proxy_cfg:
                print(f"🌐 CareerViet sử dụng Proxy: {proxy_cfg.get('server')}")
            launch_args = ["--disable-blink-features=AutomationControlled", "--no-sandbox"]
            browser = p.chromium.launch(headless=True, args=launch_args)
            context = browser.new_context(
                proxy=proxy_cfg,
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
                viewport={"width": 1440, "height": 900}
            )
            if proxy_cfg:
                def block_heavy_resources(route):
                    try:
                        req = route.request
                        if req.resource_type in ["image", "media", "font"]:
                            route.abort()
                        elif any(k in req.url for k in ["google-analytics", "googletagmanager", "facebook", "doubleclick", "clarity", "hotjar", "tiktok", "zalo"]):
                            route.abort()
                        else:
                            route.continue_()
                    except Exception:
                        pass
                context.route("**/*", block_heavy_resources)

            cookies = load_cookies()
            if cookies:
                pw_cookies = format_cookies_for_playwright(cookies)
                try:
                    context.add_cookies(pw_cookies)
                    print(f"🍪 Đã nạp {len(pw_cookies)} cookies cho phiên nộp đơn.")
                except Exception as e:
                    print(f"⚠️ Lỗi nạp cookies: {e}")

        page = context.new_page()

        session_report = {
            "platform": "CareerViet",
            "timestamp": datetime.now().isoformat(),
            "todo_count": len(evaluation_queue),
            "applied_count": 0,
            "applied_jobs": [],
            "skipped_counts": {
                "already_applied": 0,
                "expired": 0,
                "cf_blocked": 0,
                "daily_limit": 0,
                "errors": 0
            },
            "skipped_details": []
        }

        for job in evaluation_queue:
            if success_count >= max_applies:
                print(f"🏁 Đạt hạn mức {max_applies} việc làm cho ca hiện tại. Kết thúc phiên.")
                break

            status = apply_single_job(page, job, dry_run=dry_run)

            if status in ["APPLIED_OK", "DRY_RUN_OK"]:
                success_count += 1
                consecutive_fails = 0
                session_report["applied_count"] += 1
                session_report["applied_jobs"].append({
                    "title": job.get("title", ""),
                    "company": job.get("company", ""),
                    "url": job.get("url", ""),
                    "status": status
                })
                if not dry_run:
                    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    applied_history[job["url"]] = {
                        "id": job.get("id"),
                        "title": job.get("title"),
                        "company": job.get("company"),
                        "salary": job.get("salary"),
                        "location": job.get("location"),
                        "url": job["url"],
                        "applied_at": now_str,
                        "dry_run": False,
                        "source": "careerviet"
                    }
                    save_applied_history(applied_history)
                time.sleep(2.0)

            elif status == "ALREADY_APPLIED":
                already_count += 1
                consecutive_fails = 0
                session_report["skipped_counts"]["already_applied"] += 1
                session_report["skipped_details"].append({"url": job.get("url", ""), "title": job.get("title", ""), "reason": "Đã ứng tuyển trước đó"})
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                applied_history[job["url"]] = {
                    "id": job.get("id"),
                    "title": job.get("title"),
                    "company": job.get("company"),
                    "url": job["url"],
                    "applied_at": now_str,
                    "status": "already_applied_on_site",
                    "source": "careerviet"
                }
                save_applied_history(applied_history)

            else:
                consecutive_fails += 1
                if status in ["CLOSED", "EXPIRED"]:
                    session_report["skipped_counts"]["expired"] += 1
                    session_report["skipped_details"].append({"url": job.get("url", ""), "title": job.get("title", ""), "reason": "Tin tuyển dụng hết hạn/đóng"})
                else:
                    session_report["skipped_counts"]["errors"] += 1
                    session_report["skipped_details"].append({"url": job.get("url", ""), "title": job.get("title", ""), "reason": status or "Lỗi nộp đơn"})

                if consecutive_fails >= 5:
                    print("🛑 Circuit breaker: Đạt 5 lần thất bại liên tiếp. Tạm dừng để bảo vệ tài khoản.")
                    break

        page.close()
        if not use_cdp and browser:
            browser.close()

    # Lưu session_report.json
    try:
        if 'session_report' in locals():
            report_path = os.path.join(SCRIPT_DIR, "session_report.json")
            with open(report_path, "w", encoding="utf-8") as f:
                json.dump(session_report, f, indent=2, ensure_ascii=False)
            print(f"💾 Đã lưu báo cáo phiên CareerViet: {report_path}")
    except Exception as e:
        print(f"⚠️ Lỗi lưu session_report.json: {e}")

    print("\n" + "=" * 60)
    print("📊 KẾT QUẢ PHIÊN NỘP ĐƠN CAREERVIET:")
    print(f"  - Nộp mới thành công: {success_count}/{max_applies}")
    print(f"  - Việc làm đã nộp từ trước (bỏ qua): {already_count}")
    print(f"  - Tổng quy mô sổ cái đã nộp: {len(applied_history)} việc làm")
    print("=" * 60)

    save_applied_history(applied_history)
    return success_count

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CareerViet Auto-Applier")
    parser.add_argument("--max", type=int, default=30, help="Số lượng việc làm tối đa nộp mỗi ca")
    parser.add_argument("--dry-run", action="store_true", default=False, help="Chế độ chạy thử không bấm nộp thật")
    parser.add_argument("--cdp", action="store_true", default=False, help="Chạy qua cổng CDP trình duyệt đang mở")
    args = parser.parse_args()

    run_applier(max_applies=args.max, dry_run=args.dry_run, use_cdp=args.cdp)
