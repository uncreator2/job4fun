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
    # Priority 1: Environment variable CAREERVIET_COOKIES (không dùng chung COOKIES của TopCV)
    env_cookies = os.environ.get("CAREERVIET_COOKIES", "").strip()
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

def scroll_to_bottom_smoothly(page, max_steps=8, step_delay=0.35):
    """
    Cuộn trang mượt mà xuống đáy để kích hoạt lazy-loading, tải đầy đủ thẻ việc làm
    và hiển thị khối phân trang (pagination) trước khi trích xuất dữ liệu.
    """
    try:
        page.evaluate("""async ([maxSteps, stepDelay]) => {
            const distance = 800;
            let current = 0;
            while (current < maxSteps && (window.innerHeight + window.scrollY) < document.body.scrollHeight) {
                window.scrollBy(0, distance);
                current++;
                await new Promise(r => setTimeout(r, stepDelay * 1000));
            }
            // Cuộn dứt điểm xuống tận đáy trang để đảm bảo pagination xuất hiện trong DOM
            window.scrollTo(0, document.body.scrollHeight);
            await new Promise(r => setTimeout(r, 400));
        }""", [max_steps, step_delay])
    except Exception:
        try:
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(1)
        except Exception:
            pass

def parse_ssr_html(html_content):
    """
    Phân tích trực tiếp các khối HTML Server-Side Rendered (Next.js) của CareerViet.
    Trích xuất toàn bộ các thẻ việc làm với độ chính xác tuyệt đối.
    """
    import html as html_parser
    card_chunks = re.split(r'class=[\"\'][^\"\']*job-item[^\"\']*[\"\']', html_content)[1:]
    raw_jobs = []
    seen = set()

    for chunk in card_chunks:
        # Tìm thẻ liên kết việc làm
        a_m = re.search(r'<a[^>]*class=[\"\'][^\"\']*job_link[^\"\']*[\"\'][^>]*>', chunk, re.I)
        if not a_m:
            continue
        tag = a_m.group(0)

        # Trích xuất URL
        href_m = re.search(r'href=[\"\']([^\"\']+)[\"\']', tag, re.I)
        if not href_m:
            continue
        href = href_m.group(1).strip()
        if href.startswith('/'):
            href = 'https://careerviet.vn' + href
        clean_url = href.split('?')[0]
        if clean_url in seen:
            continue
        seen.add(clean_url)

        # Trích xuất Tiêu đề (ưu tiên thuộc tính title)
        title_m = re.search(r'title=[\"\']([^\"\']+)[\"\']', tag, re.I)
        title = html_parser.unescape(title_m.group(1).strip()) if title_m else ''
        if not title:
            h2_m = re.search(r'<h2[^>]*>[\s\S]*?<a[^>]*>([\s\S]*?)</a>', chunk, re.I)
            if h2_m:
                title = html_parser.unescape(re.sub(r'<[^>]+>', '', h2_m.group(1)).strip())
        if not title:
            continue

        # Trích xuất Công ty
        comp_m = re.search(r'class=[\"\'][^\"\']*company-name[^\"\']*[\"\'][^>]*title=[\"\']([^\"\']+)[\"\']', chunk, re.I)
        if not comp_m:
            comp_m = re.search(r'<a[^>]*class=[\"\'][^\"\']*company-name[^\"\']*[\"\'][^>]*>([\s\S]*?)</a>', chunk, re.I)
        company = html_parser.unescape(re.sub(r'<[^>]+>', '', comp_m.group(1)).strip()) if comp_m else ''

        # Trích xuất Mức lương
        sal_m = re.search(r'<div[^>]*class=[\"\'][^\"\']*salary[^\"\']*[\"\'][^>]*>[\s\S]*?<p>([\s\S]*?)</p>', chunk, re.I)
        salary = html_parser.unescape(re.sub(r'<[^>]+>', '', sal_m.group(1)).strip()) if sal_m else 'Thoả thuận'

        # Trích xuất Địa điểm
        loc_m = re.search(r'<div[^>]*class=[\"\'][^\"\']*location[^\"\']*[\"\'][^>]*>[\s\S]*?<li>([\s\S]*?)</li>', chunk, re.I)
        location = html_parser.unescape(re.sub(r'<[^>]+>', '', loc_m.group(1)).strip()) if loc_m else 'Hà Nội'

        # Trích xuất Mã việc làm
        id_m = re.search(r'\.([0-9A-Za-z]+)\.html$', clean_url)
        job_id = id_m.group(1) if id_m else ''

        raw_jobs.append({
            "id": job_id,
            "title": title,
            "url": clean_url,
            "company": company,
            "salary": salary,
            "location": location,
            "source": "careerviet"
        })

    return raw_jobs

