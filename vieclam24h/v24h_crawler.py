import os
import sys
import json
import time
import re
import urllib.parse
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

EXTRACTED_HISTORY_FILE = os.path.join(SCRIPT_DIR, "extracted_jobs_history.json")
EXTRACTED_HISTORY_TXT = os.path.join(SCRIPT_DIR, "extracted_jobs_history.txt")
SESSION_EXTRACTED_TXT = os.path.join(SCRIPT_DIR, "session_extracted_jobs.txt")

# Target Search URLs specified by user
TARGET_SEARCH_URLS = [
    "https://vieclam24h.vn/viec-lam-ha-noi-p73.html?q=giam%20doc%20kinh%20doanh&sort_q=priority_max%2Cdesc",
    "https://vieclam24h.vn/viec-lam-ha-noi-p73.html?q=truong%20phong%20kinh%20doanh&sort_q=priority_max%2Cdesc",
]

MAX_PAGES_PER_URL = 10  # Up to 10 pages * 30 jobs = 300 jobs per query

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

    # Fallback/merge from TXT
    if os.path.exists(EXTRACTED_HISTORY_TXT):
        try:
            with open(EXTRACTED_HISTORY_TXT, "r", encoding="utf-8") as f:
                for line in f:
                    u = line.strip()
                    if u and u not in history:
                        history[u] = {"url": u, "crawled_at": "unknown", "source": "vieclam24h"}
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

        print(f"💾 Đã lưu sổ cái: {len(history_dict)} việc làm toàn bộ (+{len(new_session_urls)} việc làm phiên này).")
    except Exception as e:
        print(f"❌ Lỗi ghi file lịch sử: {e}")

def get_page_url(base_url, page_number):
    parsed = urllib.parse.urlparse(base_url)
    params = urllib.parse.parse_qs(parsed.query)
    params["page"] = [str(page_number)]
    new_query = urllib.parse.urlencode(params, doseq=True)
    return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))

def extract_jobs_from_page(page, search_url):
    jobs = page.evaluate("""() => {
        const anchors = Array.from(document.querySelectorAll('a[href*="id"]')).filter(a => {
            return /id\\d+\\.html/.test(a.href);
        });

        const seen = new Set();
        const list = [];

        for (const a of anchors) {
            const cleanUrl = a.href.split('?')[0];
            if (seen.has(cleanUrl)) continue;
            seen.add(cleanUrl);

            // Find parent card container
            let card = a;
            for (let i = 0; i < 6; i++) {
                if (card.parentElement && (card.parentElement.className.includes('border') || card.parentElement.className.includes('rounded') || card.parentElement.className.includes('shadow') || card.parentElement.tagName === 'ARTICLE')) {
                    card = card.parentElement;
                    break;
                }
                if (card.parentElement) card = card.parentElement;
            }

            const titleEl = a.querySelector('h3') || card.querySelector('h3') || a;
            const title = titleEl ? titleEl.innerText.trim() : '';

            // Company
            const img = card.querySelector('figure img[alt], img[alt]');
            let company = img ? (img.getAttribute('alt') || '').trim() : '';
            if (!company) {
                const lines = card.innerText.split('\\n').map(l => l.trim()).filter(Boolean);
                if (lines.length > 1 && lines[0] === title) {
                    company = lines[1];
                }
            }

            // Salary
            let salary = 'Thoả thuận';
            const spans = Array.from(card.querySelectorAll('span'));
            for (const sp of spans) {
                const txt = sp.innerText ? sp.innerText.trim() : '';
                if (txt.includes('triệu') || txt.includes('Thoả thuận') || txt.includes('USD') || txt.includes('Thương lượng')) {
                    salary = txt;
                    break;
                }
            }
            if (salary === 'Thoả thuận') {
                const m = card.innerText.match(/(\\d+\\s*-\\s*\\d+\\s*triệu|Thoả thuận|Thương lượng|Trên\\s*\\d+\\s*triệu|Tới\\s*\\d+\\s*triệu|\\d+\\s*triệu)/i);
                if (m) salary = m[0].trim();
            }

            // Location
            let location = 'Hà Nội';
            if (card.innerText.includes('Hà Nội')) location = 'Hà Nội';
            else if (card.innerText.includes('TP.HCM') || card.innerText.includes('Hồ Chí Minh')) location = 'TP.HCM';

            // Job ID
            const idMatch = cleanUrl.match(/id(\\d+)\\.html/);
            const jobId = idMatch ? idMatch[1] : '';

            if (title && cleanUrl) {
                list.push({
                    id: jobId,
                    title: title,
                    url: cleanUrl,
                    company: company,
                    salary: salary,
                    location: location,
                    source: "vieclam24h"
                });
            }
        }
        return list;
    }""")
    return jobs

