# -*- coding: utf-8 -*-
"""
CareerViet Multi-Page Crawler
Extracts target managerial/director positions from CareerViet search results,
applies executive role filters, and maintains deduplicated history ledgers.
"""

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
    from cv_filter import is_target_management_job
except ImportError:
    from careerviet.cv_filter import is_target_management_job

EXTRACTED_HISTORY_FILE = os.path.join(SCRIPT_DIR, "extracted_jobs_history.json")
EXTRACTED_HISTORY_TXT = os.path.join(SCRIPT_DIR, "extracted_jobs_history.txt")
SESSION_EXTRACTED_TXT = os.path.join(SCRIPT_DIR, "session_extracted_jobs.txt")
SEARCH_URLS_FILE = os.path.join(SCRIPT_DIR, "search_urls.txt")
COOKIE_FILE = os.path.join(SCRIPT_DIR, "careerviet_cookies.json")

DEFAULT_SEARCH_URLS = [
    "https://careerviet.vn/viec-lam/giam-doc-kinh-doanh-tai-ha-noi-kl4-vi.html",
    "https://careerviet.vn/viec-lam/truong-phong-kinh-doanh-tai-ha-noi-kl4-vi.html"
]

MAX_PAGES_PER_QUERY = 5

def load_search_urls():
    if os.path.exists(SEARCH_URLS_FILE):
        with open(SEARCH_URLS_FILE, "r", encoding="utf-8") as f:
            urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]
            if urls:
                return urls
    return DEFAULT_SEARCH_URLS

def load_cookies():
    # Priority 1: Environment variable CAREERVIET_COOKIES or COOKIES
    env_cookies = os.environ.get("CAREERVIET_COOKIES", "") or os.environ.get("COOKIES", "")
    if env_cookies:
        try:
            return json.loads(env_cookies)
        except Exception:
            pass

    # Priority 2: JSON file in script directory
    if os.path.exists(COOKIE_FILE):
        try:
            with open(COOKIE_FILE, "r", encoding="utf-8") as f:
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
            "domain": c.get("domain", ".careerviet.vn"),
            "path": c.get("path", "/"),
        }
        if "secure" in c:
            cookie["secure"] = c["secure"]
        if "httpOnly" in c:
            cookie["httpOnly"] = c["httpOnly"]
        cookies.append(cookie)
    return cookies