def fetch_direct_ssr_html(url):
    """
    Tải trực tiếp mã nguồn HTML SSR từ máy chủ CareerViet qua HTTP GET.
    Bảo đảm trích xuất việc làm thành công ngay cả khi Playwright gặp sự cố render.
    """
    import urllib.request
    try:
        req = urllib.request.Request(
            url,
            headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'vi,en;q=0.9'
            }
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read().decode('utf-8', errors='ignore')
    except Exception as e:
        print(f"    ⚠️ Lỗi Direct HTTP SSR fetch: {e}")
        return ""

def extract_jobs_from_page(page, search_source_url, page_target_url):
    # 1. Cuộn mượt mà xuống đáy trang để lazy-loading gắn kết tất cả thẻ việc làm & pagination
    scroll_to_bottom_smoothly(page)

    # 2. Đợi phần tử .job-item gắn kết trong DOM
    try:
        page.wait_for_selector('.job-item, .job_link', timeout=5000)
    except Exception:
        pass

    # 3. Lớp 1: Trích xuất trực tiếp từ Live DOM
    raw_jobs = page.evaluate("""() => {
        const cards = Array.from(document.querySelectorAll('.job-item'));
        const list = [];
        const seen = new Set();

        for (const card of cards) {
            // Ưu tiên thẻ tiêu đề trong .figcaption .title hoặc h2
            let titleEl = card.querySelector('.figcaption .title a, .title a, h2 a, a.job_link[data-id], .job_link');
            if (!titleEl || !(titleEl.getAttribute('title') || titleEl.innerText || titleEl.textContent || '').trim()) {
                const links = Array.from(card.querySelectorAll('a'));
                titleEl = links.find(a => (a.getAttribute('href') || '').includes('/tim-viec-lam/') && ((a.getAttribute('title') || a.innerText || a.textContent || '').trim().length > 0));
            }
            if (!titleEl) continue;

            const title = (titleEl.getAttribute('title') || titleEl.innerText || titleEl.textContent || '').trim();
            let href = titleEl.getAttribute('href') || '';
            if (!href || !title) continue;
            if (href.startsWith('/')) {
                href = 'https://careerviet.vn' + href;
            }
            const cleanUrl = href.split('?')[0];
            if (seen.has(cleanUrl)) continue;
            seen.add(cleanUrl);

            // Tên công ty
            const compEl = card.querySelector('.company-name a, .company-name, .employer a');
            const company = compEl ? (compEl.getAttribute('title') || compEl.innerText || compEl.textContent || '').trim() : '';

            // Mức lương
            const salaryEl = card.querySelector('.salary, .job-salary');
            const salary = salaryEl ? (salaryEl.innerText || salaryEl.textContent || '').trim() : 'Thoả thuận';

            // Địa điểm
            const locEl = card.querySelector('.location, .job-location');
            let location = locEl ? (locEl.innerText || locEl.textContent || '').trim().replace(/\\n/g, ', ') : 'Hà Nội';

            // Mã việc làm
            const idMatch = cleanUrl.match(/\\.([0-9A-Za-z]+)\\.html$/);
            const jobId = idMatch ? idMatch[1] : (card.getAttribute('data-id') || '');

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

    # 4. Lớp 2: Phân tích SSR HTML từ page.content() nếu Live DOM trả về 0 thẻ
    if not raw_jobs:
        try:
            content = page.content()
            if content and "job-item" in content:
                raw_jobs = parse_ssr_html(content)
                if raw_jobs:
                    print(f"    ℹ️ Đã phục hồi {len(raw_jobs)} việc làm qua Lớp 2 (SSR HTML parser).")
        except Exception as e:
            print(f"    ⚠️ Lỗi Lớp 2 (SSR HTML): {e}")

    # 5. Lớp 3: Tải trực tiếp HTTP SSR nếu cả DOM lẫn page.content() đều trống
    if not raw_jobs:
        try:
            print(f"    🔄 Kích hoạt Lớp 3 (Direct HTTP SSR Fallback) cho {page_target_url}...")
            direct_html = fetch_direct_ssr_html(page_target_url)
            if direct_html:
                raw_jobs = parse_ssr_html(direct_html)
                if raw_jobs:
                    print(f"    ✅ Lớp 3 (Direct HTTP) đã trích xuất thành công {len(raw_jobs)} việc làm!")
        except Exception as e:
            print(f"    ⚠️ Lỗi Lớp 3 (Direct HTTP): {e}")

    # 6. Chẩn đoán khi không phát hiện được thẻ nào
    if not raw_jobs:
        try:
            os.makedirs(os.path.join(SCRIPT_DIR, "errors"), exist_ok=True)
            err_ts = int(time.time())
            err_png = os.path.join(SCRIPT_DIR, "errors", f"cv_empty_crawl_{err_ts}.png")
            err_html = os.path.join(SCRIPT_DIR, "errors", f"cv_empty_crawl_{err_ts}.html")
            page.screenshot(path=err_png)
            with open(err_html, "w", encoding="utf-8") as f:
                f.write(page.content())
            print(f"    📸 Đã lưu snapshot lỗi chẩn đoán: {err_png}")
        except Exception:
            pass

    raw_count = len(raw_jobs)

    # 7. Áp dụng bộ lọc chức danh quản lý nghiêm ngặt
    filtered_jobs = []
    for j in raw_jobs:
        title = j.get("title", "")
        url = j.get("url", "")
        if is_target_management_job(title, url):
            j["crawled_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            j["search_source"] = search_source_url
            filtered_jobs.append(j)

    return filtered_jobs, raw_count

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
            # CareerViet không chặn IP runner GitHub; dùng Direct IP để đạt tốc độ và độ tin cậy tối đa.
            # Chỉ dùng proxy nếu ENABLE_CV_PROXY=true hoặc USE_CV_PROXY=true
            use_proxy = os.environ.get("ENABLE_CV_PROXY", "false").lower() in ["true", "1"] or os.environ.get("USE_CV_PROXY", "false").lower() in ["true", "1"]
            proxy_cfg = get_proxy_config() if use_proxy else None
            if proxy_cfg:
                print(f"🌐 CareerViet sử dụng Proxy: {proxy_cfg.get('server')}")
            else:
                print("🌐 CareerViet sử dụng Direct IP (Tốc độ cao, ổn định)")

            launch_args = ["--disable-blink-features=AutomationControlled", "--no-sandbox"]
            browser = p.chromium.launch(headless=True, args=launch_args)
            context = browser.new_context(
                proxy=proxy_cfg,
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                viewport={"width": 1440, "height": 900}
            )
            if proxy_cfg:
                def block_heavy_resources(route):
                    try:
                        req = route.request
                        if "_next" in req.url:
                            route.continue_()
                            return
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
                    # Tải trang với wait_until domcontentloaded để đảm bảo cấu trúc HTML đã hoàn tất
                    loaded = False
                    for attempt in range(1, 3):
                        try:
                            page.goto(page_target_url, timeout=30000, wait_until="domcontentloaded")
                            time.sleep(1.5)
                            loaded = True
                            break
                        except Exception as nav_err:
                            if attempt == 1:
                                print(f"    ⚠️ Lần 1 tải trang bị trễ ({nav_err}), thử lại...")
                                time.sleep(2)
                            else:
                                print(f"    ⚠️ Không thể tải qua Playwright ({nav_err}), chuyển sang Lớp trích xuất dự phòng...")

                    # Trích xuất việc làm (cuộn trang mượt mà, trích xuất 3 lớp DOM/SSR/HTTP)
                    jobs, raw_count = extract_jobs_from_page(page, search_url, page_target_url)
                    print(f"    -> Thẻ việc làm phát hiện (DOM/SSR): {raw_count} | Phù hợp bộ lọc quản lý: {len(jobs)}")

                    if not jobs:
                        if raw_count == 0:
                            print(f"    ⏹️ Không phát hiện thẻ việc làm nào trên trang (URL: {page.url}). Chuyển truy vấn tiếp theo.")
                        else:
                            print(f"    ⏹️ Đã duyệt {raw_count} việc làm nhưng không có việc nào đạt tiêu chuẩn quản lý. Chuyển truy vấn.")
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

                    print(f"    -> Đã thêm {new_on_page} việc làm MỚI vào sổ cái ({len(jobs) - new_on_page} đã có trong lịch sử).")

                    # Nếu số việc làm thô ít hơn 50 (trang cuối cùng trong phân trang), dừng duyệt trang tiếp theo
                    if raw_count < 50:
                        print("    ⏹️ Trang hiện tại chứa ít hơn 50 việc làm (đã đạt cuối phân trang). Chuyển truy vấn tiếp theo.")
                        break

                except Exception as e:
                    print(f"    ❌ Lỗi khi duyệt trang {page_num}: {e}")
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
