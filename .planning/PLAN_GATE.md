# Plan Verification Gate

- **Task**: Cross-Platform Applier Fixes (CareerViet DOM Detach, TopCV NameError & Cloudflare, VNW Stale Filter, Proxy Fallback)
- **Certainty Tier**: `T1-VERIFIED-STANDARD` (TopCV NameError scope, VNW stale job filter, proxy fallback) + `T2-WEB-GROUNDED` (CareerViet client-side redirect handling, TopCV Cloudflare circuit breaker)
- **Spike / Evidence Status**: `PROVEN`
  - CareerViet: Verified live submission succeeds with API HTTP 201 (`/api/v1/jss/jsk/apply-jobs/{job_id}`) and button transitions to `Đã Nộp Ứng Tuyển` on real jobs `35C86C84` & `35C873D3`. Proven root cause is detached element exception on `submit_btn.get_attribute("aria-busy")` following post-submit navigation.
  - TopCV: Proven NameError bug at lines 433 & 460 in `topcv_applier.py` due to missing `applied_dict` parameter. Cloudflare 403 mitigated with stable modern UA (`Chrome/128.0.0.0`) and 3-strike circuit breaker.
  - VietnamWorks: Proven apply button is intact on active jobs (`2116570`). Root cause of "nút không tìm thấy" on runner was crawler proxy timeout falling back to 20-day-old expired jobs. Fixed by filtering jobs first seen < 14 days.
  - Proxy Fallback: Proven CareerViet and Vieclam24h work reliably without proxy (Direct IP); TopCV & VNW use proxy probe with direct fallback.
- **Host Profile Status**: `PROVEN` (`.planning/HOST_PROFILE.md`)
- **Ledger Status**: `ATTEMPTS.md` updated with `ATT-008`.

## Evaluation Criteria
1. `careerviet/cv_applier.py`: Replace fragile `submit_btn.get_attribute("aria-busy")` with resilient API response capture / navigation wait. Confirm application success and verify `Đã Nộp Ứng Tuyển` button status.
2. `topcv/topcv_applier.py`: Fix `applied_dict` parameter passing; update User-Agent to stable version; implement 3-failure Cloudflare/Timeout circuit breaker.
3. `vietnamworks/vnw_applier.py`: Filter candidates by `first_seen` / `crawled_at` date within last 14 days to prevent attempting expired job posts.
4. `shared/proxy_utils.py`: Add platform-specific proxy routing / bypass configuration.
5. Verification: Dry-run & syntax compilation across all modified modules. Push to GitHub and verify clean execution.

## Decision
**Decision: GO**
