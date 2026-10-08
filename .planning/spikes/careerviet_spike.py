import os
import sys
import json
import asyncio
from playwright.async_api import async_playwright

async def run_spike():
    print("=== CAREERVIET PREFLIGHT SPIKE ===")
    
    # 1. Connect to CDP to extract cookies
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp('http://127.0.0.1:9223')
        context = browser.contexts[0]
        cookies = await context.cookies()
        cv_cookies = [c for c in cookies if 'careerviet.vn' in c['domain']]
        print(f"[OK] Extracted {len(cv_cookies)} CareerViet cookies from active session.")
        
        # 2. Test search parsing on first page of Giám đốc kinh doanh Hà Nội
        page = await context.new_page()
        test_url = "https://careerviet.vn/viec-lam/giam-doc-kinh-doanh-tai-ha-noi-kl4-vi.html"
        print(f"[INFO] Navigating to {test_url}...")
        await page.goto(test_url, wait_until="domcontentloaded")
        await asyncio.sleep(2)
        
        job_cards = await page.locator('.job-item').all()
        print(f"[OK] Found {len(job_cards)} job cards on page 1.")
        
        extracted = []
        for card in job_cards[:5]:
            title_el = card.locator('.job-title a, a.job_link').first
            title = (await title_el.inner_text()).strip() if await title_el.count() > 0 else ""
            href = await title_el.get_attribute('href') if await title_el.count() > 0 else ""
            if href and not href.startswith("http"):
                href = f"https://careerviet.vn{href}"
                
            comp_el = card.locator('.company-name a, .company-name').first
            comp = (await comp_el.inner_text()).strip() if await comp_el.count() > 0 else ""
            
            salary_el = card.locator('.salary, .job-salary').first
            salary = (await salary_el.inner_text()).strip() if await salary_el.count() > 0 else ""
            
            loc_el = card.locator('.location, .job-location').first
            loc = (await loc_el.inner_text()).strip().replace("\n", ", ") if await loc_el.count() > 0 else ""
            
            extracted.append({
                "title": title,
                "url": href,
                "company": comp,
                "salary": salary,
                "location": loc
            })
            
        print(f"[OK] Sample 5 extracted jobs:\n{json.dumps(extracted, ensure_ascii=False, indent=2)}")
        await page.close()
        
    print("=== SPIKE COMPLETE: SUCCESS ===")

if __name__ == "__main__":
    asyncio.run(run_spike())
