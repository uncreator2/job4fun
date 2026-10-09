# Attempt Ledger

| Attempt ID | Phase | Timestamp | Action | Result | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| ATT-001 | INTAKE | 2026-09-18 11:41 | Initialize Host Profile & Planning Framework | PROVEN | macOS + GitHub Actions dual environments |
| ATT-002 | BUILD | 2026-09-21 09:48 | Fix VNW hydration/disabled button & V24H proxy ERR_CONNECTION_RESET | PROVEN | Local dry-runs passed for both VNW and V24H |
| ATT-003 | RESEARCH & PLAN | 2026-09-21 10:55 | Diagnose Vieclam24h search pagination fallback, modal async hydration timeout, and loop runaway | PROVEN | Formulate dual-layer role filtering, resilient modal wait, and loop bounding |
| ATT-004 | BUILD & TEST | 2026-09-21 11:01 | Implement v24h_filter, update crawler & applier, sanitize history ledgers | PROVEN | Local dry-run passed (2/2 jobs identified as management, modal opened, submit hydrated) |
| ATT-005 | INTAKE & PREFLIGHT | 2026-10-08 15:47 | CareerViet cookie extraction & canonical search URL reverse-engineering | PROVEN | Verified 57 jobs (GĐKD) and 74 jobs (TPKD) at Hà Nội kl4-vi.html via preflight spike |
| ATT-006 | BUILD & VALIDATE | 2026-10-08 16:05 | CareerViet apply engine, live apply test, dry-run & master cron orchestrator integration | PROVEN | Verified real apply on 35C86C84, dry-run 2/2 jobs, and run_pipeline.py 4th platform step |
| ATT-007 | VALIDATE & COMPLETE | 2026-10-08 16:20 | GitHub Actions Run #41 trigger, secrets injection, Ubuntu runner execution, artifact & ledger commit | PROVEN | Run #41 succeeded (1m 54s), processed dry-run jobs 35C884D3 & 35C89EB4, committed back to main |
| ATT-008 | RESEARCH & FIX | 2026-10-09 11:45 | Fix CareerViet post-apply detached DOM crash, TopCV NameError & Cloudflare 403, VNW stale jobs | PROVEN | Verified API 201 response, button state Đã Nộp Ứng Tuyển on live CareerViet, fixed scope in TopCV |
| ATT-009 | BUILD & OPTIMIZE | 2026-10-09 13:00 | Network/Proxy optimization: Direct IP for VNW/V24H; Route blocking & 5x speedup for TopCV | PROVEN | Isolated benchmarks prove 10-18x faster loads on Direct IP; TopCV drops from 18s to 2.91s |

