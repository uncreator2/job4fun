import asyncio
from datetime import datetime
import json
import os
import random
import re
import sys
import unicodedata
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
from proxy_utils import get_proxy_config

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
COOKIES_FILE = os.path.join(BASE_DIR, "topcv_cookies.json")
SESSION_JOBS_FILE = os.path.join(BASE_DIR, "session_extracted_jobs.txt")
HISTORY_TXT = os.path.join(BASE_DIR, "extracted_jobs_history.txt")
APPLIED_HISTORY_TXT = os.path.join(BASE_DIR, "applied_jobs_history.txt")
APPLIED_HISTORY_JSON = os.path.join(BASE_DIR, "applied_jobs_history.json")

# Candidate Profile (from N.P.H.H - QUANTUM OPERATIONS DOSSIER_VIE.pdf)
CANDIDATE = {
    "name": "Nguyễn Phú Hoàng Hà",
    "short_name": "Hoàng Hà",
    "phone": "0947.192.378",
    "email": "nphoangha@gmail.com",
    "core_title": "Giám đốc Quản lý Phát triển & Quy trình Kinh doanh",
    "experience_years": "hơn 8 năm"
}

def log(msg):
    print(msg, flush=True)

def normalize_text(text: str) -> str:
    if not text:
        return ""
    text = text.lower().strip()
    text = unicodedata.normalize("NFD", text)
    text = re.sub(r"[\u0300-\u036f]", "", text)
    return text.replace("đ", "d")

def generate_tailored_cover_letter(job_title: str, company_name: str, job_desc: str = "") -> str:
    norm_title = normalize_text(job_title)
    norm_desc = normalize_text(job_desc)
    combined = norm_title + " " + norm_desc

    # Phân loại chuyên môn phù hợp nhất
    if any(k in combined for k in ["san thuong mai", "tmdt", "ecommerce", "shopee", "tiktok", "lazada", "online"]):
        focus_domain = "quản trị và phát triển kênh Thương mại điện tử (Shopee, TikTok Shop, B2C/B2B)"
        highlight_skill = "xây dựng quy trình tiếp thị số năng động, tối ưu hóa tỷ lệ chuyển đổi và quản lý vận hành gian hàng đa kênh"
    elif any(k in combined for k in ["nuoc ngoai", "quoc te", "global", "export", "xuat khau", "fdi", "xuyen bien gioi"]):
        focus_domain = "kinh doanh quốc tế và phát triển đối tác chiến lược xuyên biên giới"
        highlight_skill = "chỉ đạo các thỏa thuận triệu đô, tối ưu hóa tỷ lệ thâm nhập thị trường mục tiêu và điều phối kênh phân phối toàn cầu"
    elif any(k in combined for k in ["giam doc", "director", "truong phong", "head", "quan ly", "manager", "leader"]):
        focus_domain = "hoạch định chiến lược kinh doanh và tái cấu trúc quy trình vận hành"
        highlight_skill = "dẫn dắt đội ngũ tinh gọn, tự động hóa quy trình quản lý khách hàng và thúc đẩy doanh số bền vững"
    else:
        focus_domain = "phát triển kinh doanh và quản lý tài khoản doanh nghiệp chiến lược (Key Account Management)"
        highlight_skill = "mở rộng tệp khách hàng đối tác lớn, hợp lý hóa biểu phí ngân sách và kiến tạo dòng tiền tăng trưởng"

    letter = (
        f"Kính gửi Quý Nhà tuyển dụng {company_name or 'Quý Công ty'},\n\n"
        f"Tôi là {CANDIDATE['short_name']}. Với {CANDIDATE['experience_years']} kinh nghiệm chuyên sâu trong {focus_domain}, "
        f"tôi rất quan tâm và tự tin đáp ứng xuất sắc các mục tiêu của vị trí {job_title}.\n\n"
        f"Thế mạnh nổi bật của tôi là {highlight_skill}, kết hợp khả năng chuẩn hóa quy trình và ứng dụng công nghệ để nâng cao hiệu suất làm việc. "
        f"Tôi đã đính kèm hồ sơ chi tiết và rất mong có cơ hội trao đổi trực tiếp cùng Quý công ty.\n\n"
        f"Trân trọng,\n"
        f"{CANDIDATE['name']} - {CANDIDATE['phone']}"
    )
    return letter

def load_applied_history():
    applied_set = set()
    applied_dict = {}

    if os.path.exists(APPLIED_HISTORY_TXT):
        try:
            with open(APPLIED_HISTORY_TXT, "r", encoding="utf-8") as f:
                applied_set = {line.strip() for line in f if line.strip()}
        except Exception:
            pass

    if os.path.exists(APPLIED_HISTORY_JSON):
        try:
            with open(APPLIED_HISTORY_JSON, "r", encoding="utf-8") as f:
                applied_dict = json.load(f)
                for k in applied_dict.keys():
                    applied_set.add(k)
        except Exception:
            pass

    return applied_set, applied_dict

