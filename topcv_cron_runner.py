import asyncio
from datetime import datetime
import json
import os
import random
import sys
from playwright.async_api import async_playwright

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_FILE = os.path.join(BASE_DIR, "env.txt")
COOKIES_FILE = os.path.join(BASE_DIR, "topcv_cookies.json")
SEARCH_URLS_FILE = os.path.join(BASE_DIR, "search_urls.txt")

# Output files
SESSION_TXT = os.path.join(BASE_DIR, "session_extracted_jobs.txt")
SESSION_JSON = os.path.join(BASE_DIR, "session_extracted_jobs.json")
HISTORY_TXT = os.path.join(BASE_DIR, "extracted_jobs_history.txt")
HISTORY_JSON = os.path.join(BASE_DIR, "extracted_jobs_history.json")
STATUS_SCREENSHOT = os.path.join(BASE_DIR, "topcv_status.png")

# Configuration
MAX_PAGES_PER_QUERY = int(os.environ.get("MAX_PAGES_PER_QUERY", "20"))
DEFAULT_SEARCH_URLS = [
    "https://www.topcv.vn/tim-viec-lam-giam-doc-kinh-doanh-tai-ha-noi-kl1?type_keyword=1&sba=1&locations=l1",
    "https://www.topcv.vn/tim-viec-lam-truong-phong-kinh-doanh-tai-ha-noi-kl1?type_keyword=1&sba=1&locations=l1",
    "https://www.topcv.vn/tim-viec-lam-kinh-doanh-tai-nuoc-ngoai-kl100?type_keyword=1&sba=1&locations=l100_l10001_l10002&saturday_status=0"
]

def log(msg):
    print(msg, flush=True)

async def human_delay(min_sec=2.0, max_sec=4.0):
    delay = random.uniform(min_sec, max_sec)
    await asyncio.sleep(delay)

def load_history():
    history_set = set()
    history_dict = {}

    if os.path.exists(HISTORY_TXT):
        try:
            with open(HISTORY_TXT, "r", encoding="utf-8") as f:
                history_set = {line.strip() for line in f if line.strip()}
        except Exception as e:
            log(f"[!] Warning reading {HISTORY_TXT}: {e}")

    if os.path.exists(HISTORY_JSON):
        try:
            with open(HISTORY_JSON, "r", encoding="utf-8") as f:
                history_dict = json.load(f)
                for k in history_dict.keys():
                    history_set.add(k)
        except Exception as e:
            log(f"[!] Warning reading {HISTORY_JSON}: {e}")

    return history_set, history_dict

def save_history(all_history_dict, new_unique_jobs):
    for job in new_unique_jobs:
        url = job["clean_url"]
        if url not in all_history_dict:
            all_history_dict[url] = job

    with open(HISTORY_JSON, "w", encoding="utf-8") as f:
        json.dump(all_history_dict, f, indent=2, ensure_ascii=False)

    with open(HISTORY_TXT, "a", encoding="utf-8") as f:
        for job in new_unique_jobs:
            f.write(job["clean_url"] + "\n")

def get_target_search_urls():
    custom_url = os.environ.get("SEARCH_URL", "").strip()
    if custom_url:
        return [custom_url]

    if os.path.exists(SEARCH_URLS_FILE):
        try:
            with open(SEARCH_URLS_FILE, "r", encoding="utf-8") as f:
                urls = [l.strip() for l in f if l.strip() and not l.startswith("#")]
                if urls:
                    return urls
        except Exception as e:
            log(f"[!] Warning reading {SEARCH_URLS_FILE}: {e}")

    return DEFAULT_SEARCH_URLS

