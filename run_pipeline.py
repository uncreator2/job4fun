import os
import sys
import json
import subprocess
import argparse
from datetime import datetime

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
TOPCV_DIR = os.path.join(ROOT_DIR, "topcv")
VNW_DIR = os.path.join(ROOT_DIR, "vietnamworks")
V24H_DIR = os.path.join(ROOT_DIR, "vieclam24h")
CV_DIR = os.path.join(ROOT_DIR, "careerviet")

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

def print_platform_detailed_report(platform_name, platform_dir, status):
    print("\n" + "=" * 70)
    print(f"📊 BÁO CÁO THỰC TẾ CHI TIẾT CA CHẠY: {platform_name.upper()}")
    print("=" * 70)

    if status.get("skipped_limit"):
        print(f"🛑 Trạng thái: Đã kích hoạt cờ giới hạn ngày hôm nay.")
        print(f"   ⏩ Tự động bỏ qua ca chạy để bảo vệ tài khoản.")
        print("=" * 70 + "\n")
        return {"todo": 0, "applied": 0, "skipped_limit": True, "label": "Giới hạn ngày 🛑"}

    report_path = os.path.join(platform_dir, "session_report.json")
    if os.path.exists(report_path):
        try:
            with open(report_path, "r", encoding="utf-8") as f:
                rep = json.load(f)

            todo = rep.get("todo_count", 0)
            applied = rep.get("applied_count", 0)
            applied_jobs = rep.get("applied_jobs", [])
            skipped = rep.get("skipped_counts", {})
            cf_blocked = skipped.get("cf_blocked", 0)

            print(f"🎯 Danh sách việc làm To-Do (cần nộp ca này): {todo} việc làm")
            if applied > 0:
                print(f"✅ ĐÃ NỘP THÀNH CÔNG: {applied}/{todo} việc làm:")
                for idx, j in enumerate(applied_jobs, 1):
                    title = j.get("title", "Chưa có tiêu đề")
                    comp = f" - {j.get('company')}" if j.get("company") else ""
                    url = j.get("url", "")
                    proof = f" (Minh chứng: {j.get('proof')})" if j.get("proof") else ""
                    print(f"   {idx}. [{title}]{comp}")
                    print(f"      🔗 {url}{proof}")
            else:
                print(f"❌ ĐÃ NỘP THÀNH CÔNG: 0 việc làm.")

            print(f"\n⏭️ Thống kê chi tiết các việc làm bỏ qua / không nộp:")
            print(f"   - Đã từng ứng tuyển trước đó (chống spam):  {skipped.get('already_applied', 0)} việc làm")
            print(f"   - Tin tuyển dụng hết hạn / đã đóng:        {skipped.get('expired', 0)} việc làm")
            print(f"   - Bị Cloudflare WAF chặn:                  {cf_blocked} việc làm")
            print(f"   - Đạt giới hạn tài khoản trong ngày:      {skipped.get('daily_limit', 0)} việc làm")
            print(f"   - Lỗi kỹ thuật / nộp form:                 {skipped.get('errors', 0)} việc làm")
            print("=" * 70 + "\n")

            if applied > 0 and applied == todo:
                label = f"Nộp đủ {applied}/{todo} 🎯"
            elif applied > 0:
                label = f"Nộp {applied}/{todo} ✅"
            elif cf_blocked > 0:
                label = f"Chặn WAF ({cf_blocked}) ⚠️"
            elif todo == 0:
                label = "To-Do trống ⏸️"
            else:
                label = f"Chưa nộp ({applied}/{todo}) ⚠️"

            return {
                "todo": todo,
                "applied": applied,
                "skipped_total": sum(skipped.values()),
                "cf_blocked": cf_blocked,
                "label": label
            }
        except Exception as e:
            print(f"⚠️ Lỗi phân tích {report_path}: {e}")

    # Fallback
    print(f"⚠️ Không tìm thấy session_report.json cho {platform_name}.")
    print(f"   - Tiến trình Quét: {'Thành công' if status.get('crawled') else 'Thất bại'}")
    print(f"   - Tiến trình Nộp:  {'Thành công' if status.get('applied') else 'Thất bại'}")
    print("=" * 70 + "\n")
    return {"todo": 0, "applied": 0, "label": "Chưa có báo cáo"}

