# Plan Verification Gate

- **Task**: Fix VietnamWorks button detection race condition & Vieclam24h proxy ERR_CONNECTION_RESET
- **Certainty Tier**: `T2-WEB-GROUNDED` (Playwright SPA hydration + Proxy resilience)
- **Spike / Evidence Status**: `PROVEN`
  - VNW Job 2104605: Verified 2 active apply buttons; failure caused by Next.js hydration race condition before `apply_btn.count()`
  - VNW Job 2084750: Verified apply button is `disabled=""` (employer closed intake); required `is_disabled()` handling
  - V24H Run #6 log line 1305: Verified `net::ERR_CONNECTION_RESET at https://vieclam24h.vn/` during initial `goto`
- **Host Profile Status**: `PROVEN` (`.planning/HOST_PROFILE.md`)
- **Ledger Status**: `ATTEMPTS.md` updated.

## Evaluation Criteria
1. VietnamWorks: Implement `page.wait_for_selector(..., timeout=10000)` and `is_disabled()` check.
2. Vieclam24h: Implement `safe_goto(..., max_retries=3)` with backoff to withstand proxy connection resets.
3. GitHub Actions: Stage and commit ledger before `git pull --rebase origin main` to prevent rebase failure.
4. Local Verification: Dry-run passes on both platforms.

## Decision
**Decision: GO**