def detect_max_pages(page):
    pager_info = page.evaluate("""() => {
        const pageLinks = Array.from(document.querySelectorAll('a[href*="page="]')).map(a => {
            const m = a.href.match(/page=(\\d+)/);
            return m ? parseInt(m[1]) : 0;
        }).filter(n => n > 0);

        return {
            maxPage: pageLinks.length > 0 ? Math.max(...pageLinks) : 1
        };
    }""")
    return pager_info.get("maxPage", 1)

def crawl_vieclam24h(max_pages_limit=MAX_PAGES_PER_URL):
    print(f"\n================ BẮT ĐẦU CRAWLER VIECLAM24H: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ================")
    history_dict = load_extracted_history()
    print(f"📚 Sổ cái hiện có: {len(history_dict)} việc làm đã lưu.")

    proxy_cfg = get_proxy_config()
    if proxy_cfg:
        print(f"🌐 Sử dụng Proxy: {proxy_cfg.get('server')}")

    new_session_urls = []
    total_found_in_session = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, proxy=proxy_cfg)
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            locale="vi-VN"
        )
        page = context.new_page()

        if Stealth:
            try:
                stealth = Stealth()
                stealth.apply_stealth_sync(page)
            except Exception:
                pass

        for u_idx, base_url in enumerate(TARGET_SEARCH_URLS, 1):
            print(f"\n[{u_idx}/{len(TARGET_SEARCH_URLS)}] 🎯 ĐANG QUÉT MỤC TIÊU:")
            print(f"   URL: {base_url}")

            # Load first page to detect max pages from pager DOM
            paged_url_1 = get_page_url(base_url, 1)
            try:
                page.goto(paged_url_1, wait_until="domcontentloaded", timeout=40000)
                page.wait_for_timeout(3000)
            except Exception as e:
                print(f"⚠️ Không tải được trang 1: {e}")
                continue

            max_page_detected = detect_max_pages(page)
            total_pages = min(max_page_detected, max_pages_limit)
            print(f"   📄 Pager DOM phát hiện: {max_page_detected} trang. Sẽ duyệt: {total_pages} trang.")

            for page_num in range(1, total_pages + 1):
                paged_url = get_page_url(base_url, page_num)
                print(f"   -> Đang tải trang {page_num}/{total_pages}: {paged_url}")

                if page_num > 1:
                    try:
                        page.goto(paged_url, wait_until="domcontentloaded", timeout=40000)
                        page.wait_for_timeout(2500)
                    except Exception as e:
                        print(f"⚠️ Lỗi tải trang {page_num}: {e}")
                        continue

                # Wait for job cards to hydrate
                try:
                    page.wait_for_selector('a[href*="id"]', timeout=8000)
                except Exception:
                    pass

                jobs = extract_jobs_from_page(page, base_url)
                print(f"      + Tìm thấy {len(jobs)} việc làm trên trang.")

                for j in jobs:
                    u = j.get("url")
                    total_found_in_session += 1
                    if u not in history_dict:
                        j["crawled_at"] = datetime.now().isoformat()
                        history_dict[u] = j
                        new_session_urls.append(u)

        browser.close()

    save_extracted_history(history_dict, new_session_urls)

    print(f"\n================ HOÀN TẤT QUÉT VIECLAM24H ================")
    print(f"📊 Tổng việc quét được trong phiên: {total_found_in_session}")
    print(f"🆕 Việc làm MỚI được thêm vào: {len(new_session_urls)}")
    print(f"📦 Tổng số việc làm tích luỹ trong sổ cái: {len(history_dict)}")
    print(f"===========================================================\n")
    return len(new_session_urls)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-pages", type=int, default=MAX_PAGES_PER_URL)
    args = parser.parse_args()
    crawl_vieclam24h(max_pages_limit=args.max_pages)