async def inject_cookies(context):
    raw_cookies_env = os.environ.get("COOKIES", "").strip()
    if raw_cookies_env and not os.path.exists(COOKIES_FILE):
        try:
            with open(COOKIES_FILE, "w", encoding="utf-8") as f:
                f.write(raw_cookies_env)
        except Exception:
            pass

    if os.path.exists(COOKIES_FILE):
        try:
            with open(COOKIES_FILE, "r", encoding="utf-8") as f:
                raw_cookies = json.load(f)
                formatted = []
                for c in raw_cookies:
                    formatted.append({
                        "name": c["name"],
                        "value": c["value"],
                        "domain": c.get("domain", ".topcv.vn"),
                        "path": c.get("path", "/")
                    })
                await context.add_cookies(formatted)
                log(f"[*] Đã nạp {len(formatted)} cookies vào phiên trình duyệt.")
                return True
        except Exception as e:
            log(f"[!] Lỗi đọc cookies: {e}")
    return False

async def dismiss_popups(page):
    try:
        await page.evaluate("""() => {
            // Dismiss survey modal, backdrop, and cookies banner
            const popups = document.querySelectorAll(
                '#modal-survey-reliability, .modal, .modal-backdrop, .overlay-ignore, #form-setting-cookie'
            );
            popups.forEach(el => el.remove());
            document.body.classList.remove('modal-open');
        }""")
    except Exception:
        pass

async def extract_jobs_from_current_page(page, query_url):
    await dismiss_popups(page)

    # Scroll smoothly in increments to trigger lazy-loading of cards & images
    for _ in range(4):
        await page.evaluate("window.scrollBy(0, 800)")
        await asyncio.sleep(0.3)

    jobs_data = await page.evaluate("""() => {
        const cards = Array.from(document.querySelectorAll('.job-item-search-result'));
        return cards.map(card => {
            const titleA = card.querySelector('.title a, h3 a, a[href*="/viec-lam/"]');
            const compA = card.querySelector('.company, .company-name');
            const salEl = card.querySelector('.title-salary, .salary');
            const cityEl = card.querySelector('.city-text, .address');
            const expEl = card.querySelector('.exp');
            const jobId = card.getAttribute('data-job-id');

            let rawUrl = titleA ? titleA.href : '';
            let cleanUrl = rawUrl.split('?')[0];

            return {
                job_id: jobId,
                title: titleA ? titleA.innerText.trim() : '',
                raw_url: rawUrl,
                clean_url: cleanUrl,
                company: compA ? compA.innerText.trim() : '',
                salary: salEl ? salEl.innerText.trim() : '',
                location: cityEl ? cityEl.innerText.trim() : '',
                exp: expEl ? expEl.innerText.trim() : ''
            };
        }).filter(j => !!j.clean_url);
    }""")

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for j in jobs_data:
        j["first_extracted_at"] = now_str
        j["source_search_url"] = query_url

    return jobs_data

