#!/usr/bin/env python3
"""
Multi-Platform Modular Test & Repair CLI Engine
Allows running fast, isolated tests on any single job platform (topcv, vietnamworks, careerviet, vieclam24h)
without triggering the entire multi-platform monolithic pipeline.
"""

import os
import sys
import json
import time
import socket
import urllib.request
import argparse
import subprocess
from datetime import datetime

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
TOPCV_DIR = os.path.join(ROOT_DIR, "topcv")
VNW_DIR = os.path.join(ROOT_DIR, "vietnamworks")
CV_DIR = os.path.join(ROOT_DIR, "careerviet")
V24H_DIR = os.path.join(ROOT_DIR, "vieclam24h")
SHARED_DIR = os.path.join(ROOT_DIR, "shared")

for d in [ROOT_DIR, SHARED_DIR, TOPCV_DIR, VNW_DIR, CV_DIR, V24H_DIR]:
    if os.path.exists(d) and d not in sys.path:
        sys.path.append(d)

from proxy_utils import get_proxy_config

SITE_CONFIGS = {
    "topcv": {
        "name": "TopCV",
        "dir": TOPCV_DIR,
        "url": "https://www.topcv.vn/",
        "search_url": "https://www.topcv.vn/tim-viec-lam-moi-nhat",
        "cookie_env": "COOKIES",
        "cookie_file": os.path.join(TOPCV_DIR, "cookies.txt"),
        "crawler_script": "topcv_cron_runner.py",
        "applier_script": "topcv_applier.py"
    },
    "vietnamworks": {
        "name": "VietnamWorks",
        "dir": VNW_DIR,
        "url": "https://www.vietnamworks.com/",
        "search_url": "https://www.vietnamworks.com/viec-lam?q=giam-doc-kinh-doanh",
        "cookie_env": "VNW_COOKIES",
        "cookie_file": os.path.join(VNW_DIR, "vietnamworks_cookies.json"),
        "crawler_script": "vnw_crawler.py",
        "applier_script": "vnw_applier.py"
    },
    "careerviet": {
        "name": "CareerViet",
        "dir": CV_DIR,
        "url": "https://careerviet.vn/",
        "search_url": "https://careerviet.vn/viec-lam/truong-phong-kinh-doanh-tai-ha-noi-kl4-vi.html",
        "cookie_env": "CAREERVIET_COOKIES",
        "cookie_file": os.path.join(CV_DIR, "careerviet_cookies.json"),
        "crawler_script": "cv_crawler.py",
        "applier_script": "cv_applier.py"
    },
    "vieclam24h": {
        "name": "Vieclam24h",
        "dir": V24H_DIR,
        "url": "https://vieclam24h.vn/",
        "search_url": "https://vieclam24h.vn/tim-kiem-viec-lam",
        "cookie_env": "V24H_COOKIES",
        "cookie_file": os.path.join(V24H_DIR, "vieclam24h_cookies.json"),
        "crawler_script": "v24h_crawler.py",
        "applier_script": "v24h_applier.py"
    }
}

def print_header(title):
    print("\n" + "=" * 65)
    print(f"  {title}")
    print("=" * 65)

def diagnose_site(site_key):
    cfg = SITE_CONFIGS[site_key]
    site_name = cfg["name"]
    print_header(f"🔍 BÁO CÁO CHẨN ĐOÁN HỆ THỐNG: {site_name.upper()}")

    results = {"site": site_name, "proxy": False, "auth": False, "http": False, "recommendations": []}

    # 1. Kiểm tra cấu hình Proxy
    proxy_cfg = get_proxy_config()
    if proxy_cfg:
        server = proxy_cfg.get("server", "")
        print(f"🌐 [PROXY] Cấu hình phát hiện: {server}")
        # Parse host & port
        host = server.replace("http://", "").replace("https://", "").split(":")[0]
        try:
            ip = socket.gethostbyname(host)
            print(f"   ✅ Phân giải DNS DDNS: {host} -> {ip}")
            results["proxy_dns"] = True
        except Exception as e:
            print(f"   ❌ Lỗi phân giải DNS cho proxy ({host}): {e}")
            results["recommendations"].append(f"Kiểm tra lại domain proxy hoặc kết nối DNS máy: {host}")

        # Test proxy HTTP request
        try:
            user = proxy_cfg.get("username")
            pwd = proxy_cfg.get("password")
            proxy_url = f"http://{user}:{pwd}@{host}:{server.split(':')[-1]}" if user and pwd else server
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({'http': proxy_url, 'https': proxy_url}))
            req = urllib.request.Request(
                cfg["url"],
                headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36'}
            )
            t0 = time.time()
            resp = opener.open(req, timeout=15)
            elapsed = time.time() - t0
            print(f"   ✅ Kết nối HTTP tới {cfg['url']} qua proxy thành công (Status: {resp.status}, Latency: {elapsed:.2f}s)")
            results["proxy"] = True
            results["http"] = True
        except Exception as e:
            print(f"   ⚠️ Thử nghiệm HTTP qua proxy cảnh báo: {e}")
            if "403" in str(e):
                print("   ℹ️ Lưu ý: Một số sàn (TopCV) kích hoạt Cloudflare cho urllib; Playwright với stealth sẽ xử lý bypass.")
                results["proxy"] = True
            else:
                results["recommendations"].append(f"Kiểm tra trạng thái proxy residential hoặc dùng Direct IP fallback nếu cần: {e}")
    else:
        print("🌐 [PROXY] Không cấu hình proxy (Sử dụng Direct IP)")
        results["proxy"] = True

    # 2. Kiểm tra Authentication (Cookies & Credentials)
    cookie_env = cfg["cookie_env"]
    cookie_val = os.environ.get(cookie_env, "").strip()
    cookie_file = cfg["cookie_file"]

    has_cookies = False
    if cookie_val:
        print(f"🔑 [AUTH] Phát hiện biến môi trường ${cookie_env} ({len(cookie_val)} ký tự)")
        has_cookies = True
    elif os.path.exists(cookie_file):
        print(f"🍪 [AUTH] Phát hiện file cookie cục bộ: {cookie_file} ({os.path.getsize(cookie_file)} bytes)")
        has_cookies = True
    else:
        print(f"⚠️ [AUTH] Không tìm thấy cookies trong ${cookie_env} hoặc {cookie_file}")
        results["recommendations"].append(f"Cung cấp cookies hợp lệ qua bí mật ${cookie_env} hoặc file {os.path.basename(cookie_file)}")

    results["auth"] = has_cookies

    # 3. Tổng kết & Đánh giá
    print("-" * 65)
    status_str = "🟢 KHỎE MẠNH (SẴN SÀNG CHẠY)" if results["auth"] else "🟡 CẦN KIỂM TRA LẠI THÔNG TIN ĐĂNG NHẬP"
    print(f"📋 ĐÁNH GIÁ CHUNG: {status_str}")
    if results["recommendations"]:
        print("🛠️ GỢI Ý SỬA CHỮA (REPAIR TIPS):")
        for idx, rec in enumerate(results["recommendations"], 1):
            print(f"   {idx}. {rec}")
    print("-" * 65)
    return results

