import os
import sys
import subprocess
import argparse
from datetime import datetime

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
TOPCV_DIR = os.path.join(ROOT_DIR, "topcv")
VNW_DIR = os.path.join(ROOT_DIR, "vietnamworks")
V24H_DIR = os.path.join(ROOT_DIR, "vieclam24h")

def run_step(cmd, cwd, description):
    print(f"\n=======================================================")
    print(f"▶️  {description}")
    print(f"📁 Thư mục: {cwd}")
    print(f"💻 Lệnh: {' '.join(cmd)}")
    print(f"=======================================================")
    start_time = datetime.now()
    res = subprocess.run(cmd, cwd=cwd)
    elapsed = (datetime.now() - start_time).total_seconds()
    if res.returncode == 0:
        print(f"✅ Hoàn thành trong {elapsed:.1f}s")
        return True
    else:
        print(f"⚠️ Thất bại với exit code {res.returncode} (sau {elapsed:.1f}s)")
        return False

def main():
    parser = argparse.ArgumentParser(description="Multi-Platform Automated Job Pipeline Orchestrator")
    parser.add_argument("--platform", choices=["all", "topcv", "vietnamworks", "vieclam24h"], default="all", help="Nền tảng muốn chạy (mặc định: all)")
    parser.add_argument("--max", type=int, default=100, help="Số lượng việc làm tối đa nộp mỗi sàn (mặc định: 100)")
    parser.add_argument("--dry-run", action="store_true", default=False, help="Chế độ thử nghiệm không nộp thật")
    args = parser.parse_args()

    print(f"🚀 KHỞI ĐỘNG PIPELINE ĐA NỀN TẢNG: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"⚙️  Nền tảng: {args.platform.upper()} | Quota mỗi sàn: {args.max} | Dry-run: {args.dry_run}\n")

    summary = {}

    # 1. TOPCV
    if args.platform in ["all", "topcv"]:
        print("\n" + "#" * 60)
        print("🏢 [BƯỚC 1/3] XỬ LÝ PHÂN HỆ TOPCV")
        print("#" * 60)

        # Crawl
        c_ok = run_step(
            [sys.executable, "topcv_cron_runner.py", "--mode", "crawl_only"],
            cwd=TOPCV_DIR,
            description="TopCV: Quét việc làm mới"
        )
        # Apply
        apply_cmd = [sys.executable, "topcv_applier.py", "--max", str(args.max)]
        if args.dry_run:
            apply_cmd.append("--dry-run")
        a_ok = run_step(
            apply_cmd,
            cwd=TOPCV_DIR,
            description="TopCV: Nộp đơn việc làm chưa nộp"
        )
        summary["TopCV"] = {"crawled": c_ok, "applied": a_ok}

    # 2. VIETNAMWORKS
    if args.platform in ["all", "vietnamworks"]:
        print("\n" + "#" * 60)
        print("🏢 [BƯỚC 2/3] XỬ LÝ PHÂN HỆ VIETNAMWORKS")
        print("#" * 60)

        # Crawl
        c_ok = run_step(
            [sys.executable, "vnw_crawler.py"],
            cwd=VNW_DIR,
            description="VietnamWorks: Quét việc làm mới"
        )
        # Apply
        apply_cmd = [sys.executable, "vnw_applier.py", "--max", str(args.max)]
        if args.dry_run:
            apply_cmd.append("--dry-run")
        a_ok = run_step(
            apply_cmd,
            cwd=VNW_DIR,
            description="VietnamWorks: Nộp đơn việc làm chưa nộp"
        )
        summary["VietnamWorks"] = {"crawled": c_ok, "applied": a_ok}

    # 3. VIECLAM24H
    if args.platform in ["all", "vieclam24h"]:
        print("\n" + "#" * 60)
        print("🏢 [BƯỚC 3/3] XỬ LÝ PHÂN HỆ VIECLAM24H")
        print("#" * 60)

        # Crawl
        c_ok = run_step(
            [sys.executable, "v24h_crawler.py"],
            cwd=V24H_DIR,
            description="Vieclam24h: Quét việc làm mới"
        )
        # Apply
        apply_cmd = [sys.executable, "v24h_applier.py", "--max", str(args.max)]
        if args.dry_run:
            apply_cmd.append("--dry-run")
        a_ok = run_step(
            apply_cmd,
            cwd=V24H_DIR,
            description="Vieclam24h: Nộp đơn việc làm chưa nộp"
        )
        summary["Vieclam24h"] = {"crawled": c_ok, "applied": a_ok}

    print("\n" + "=" * 60)
    print("📊 BÁO CÁO TỔNG KẾT PIPELINE HOÀN TẤT")
    print("=" * 60)
    for platform, status in summary.items():
        c_str = "Thành công ✅" if status["crawled"] else "Lỗi ❌"
        a_str = "Thành công ✅" if status["applied"] else "Lỗi ❌"
        print(f"🏢 {platform:<15} | Quét mới: {c_str:<12} | Nộp đơn: {a_str}")
    print("=" * 60 + "\n")

if __name__ == "__main__":
    main()