def save_applied_record(applied_dict, job_url, title, company, letter, proof_path=""):
    applied_dict[job_url] = {
        "job_url": job_url,
        "title": title,
        "company": company,
        "applied_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "cover_letter": letter,
        "proof_screenshot": proof_path
    }
    with open(APPLIED_HISTORY_JSON, "w", encoding="utf-8") as f:
        json.dump(applied_dict, f, indent=2, ensure_ascii=False)

    with open(APPLIED_HISTORY_TXT, "a", encoding="utf-8") as f:
        f.write(job_url + "\n")

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
                log(f"[*] Đã nạp {len(formatted)} cookies vào phiên.")
                return True
        except Exception as e:
            log(f"[!] Lỗi nạp cookies: {e}")
    return False

async def apply_to_single_job(page, job_url: str, dry_run: bool = False) -> dict:
    log(f"\n==================================================")
    log(f"🎯 BẮT ĐẦU XỬ LÝ ỨNG TUYỂN: {job_url}")
    log(f"==================================================")

    try:
        await page.goto(job_url, wait_until="domcontentloaded", timeout=35000)
        await asyncio.sleep(2.5)
    except Exception as e:
        log(f"[!] Lỗi tải trang việc làm: {e}")
        return {"status": "ERROR", "reason": f"Page load error: {e}"}

    # 1. Kiểm tra xem có bị Cloudflare chặn hoặc challenge không
    for _ in range(3):
        is_cf = await page.evaluate("document.body.innerText.includes('Sorry, you have been blocked') || document.body.innerText.includes('Just a moment...')")
        if not is_cf:
            break
        log("⏳ Phát hiện trang chờ Cloudflare, đang chờ giải mã (3s)...")
        await asyncio.sleep(3.0)

    # Trích xuất thông tin việc làm từ trang
    job_info = await page.evaluate("""() => {
        const titleEl = document.querySelector('h1.job-detail__info--title, .job-detail-info h1, h1');
        const compEl = document.querySelector('.company-name, .company-title, a.company');
        const descEl = document.querySelector('.job-description, #job-description, .job-data');
        const applyBtn = document.querySelector('a.btn-apply, button.btn-apply, a.open-apply-modal, a.btn-apply-job, .btn-action-job.btn-apply');
        const alreadyApplied = document.body.innerText.includes('Đã ứng tuyển') || (applyBtn && applyBtn.innerText.includes('Đã ứng tuyển'));
        const bodyText = document.body.innerText;
        const isBlocked = bodyText.includes('Sorry, you have been blocked') || bodyText.includes('Just a moment...');

        return {
            title: titleEl ? titleEl.innerText.trim() : document.title,
            company: compEl ? compEl.innerText.trim() : '',
            description: descEl ? descEl.innerText.slice(0, 800) : '',
            hasApplyBtn: !!applyBtn,
            applyBtnText: applyBtn ? applyBtn.innerText.trim() : '',
            alreadyApplied: !!alreadyApplied,
            isBlocked: isBlocked
        };
    }""")

    if job_info.get("isBlocked"):
        log("❌ Cloudflare chặn truy cập vào URL này trên IP runner.")
        return {"status": "CF_BLOCKED", "title": job_info["title"]}

    log(f"📋 Vị trí: {job_info['title']}")
    log(f"🏢 Công ty: {job_info['company']}")

    if job_info["alreadyApplied"]:
        log("ℹ️ Việc làm này ĐÃ ỨNG TUYỂN trước đó. Bỏ qua.")
        return {"status": "ALREADY_APPLIED", "title": job_info["title"]}

    if not job_info["hasApplyBtn"]:
        log("⚠️ Không tìm thấy nút ứng tuyển (có thể việc làm đã đóng hoặc hết hạn).")
        return {"status": "NO_APPLY_BTN", "title": job_info["title"]}

    # 2. Bấm nút Ứng tuyển ngay để mở Modal
    log("🚀 Nhấn nút 'Ứng tuyển ngay'...")
    await page.evaluate("""() => {
        const btns = Array.from(document.querySelectorAll('a.open-apply-modal, a.btn-apply, a.btn-apply-job, .btn-action-job.btn-apply, button.btn-apply'));
        const visibleBtn = btns.find(b => b.offsetWidth > 0 && b.offsetHeight > 0) || btns[0];
        if (visibleBtn) visibleBtn.click();
    }""")
    await asyncio.sleep(2.0)

    # 3. Chờ Modal hiển thị
    modal_opened = await page.evaluate("""() => {
        const modal = document.querySelector('#modal-apply-cv, #modal-apply, .modal.in, .modal.show');
        return modal ? (modal.offsetWidth > 0 && modal.offsetHeight > 0) : false;
    }""")

    if not modal_opened:
        log("❌ Modal ứng tuyển không mở được.")
        return {"status": "MODAL_NOT_OPENED", "title": job_info["title"]}

    log("✅ Modal ứng tuyển đã mở thành công.")

    # 4. Tạo thư giới thiệu phù hợp
    cover_letter = generate_tailored_cover_letter(job_info["title"], job_info["company"], job_info["description"])
    log("✍️  Thư giới thiệu sinh ra:\n" + "-"*40 + "\n" + cover_letter + "\n" + "-"*40)

    # 5. Điền form trong Modal: Chọn CV, cuộn trang, điền thư, tích đồng ý
    log("⚙️  Đang chọn CV, cuộn modal, điền thư giới thiệu và tích điều khoản...")
    fill_result = await page.evaluate(f"""(() => {{
        const modal = document.querySelector('#modal-apply-cv, #modal-apply');
        if (!modal) return {{ success: false, reason: 'No modal' }};

        // 1. Đảm bảo chọn CV gần nhất (N_P_H_H_Quantum_Operations_Dossier_VI.pdf)
        const lastCvRadio = modal.querySelector('.list-cvs_item.is-last-apply input[type=radio], input[name=cvid]');
        if (lastCvRadio && !lastCvRadio.checked) {{
            lastCvRadio.click();
        }}

        // 2. Cuộn nội dung Modal xuống phần thư giới thiệu
        const modalBody = modal.querySelector('.modal-body') || modal;
        modalBody.scrollTop = 650;

        // 3. Điền thư giới thiệu
        const letterTextarea = modal.querySelector('#letter, textarea[name=letter]');
        if (letterTextarea) {{
            letterTextarea.value = {json.dumps(cover_letter)};
            letterTextarea.dispatchEvent(new Event('input', {{ bubbles: true }}));
            letterTextarea.dispatchEvent(new Event('change', {{ bubbles: true }}));
        }}

        // 4. Tích điều khoản bảo vệ dữ liệu cá nhân (BẮT BUỘC)
        const privacyCb = modal.querySelector('#input-employer-data-protection, input[name=is-confirm-data-protection]');
        if (privacyCb && !privacyCb.checked) {{
            privacyCb.click();
        }}

        const submitBtn = modal.querySelector('#btn-apply, button[type=submit].btn-theme');

        return {{
            success: true,
            cvChecked: lastCvRadio ? lastCvRadio.checked : false,
            letterLength: letterTextarea ? letterTextarea.value.length : 0,
            privacyChecked: privacyCb ? privacyCb.checked : false,
            submitBtnReady: submitBtn ? !submitBtn.disabled : false
        }};
    }})()""")

    log(f"   Trạng thái điền form: {fill_result}")
    await asyncio.sleep(1.5)

    # 6. Chế độ Thử nghiệm (Dry-Run) hay Nộp thật
    clean_job_id = re.search(r"/(\d+)\.html", job_url)
    job_id_str = clean_job_id.group(1) if clean_job_id else str(random.randint(1000, 9999))
    proof_path = os.path.join(BASE_DIR, f"apply_proof_{job_id_str}.png")

    if dry_run:
        log("🛡️  CHẾ ĐỘ DRY-RUN: Đã chuẩn bị sẵn sàng toàn bộ form, KHÔNG bấm Nộp thật.")
        await page.screenshot(path=proof_path)
        log(f"📸 Đã lưu ảnh chụp trạng thái sẵn sàng: {proof_path}")
        return {
            "status": "DRY_RUN_READY",
            "title": job_info["title"],
            "company": job_info["company"],
            "letter": cover_letter,
            "proof": proof_path
        }

    # 7. BẤM NỘP HỒ SƠ ỨNG TUYỂN
    log("🚀 Nhấn nút 'Nộp hồ sơ ứng tuyển'...")
    await page.click("#modal-apply-cv #btn-apply, #btn-apply")
    log("⏳ Đang chờ xác nhận từ hệ thống TopCV...")
    await asyncio.sleep(6.0)

    # Kiểm tra xác nhận thành công
    submit_status = {"isSuccess": True, "alertMsg": ""}
    try:
        submit_status = await page.evaluate("""() => {
            const bodyText = document.body ? document.body.innerText : "";
            const isSuccess = bodyText.includes('Ứng tuyển thành công') ||
                              bodyText.includes('Hồ sơ của bạn đã được gửi') ||
                              bodyText.includes('Đã ứng tuyển') ||
                              !!document.querySelector('.modal-apply-success, #modal-apply-success');
            const alertMsg = document.querySelector('.alert, .toast-message, .error-message')?.innerText?.trim() || "";
            return { isSuccess, alertMsg };
        }""")
    except Exception as e:
        log(f"[*] Trang đã chuyển hướng hoặc tải lại sau khi nộp (Navigation confirmed): {e}")

    try:
        await page.screenshot(path=proof_path)
        log(f"📸 Đã lưu ảnh chụp kết quả: {proof_path}")
    except Exception as e:
        log(f"[!] Warning screenshot: {e}")

    log(f"🎉 KẾT QUẢ ỨNG TUYỂN: {'THÀNH CÔNG RỰC RỠ' if submit_status.get('isSuccess') else 'ĐÃ GỬI (Chờ kiểm tra)'}")
    return {
        "status": "SUCCESS" if submit_status.get("isSuccess") else "SUBMITTED",
        "title": job_info["title"],
        "company": job_info["company"],
        "letter": cover_letter,
        "proof": proof_path
    }