def main():
    parser = argparse.ArgumentParser(description="Multi-Platform Automated Job Pipeline Orchestrator")
    parser.add_argument("--platform", choices=["all", "topcv", "vietnamworks", "vieclam24h", "careerviet"], default="all", help="Nền tảng muốn chạy (mặc định: all)")
    parser.add_argument("--max", type=int, default=30, help="Số lượng việc làm tối đa nộp mỗi sàn (mặc định: 30)")
    parser.add_argument("--dry-run", action="store_true", default=False, help="Chế độ thử nghiệm không nộp thật")
    args = parser.parse_args()

    print(f"🚀 KHỞI ĐỘNG PIPELINE ĐA NỀN TẢNG: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"⚙️  Nền tảng: {args.platform.upper()} | Quota mỗi sàn: {args.max} | Dry-run: {args.dry_run}\n")

    summary = {}

    # 1. TOPCV
    if args.platform in ["all", "topcv"]:
        print("\n" + "#" * 60)
        print("🏢 [BƯỚC 1/4] XỬ LÝ PHÂN HỆ TOPCV")
        print("#" * 60)

        from datetime import timezone, timedelta
        vn_tz = timezone(timedelta(hours=7))
        today_str = datetime.now(vn_tz).strftime("%Y-%m-%d")
        limit_flag = os.path.join(TOPCV_DIR, f"topcv_daily_limit_{today_str}.flag")

        if os.path.exists(limit_flag):
            print(f"🛑 [BỎ QUA TOPCV] Phát hiện cờ giới hạn tài khoản TopCV ngày {today_str}.")
            print("   Lý do: 'Tài khoản của bạn có dấu hiệu bất thường, vui lòng quay lại ứng tuyển vào ngày mai'.")
            print("   ⏩ Tự động bỏ qua TopCV ca này và chuyển sang các sàn tiếp theo!\n")
            summary["TopCV"] = {"crawled": True, "applied": True, "skipped_limit": True, "dir": TOPCV_DIR}
        else:
            c_ok = run_step(
                [sys.executable, "topcv_cron_runner.py", "--mode", "crawl_only"],
                cwd=TOPCV_DIR,
                description="TopCV: Quét việc làm mới"
            )
            apply_cmd = [sys.executable, "topcv_applier.py", "--max", str(args.max)]
            if args.dry_run:
                apply_cmd.append("--dry-run")
            a_ok = run_step(
                apply_cmd,
                cwd=TOPCV_DIR,
                description="TopCV: Nộp đơn việc làm chưa nộp"
            )
            summary["TopCV"] = {"crawled": c_ok, "applied": a_ok, "dir": TOPCV_DIR}

        print_platform_detailed_report("TopCV", TOPCV_DIR, summary["TopCV"])

    # 2. VIETNAMWORKS
    if args.platform in ["all", "vietnamworks"]:
        print("\n" + "#" * 60)
        print("🏢 [BƯỚC 2/4] XỬ LÝ PHÂN HỆ VIETNAMWORKS")
        print("#" * 60)

        c_ok = run_step(
            [sys.executable, "vnw_crawler.py"],
            cwd=VNW_DIR,
            description="VietnamWorks: Quét việc làm mới"
        )
        apply_cmd = [sys.executable, "vnw_applier.py", "--max", str(args.max)]
        if args.dry_run:
            apply_cmd.append("--dry-run")
        a_ok = run_step(
            apply_cmd,
            cwd=VNW_DIR,
            description="VietnamWorks: Nộp đơn việc làm chưa nộp"
        )
        summary["VietnamWorks"] = {"crawled": c_ok, "applied": a_ok, "dir": VNW_DIR}

        print_platform_detailed_report("VietnamWorks", VNW_DIR, summary["VietnamWorks"])

    # 3. VIECLAM24H
    if args.platform in ["all", "vieclam24h"]:
        print("\n" + "#" * 60)
        print("🏢 [BƯỚC 3/4] XỬ LÝ PHÂN HỆ VIECLAM24H")
        print("#" * 60)

        c_ok = run_step(
            [sys.executable, "v24h_crawler.py"],
            cwd=V24H_DIR,
            description="Vieclam24h: Quét việc làm mới"
        )
        apply_cmd = [sys.executable, "v24h_applier.py", "--max", str(args.max)]
        if args.dry_run:
            apply_cmd.append("--dry-run")
        a_ok = run_step(
            apply_cmd,
            cwd=V24H_DIR,
            description="Vieclam24h: Nộp đơn việc làm chưa nộp"
        )
        summary["Vieclam24h"] = {"crawled": c_ok, "applied": a_ok, "dir": V24H_DIR}

        print_platform_detailed_report("Vieclam24h", V24H_DIR, summary["Vieclam24h"])

    # 4. CAREERVIET
    if args.platform in ["all", "careerviet"]:
        print("\n" + "#" * 60)
        print("🏢 [BƯỚC 4/4] XỬ LÝ PHÂN HỆ CAREERVIET")
        print("#" * 60)

        c_ok = run_step(
            [sys.executable, "cv_crawler.py"],
            cwd=CV_DIR,
            description="CareerViet: Quét việc làm mới"
        )
        apply_cmd = [sys.executable, "cv_applier.py", "--max", str(args.max)]
        if args.dry_run:
            apply_cmd.append("--dry-run")
        a_ok = run_step(
            apply_cmd,
            cwd=CV_DIR,
            description="CareerViet: Nộp đơn việc làm chưa nộp"
        )
        summary["CareerViet"] = {"crawled": c_ok, "applied": a_ok, "dir": CV_DIR}

        print_platform_detailed_report("CareerViet", CV_DIR, summary["CareerViet"])

    # BẢNG TỔNG KẾT MINH BẠCH CUỐI CÙNG
    print("\n" + "=" * 80)
    print("📊 BẢNG TỔNG KẾT VẬN HÀNH TOÀN BỘ SÀN (SỐ LIỆU THỰC TẾ MINH BẠCH)")
    print("=" * 80)
    for platform, status in summary.items():
        p_dir = status.get("dir", "")
        rep_path = os.path.join(p_dir, "session_report.json")
        todo_cnt = 0
        app_cnt = 0
        lbl = "Hoàn thành"
        if status.get("skipped_limit"):
            lbl = "Giới hạn ngày 🛑"
        elif os.path.exists(rep_path):
            try:
                with open(rep_path, "r", encoding="utf-8") as f:
                    r_data = json.load(f)
                todo_cnt = r_data.get("todo_count", 0)
                app_cnt = r_data.get("applied_count", 0)
                cf_cnt = r_data.get("skipped_counts", {}).get("cf_blocked", 0)
                if cf_cnt > 0:
                    lbl = f"Chặn WAF ({cf_cnt}) ⚠️"
                elif app_cnt > 0:
                    lbl = f"Nộp {app_cnt}/{todo_cnt} ✅"
                elif todo_cnt == 0:
                    lbl = "To-Do trống ⏸️"
                else:
                    lbl = f"Chưa nộp (0/{todo_cnt}) ⚠️"
            except Exception:
                pass

        print(f"🏢 {platform:<14} | To-Do: {todo_cnt:<3} | Nộp thành công: {app_cnt:<3} | Trạng thái: {lbl}")
    print("=" * 80 + "\n")

if __name__ == "__main__":
    main()