async def run():
    log("==================================================")
    log("🔍 TOPCV WORKER: QUÉT VÀ TRÍCH XUẤT VIỆC LÀM TỰ ĐỘNG")
    log("==================================================")

    history_set, history_dict = load_history()
    log(f"📚 Sổ cái lịch sử hiện có: {len(history_set)} việc làm.")

    search_urls = get_target_search_urls()
    log(f"🎯 Tổng số URL tìm kiếm cần quét: {len(search_urls)}")

    all_session_extracted_jobs = []
    seen_in_session_set = set()

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage"
            ]
        )
        context = await browser.new_context(
            viewport={"width": 1440, "height": 900},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36",
            locale="vi-VN",
            timezone_id="Asia/Ho_Chi_Minh"
        )
        page = await context.new_page()

        # Nạp session cookies
        await inject_cookies(context)

        # Lặp qua từng URL tìm kiếm
        for idx, base_search_url in enumerate(search_urls, start=1):
            log(f"\n--------------------------------------------------")
            log(f"🚀 [{idx}/{len(search_urls)}] Quét URL mục tiêu: {base_search_url}")

            current_target_url = base_search_url
            page_num = 1

            while page_num <= MAX_PAGES_PER_QUERY:
                log(f"  📄 Đang tải Trang {page_num}: {current_target_url}...")
                try:
                    await page.goto(current_target_url, wait_until="domcontentloaded", timeout=35000)
                    await asyncio.sleep(2.0)
                except Exception as e:
                    log(f"     [!] Notice tải trang: {e}")

                # Kiểm tra xem có bị Cloudflare chặn không
                is_cf_blocked = await page.evaluate("document.body.innerText.includes('Why have I been blocked')")
                if is_cf_blocked:
                    log("     ❌ Bị Cloudflare phát hiện! Tạm ngưng quét URL này để đảm bảo an toàn.")
                    break

                current_jobs = await extract_jobs_from_current_page(page, base_search_url)
                log(f"     -> Trích xuất được {len(current_jobs)} việc làm trên trang {page_num}.")

                for j in current_jobs:
                    u = j["clean_url"]
                    if u and u not in seen_in_session_set:
                        seen_in_session_set.add(u)
                        all_session_extracted_jobs.append(j)

                if page_num >= MAX_PAGES_PER_QUERY:
                    log(f"  🛑 Đã đạt giới hạn tối đa ({MAX_PAGES_PER_QUERY} trang) cho URL này.")
                    break

                # Scroll xuống gần cuối trang để kiểm tra nút phân trang kế tiếp
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight - 500)")
                await asyncio.sleep(1.0)
                await dismiss_popups(page)

                pagination_info = await page.evaluate("""() => {
                    const nextBtn = document.querySelector('a[rel="next"]') ||
                                    document.querySelector('a[aria-label*="Next"]') ||
                                    document.querySelector('li.active + li a');
                    if (!nextBtn) return null;

                    const isParentDisabled = nextBtn.parentElement && nextBtn.parentElement.classList.contains('disabled');
                    const isDisabled = nextBtn.classList.contains('disabled') || isParentDisabled;
                    if (isDisabled) return null;

                    const dataHref = nextBtn.getAttribute('data-href');
                    const href = nextBtn.href;
                    return {
                        has_next: true,
                        next_url: dataHref || href
                    };
                }""")

                if not pagination_info or not pagination_info.get("has_next"):
                    log(f"  🏁 Đã đến trang cuối cùng của URL này (Tổng {page_num} trang).")
                    break

                current_target_url = pagination_info.get("next_url")
                page_num += 1
                await human_delay(2.5, 4.0)

            await human_delay(3.0, 5.0)

        await page.screenshot(path=STATUS_SCREENSHOT)
        log(f"\n📸 Đã lưu ảnh chụp trạng thái: {STATUS_SCREENSHOT}")
        await browser.close()

    # 4. Phân loại và lọc với Sổ cái Lịch sử
    new_unique_jobs = []
    already_seen_count = 0

    for job in all_session_extracted_jobs:
        u = job["clean_url"]
        if u in history_set:
            already_seen_count += 1
        else:
            new_unique_jobs.append(job)

    # 5. Lưu kết quả phiên hiện tại
    with open(SESSION_TXT, "w", encoding="utf-8") as f:
        for j in new_unique_jobs:
            f.write(j["clean_url"] + "\n")

    with open(SESSION_JSON, "w", encoding="utf-8") as f:
        json.dump(new_unique_jobs, f, indent=2, ensure_ascii=False)

    # 6. Cập nhật vào Sổ cái Lịch sử
    save_history(history_dict, new_unique_jobs)

    # 7. Báo cáo tổng kết
    log("\n==================================================")
    log("📊 BÁO CÁO TỔNG KẾT CA QUÉT VIỆC LÀM TOPCV")
    log("==================================================")
    log(f"✨ Tổng số việc làm quét được trong ca: {len(all_session_extracted_jobs)}")
    log(f"♻️  Số việc làm ĐÃ TỒN TẠI trong lịch sử: {already_seen_count}")
    log(f"🆕 Số việc làm MỚI TINH phát hiện:      {len(new_unique_jobs)}")
    log(f"📁 File việc làm mới phiên này (TXT):   {SESSION_TXT}")
    log(f"📁 File việc làm mới phiên này (JSON):  {SESSION_JSON}")
    log(f"🏛️  Sổ cái lịch sử toàn bộ (TXT):       {HISTORY_TXT} (Hiện có {len(history_dict)} việc làm)")
    log(f"🏛️  Sổ cái lịch sử toàn bộ (JSON):      {HISTORY_JSON}")
    log("==================================================")

if __name__ == "__main__":
    asyncio.run(run())