async def run():
    target_url = os.environ.get("APPLY_JOB_URL", "").strip()
    dry_run = os.environ.get("DRY_RUN", "false").lower() == "true"
    max_applies = int(os.environ.get("MAX_APPLIES", "100"))

    applied_set, applied_dict = load_applied_history()
    log(f"📚 Sổ cái các việc làm đã ứng tuyển: {len(applied_set)} việc làm.")

    # Danh sách URL cần ứng tuyển
    jobs_to_apply = []
    if target_url:
        jobs_to_apply = [target_url]
    else:
        # 1. Ưu tiên các việc làm mới vừa quét trong phiên này
        if os.path.exists(SESSION_JOBS_FILE):
            with open(SESSION_JOBS_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    u = line.strip()
                    if u and u not in applied_set and u not in jobs_to_apply:
                        jobs_to_apply.append(u)
                        if len(jobs_to_apply) >= max_applies:
                            break

        # 2. Nếu chưa đủ số lượng ca này, lấy thêm các việc làm chưa ứng tuyển từ kho lịch sử
        if len(jobs_to_apply) < max_applies and os.path.exists(HISTORY_TXT):
            with open(HISTORY_TXT, "r", encoding="utf-8") as f:
                for line in f:
                    u = line.strip()
                    if u and u not in applied_set and u not in jobs_to_apply:
                        jobs_to_apply.append(u)
                        if len(jobs_to_apply) >= max_applies:
                            break

    if not jobs_to_apply:
        log("🎉 Tất cả việc làm trong kho lưu trữ đều đã được ứng tuyển hoặc chưa có việc làm mới nào cần nộp!")
        return

    log(f"🎯 Số việc làm sẽ thực hiện trong ca này: {len(jobs_to_apply)}")

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
        proxy_config = get_proxy_config()
        if proxy_config:
            log(f"🌐 Đã cấu hình Residential/4G Proxy: {proxy_config.get('server')}")

        context_kwargs = {
            "viewport": {"width": 1440, "height": 900},
            "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36",
            "locale": "vi-VN",
            "timezone_id": "Asia/Ho_Chi_Minh"
        }
        if proxy_config:
            context_kwargs["proxy"] = proxy_config

        context = await browser.new_context(**context_kwargs)
        page = await context.new_page()
        try:
            stealth = Stealth()
            await stealth.apply_stealth_async(page)
            log("[*] Đã kích hoạt chế độ chống nhận diện Bot (Playwright Stealth).")
        except Exception as e:
            log(f"[!] Warning stealth: {e}")

        await inject_cookies(context)

        for idx, job_url in enumerate(jobs_to_apply, 1):
            log(f"\n==================================================")
            log(f"📌 [{idx}/{len(jobs_to_apply)}] TIẾN TRÌNH: {job_url}")
            try:
                res = await apply_to_single_job(page, job_url, dry_run=dry_run)
                if res.get("status") in ["SUCCESS", "SUBMITTED"]:
                    save_applied_record(applied_dict, job_url, res.get("title", ""), res.get("company", ""), res.get("letter", ""), res.get("proof", ""))
                elif res.get("status") == "ALREADY_APPLIED":
                    save_applied_record(applied_dict, job_url, res.get("title", ""), "", "Đã ứng tuyển trước đó trên TopCV", "")
            except Exception as e:
                log(f"❌ Lỗi khi xử lý job {job_url}: {e}. Tự động bỏ qua và chuyển sang job tiếp theo.")
            await asyncio.sleep(random.uniform(4.0, 7.0))

        await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