def load_extracted_history():
    history = {}
    if os.path.exists(EXTRACTED_HISTORY_FILE):
        try:
            with open(EXTRACTED_HISTORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    for item in data:
                        u = item.get("url")
                        if u:
                            history[u] = item
                elif isinstance(data, dict):
                    history = data
        except Exception as e:
            print(f"⚠️ Lỗi đọc extracted_jobs_history.json: {e}")

    if os.path.exists(EXTRACTED_HISTORY_TXT):
        try:
            with open(EXTRACTED_HISTORY_TXT, "r", encoding="utf-8") as f:
                for line in f:
                    u = line.strip()
                    if u and u not in history:
                        history[u] = {"url": u, "crawled_at": "unknown", "source": "careerviet"}
        except Exception as e:
            print(f"⚠️ Lỗi đọc extracted_jobs_history.txt: {e}")

    return history

def save_extracted_history(history_dict, new_session_urls):
    try:
        with open(EXTRACTED_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(list(history_dict.values()), f, ensure_ascii=False, indent=2)

        with open(EXTRACTED_HISTORY_TXT, "w", encoding="utf-8") as f:
            for u in sorted(history_dict.keys()):
                f.write(f"{u}\n")

        with open(SESSION_EXTRACTED_TXT, "w", encoding="utf-8") as f:
            for u in new_session_urls:
                f.write(f"{u}\n")

        print(f"💾 Đã lưu sổ cái: {len(history_dict)} việc làm toàn bộ (+{len(new_session_urls)} việc làm mới phiên này).")
    except Exception as e:
        print(f"❌ Lỗi ghi file lịch sử: {e}")

def get_page_url(base_url, page_number):
    if page_number <= 1:
        return base_url
    if "-vi.html" in base_url:
        return base_url.replace("-vi.html", f"-trang-{page_number}-vi.html")
    return f"{base_url}?page={page_number}"

def extract_jobs_from_page(page, search_source_url):
    raw_jobs = page.evaluate("""() => {
        const cards = Array.from(document.querySelectorAll('.job-item'));
        const list = [];
        const seen = new Set();

        for (const card of cards) {
            const titleEl = card.querySelector('.job-title a, a.job_link, .title a');
            if (!titleEl) continue;

            const title = titleEl.innerText.trim();
            let href = titleEl.getAttribute('href') || '';
            if (!href) continue;
            if (href.startsWith('/')) {
                href = 'https://careerviet.vn' + href;
            }
            const cleanUrl = href.split('?')[0];
            if (seen.has(cleanUrl)) continue;
            seen.add(cleanUrl);

            // Company
            const compEl = card.querySelector('.company-name a, .company-name, .employer a');
            const company = compEl ? compEl.innerText.trim() : '';

            // Salary
            const salaryEl = card.querySelector('.salary, .job-salary');
            const salary = salaryEl ? salaryEl.innerText.trim() : 'Thoả thuận';

            // Location
            const locEl = card.querySelector('.location, .job-location');
            let location = locEl ? locEl.innerText.trim().replace(/\\n/g, ', ') : 'Hà Nội';

            // Extract Job ID
            const idMatch = cleanUrl.match(/\\.([0-9A-Za-z]+)\\.html$/);
            const jobId = idMatch ? idMatch[1] : '';

            list.push({
                id: jobId,
                title: title,
                url: cleanUrl,
                company: company,
                salary: salary,
                location: location,
                source: "careerviet"
            });
        }
        return list;
    }""")

    # Apply strict role filter
    filtered_jobs = []
    for j in raw_jobs:
        title = j.get("title", "")
        url = j.get("url", "")
        if is_target_management_job(title, url):
            j["crawled_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            j["search_source"] = search_source_url
            filtered_jobs.append(j)

    return filtered_jobs

def run_crawler(max_pages=MAX_PAGES_PER_QUERY, use_cdp=False):
    print("=" * 60)
    print("🚀 BẮT ĐẦU CRAWLER CAREERVIET (HÀ NỘI - MANAGEMENT)")
    print(f"⏰ Thời gian: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    search_urls = load_search_urls()
    print(f"📋 Danh sách truy vấn ({len(search_urls)} URLs):")
    for u in search_urls:
        print(f"  - {u}")

    history = load_extracted_history()
    print(f"📚 Sổ cái hiện tại: {len(history)} việc làm đã lưu.")

    new_session_urls = []
    total_found_session = 0

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

            # Load cookies
            cookies = load_cookies()
            if cookies:
                pw_cookies = format_cookies_for_playwright(cookies)
                try:
                    context.add_cookies(pw_cookies)
                    print(f"🍪 Đã nạp {len(pw_cookies)} cookies cho phiên CareerViet.")
                except Exception as e:
                    print(f"⚠️ Lỗi nạp cookies: {e}")

        page = context.new_page()

        for search_idx, search_url in enumerate(search_urls, 1):
            print(f"\n🔍 [{search_idx}/{len(search_urls)}] Quét URL mục tiêu: {search_url}")

            for page_num in range(1, max_pages + 1):
                page_target_url = get_page_url(search_url, page_num)
                print(f"  📄 Trang {page_num}: {page_target_url}")

                try:
                    page.goto(page_target_url, timeout=30000, wait_until="domcontentloaded")
                    time.sleep(2)

                    # Extract jobs
                    jobs = extract_jobs_from_page(page, search_url)
                    print(f"    -> Tìm thấy {len(jobs)} việc làm quản lý phù hợp trên trang.")

                    if not jobs:
                        print("    ⏹️ Không còn việc làm phù hợp trên trang này, chuyển truy vấn tiếp theo.")
                        break

                    new_on_page = 0
                    for j in jobs:
                        u = j["url"]
                        total_found_session += 1
                        if u not in history:
                            history[u] = j
                            new_session_urls.append(u)
                            new_on_page += 1
                            print(f"      ✨ MỚI: [{j['id']}] {j['title']} | {j['company']} | {j['salary']}")

                    print(f"    -> Đã thêm {new_on_page} việc làm mới vào sổ cái.")

                except Exception as e:
                    print(f"    ❌ Lỗi khi duyệt trang {page_num}: {e}")
                    # Save error screenshot
                    err_pic = os.path.join(SCRIPT_DIR, "errors", f"crawl_err_q{search_idx}_p{page_num}.png")
                    try:
                        page.screenshot(path=err_pic)
                    except Exception:
                        pass
                    break

        page.close()
        if not use_cdp and browser:
            browser.close()

    print("\n" + "=" * 60)
    print(f"📊 KẾT QUẢ PHIÊN CRAWL CAREERVIET:")
    print(f"  - Tổng số việc làm quản lý rà soát phiên này: {total_found_session}")
    print(f"  - Việc làm MỚI được thêm vào sổ cái: {len(new_session_urls)}")
    print(f"  - Tổng quy mô sổ cái CareerViet hiện tại: {len(history)} việc làm")
    print("=" * 60)

    save_extracted_history(history, new_session_urls)
    return len(new_session_urls)

if __name__ == "__main__":
    use_cdp_mode = "--cdp" in sys.argv
    run_crawler(use_cdp=use_cdp_mode)
