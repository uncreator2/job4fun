import os
import sys
import json
import time
import re
from datetime import datetime
from playwright.sync_api import sync_playwright

# Setup import path for proxy_utils
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
LATEST_JOBS_FILE = os.path.join(SCRIPT_DIR, "latest_extracted_jobs.json")
SEARCH_URLS_FILE = os.path.join(SCRIPT_DIR, "search_urls.txt")

MAX_PAGES_PER_QUERY = 5

DEFAULT_SEARCH_URLS = [
    "https://www.vietnamworks.com/viec-lam?q=giam-doc-kinh-doanh&l=24",
    "https://www.vietnamworks.com/viec-lam?q=truong-phong-kinh-doanh&l=24",
    "https://www.vietnamworks.com/viec-lam?q=business-manager&l=24",
    "https://www.vietnamworks.com/viec-lam?l=70"
]

def load_search_urls():
    if os.path.exists(SEARCH_URLS_FILE):
        with open(SEARCH_URLS_FILE, "r", encoding="utf-8") as f:
            urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]
            if urls:
                return urls
    return DEFAULT_SEARCH_URLS

def load_cookies():
    # Priority 1: Environment variable VNW_COOKIES or COOKIES
    env_cookies = os.environ.get("VNW_COOKIES", "") or os.environ.get("COOKIES", "")
    if env_cookies:
        try:
            return json.loads(env_cookies)
        except Exception:
            pass

    # Priority 2: JSON file in script dir
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

def extract_jobs_from_page(page, search_source_url):
    handle_experience_modal(page)
    jobs_data = page.evaluate("""() => {
        const results = [];
        const anchors = Array.from(document.querySelectorAll('a[href*="-jv"]'));
        const seen = new Set();

        for (const a of anchors) {
            const rawHref = a.href;
            const cleanUrl = rawHref.split('?')[0];
            const title = a.innerText.trim();

            if (!seen.has(cleanUrl) && title.length > 5) {
                seen.add(cleanUrl);

                // Extract job ID from URL (e.g., ...-2100900-jv -> 2100900)
                const idMatch = cleanUrl.match(/-(\\d+)-jv$/);
                const jobId = idMatch ? idMatch[1] : '';

                // Find card container to get company, salary, location
                const card = a.closest('div[class*="block-job-item"], div[class*="JobItem"], div[class*="card"]') || a.parentElement;
                let company = '';
                let salary = '';
                let location = '';

                if (card) {
                    const cardText = card.innerText;
                    const lines = cardText.split('\\n').map(l => l.trim()).filter(l => l.length > 0);
                    // Usually company is the line after title or has company link
                    const compLink = card.querySelector('a[href*="/nha-tuyen-dung/"], [class*="company"]');
                    company = compLink ? compLink.innerText.trim() : '';

                    // Find salary indicators
                    for (const line of lines) {
                        if (line.includes('đ/tháng') || line.includes('$') || line.includes('Thương lượng') || line.includes('Lương:')) {
                            salary = line;
                            break;
                        }
                    }
                }

                results.push({
                    id: jobId,
                    title: title,
                    company: company,
                    salary: salary,
                    url: cleanUrl,
                    full_url: rawHref
                });
            }
        }
        return results;
    }""")
    return jobs_data

def crawl_vietnamworks():
    print(f"🚀 BẮT ĐẦU CRAWLER VIETNAMWORKS: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    search_urls = load_search_urls()
    print(f"📋 Danh sách {len(search_urls)} URL tìm kiếm mục tiêu:")
    for u in search_urls:
        print(f"   - {u}")

    # Load existing ledger
    extracted_history = {}
    if os.path.exists(EXTRACTED_HISTORY_FILE):
        try:
            with open(EXTRACTED_HISTORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    for j in data:
                        extracted_history[j.get("url")] = j
                elif isinstance(data, dict):
                    extracted_history = data
        except Exception as e:
            print(f"⚠️ Không thể đọc {EXTRACTED_HISTORY_FILE}: {e}")

    print(f"📦 Số lượng việc làm đã lưu trong ledger trước ca: {len(extracted_history)}")

    proxy_cfg = get_proxy_config()
    raw_cookies = load_cookies()
    formatted_cookies = format_cookies_for_playwright(raw_cookies)
    print(f"🔑 Tải được {len(formatted_cookies)} cookie xác thực.")

    new_jobs_this_run = []

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

        # Step 1: Initialize session on homepage
        print("🌐 Đang khởi tạo phiên làm việc tại trang chủ VietnamWorks...")
        try:
            page.goto("https://www.vietnamworks.com/", wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(2000)
            handle_experience_modal(page)
        except Exception as e:
            print(f"⚠️ Không tải được trang chủ: {e}")

        # Step 2: Loop through search URLs
        for search_url in search_urls:
            print(f"\n🔍 Đang quét danh mục: {search_url}")
            for page_num in range(1, MAX_PAGES_PER_QUERY + 1):
                paged_url = f"{search_url}&page={page_num}" if page_num > 1 else search_url
                print(f"   📄 Trang {page_num}: {paged_url}")

                try:
                    resp = page.goto(paged_url, wait_until="domcontentloaded", timeout=30000)
                    page.wait_for_timeout(2000)
                    handle_experience_modal(page)

                    if resp and resp.status == 403:
                        print("   ⚠️ Nginx 403. Thử tải lại qua trang chủ...")
                        page.goto("https://www.vietnamworks.com/", wait_until="domcontentloaded", timeout=20000)
                        page.wait_for_timeout(1000)
                        resp = page.goto(paged_url, wait_until="domcontentloaded", timeout=30000)
                        page.wait_for_timeout(2000)

                    # Wait up to 10s for job cards to hydrate
                    try:
                        page.wait_for_selector('a[href*="-jv"]', timeout=10000)
                    except Exception:
                        pass

                    jobs = extract_jobs_from_page(page, search_url)
                    print(f"      -> Tìm thấy {len(jobs)} việc làm trên trang.")

                    if not jobs:
                        print("      -> Hết việc làm hoặc đã đến trang cuối.")
                        break

                    added_in_page = 0
                    for j in jobs:
                        url = j["url"]
                        if url not in extracted_history:
                            j["first_seen"] = datetime.now().isoformat()
                            j["search_source"] = search_url
                            extracted_history[url] = j
                            new_jobs_this_run.append(j)
                            added_in_page += 1

                    print(f"      -> Thêm mới {added_in_page} việc làm chưa từng có.")

                except Exception as e:
                    print(f"   ❌ Lỗi khi quét trang {page_num}: {e}")
                    break

        browser.close()

    # Save to history ledger
    history_list = list(extracted_history.values())
    with open(EXTRACTED_HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history_list, f, ensure_ascii=False, indent=2)

    with open(LATEST_JOBS_FILE, "w", encoding="utf-8") as f:
        json.dump(new_jobs_this_run, f, ensure_ascii=False, indent=2)

    print(f"\n================ BÁO CÁO CRAWLER VIETNAMWORKS ================")
    print(f"✅ Việc làm mới thu thập trong ca này: {len(new_jobs_this_run)}")
    print(f"📊 Tổng số việc làm tích lũy trong ledger: {len(history_list)}")
    print(f"💾 Đã lưu vào: {EXTRACTED_HISTORY_FILE}")
    print(f"===============================================================")
    return len(new_jobs_this_run)

if __name__ == "__main__":
    crawl_vietnamworks()