def run_isolated_crawler(site_key):
    cfg = SITE_CONFIGS[site_key]
    site_dir = cfg["dir"]
    script = cfg["crawler_script"]
    print_header(f"🕷️ CHẠY CRAWLER KIỂM THỬ: {cfg['name']}")

    cmd = [sys.executable, script]
    if site_key == "topcv":
        cmd.extend(["--mode", "crawl_only"])

    print(f"▶️ Thực thi: {' '.join(cmd)} (tại {site_dir})")
    start = time.time()
    res = subprocess.run(cmd, cwd=site_dir)
    elapsed = time.time() - start
    if res.returncode == 0:
        print(f"✅ Crawler hoàn thành thành công trong {elapsed:.1f}s")
        return True
    else:
        print(f"❌ Crawler gặp lỗi với mã thoát {res.returncode} sau {elapsed:.1f}s")
        return False

def run_isolated_applier(site_key, max_jobs=1, dry_run=True):
    cfg = SITE_CONFIGS[site_key]
    site_dir = cfg["dir"]
    script = cfg["applier_script"]
    print_header(f"📨 CHẠY APPLIER KIỂM THỬ: {cfg['name']} (Quota: {max_jobs}, Dry-run: {dry_run})")

    cmd = [sys.executable, script, "--max", str(max_jobs)]
    if dry_run:
        cmd.append("--dry-run")

    print(f"▶️ Thực thi: {' '.join(cmd)} (tại {site_dir})")
    start = time.time()
    res = subprocess.run(cmd, cwd=site_dir)
    elapsed = time.time() - start
    if res.returncode == 0:
        print(f"✅ Applier hoàn thành thành công trong {elapsed:.1f}s")
        return True
    else:
        print(f"❌ Applier gặp lỗi với mã thoát {res.returncode} sau {elapsed:.1f}s")
        return False

def main():
    parser = argparse.ArgumentParser(description="Multi-Platform Modular Test & Repair CLI Engine")
    parser.add_argument("--site", choices=["topcv", "vietnamworks", "careerviet", "vieclam24h", "all"], required=True, help="Nền tảng muốn kiểm thử")
    parser.add_argument("--mode", choices=["diagnose", "crawl_test", "apply_test", "all"], default="diagnose", help="Chế độ kiểm thử (mặc định: diagnose)")
    parser.add_argument("--max", type=int, default=1, help="Số lượng việc làm kiểm thử nộp (mặc định: 1)")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Chế độ thử nghiệm không nộp thật (mặc định: True)")
    parser.add_argument("--real-apply", action="store_true", default=False, help="Bật nộp thật (ghi đè dry-run thành False)")

    args = parser.parse_args()
    dry_run = not args.real_apply

    sites_to_test = list(SITE_CONFIGS.keys()) if args.site == "all" else [args.site]

    print(f"🧪 KHỞI ĐỘNG CÔNG CỤ TEST & REPAIR: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🎯 Sàn mục tiêu: {[s.upper() for s in sites_to_test]} | Chế độ: {args.mode.upper()} | Dry-run: {dry_run}\n")

    summary = {}
    for site in sites_to_test:
        summary[site] = {}
        if args.mode in ["diagnose", "all"]:
            diag_res = diagnose_site(site)
            summary[site]["diagnose"] = diag_res

        if args.mode in ["crawl_test", "all"]:
            c_ok = run_isolated_crawler(site)
            summary[site]["crawler"] = c_ok

        if args.mode in ["apply_test", "all"]:
            a_ok = run_isolated_applier(site, max_jobs=args.max, dry_run=dry_run)
            summary[site]["applier"] = a_ok

    print_header("📊 TỔNG KẾT PHIÊN TEST & REPAIR")
    for site, report in summary.items():
        status_items = []
        for k, v in report.items():
            if isinstance(v, bool):
                status_items.append(f"{k}: {'OK ✅' if v else 'FAIL ❌'}")
            elif isinstance(v, dict):
                status_items.append("diagnose: HOÀN TẤT ✅")
        print(f"🏢 {site.upper():<15} -> {', '.join(status_items)}")
    print("=" * 65 + "\n")

if __name__ == "__main__":
    main()
