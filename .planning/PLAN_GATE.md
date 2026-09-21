# Plan Verification Gate

- **Task**: Vieclam24h Role Filtering, Modal Submit Hydration & Loop Bounding
- **Certainty Tier**: `T1-VERIFIED-STANDARD` (Role Filtering, Loop Bounding) + `T2-WEB-GROUNDED` (Playwright SPA Hydration & Async Modal)
- **Spike / Evidence Status**: `PROVEN`
  - Root Cause 1 (Nhân viên Crawled): Vieclam24h full-text search fallback on pages 3–10 matches "kinh doanh" without title filter. Verified 112/191 jobs in ledger are staff-level.
  - Root Cause 2 (Modal Submit Not Found): Client-side internal API (`/api/v1/applicant/...`) takes 2–4s to render CV list and submit button behind proxy. Premature 1000ms check failed to find `button:has-text("Nộp hồ sơ ngay")`.
  - Root Cause 3 (Runaway Loop): Candidate loop lacked batch attempt bounds and loop failure circuit breaker, causing 165 iterations over 1+ hours.
  - Spike / Validation: Verified locally with Playwright and regex; filtered 191 jobs down to 60 pristine management roles with 0% false positive staff entries.
- **Host Profile Status**: `PROVEN` (`.planning/HOST_PROFILE.md`)
- **Ledger Status**: `ATTEMPTS.md` updated.

## Evaluation Criteria
1. `vieclam24h/v24h_crawler.py`: Implement canonical whitelist (`MANAGEMENT_KEYWORDS`) and blacklist (`EXCLUDE_KEYWORDS`) in `extract_jobs_from_page()`.
2. `vieclam24h/v24h_applier.py`:
   - Enforce dual-layer filter in `candidate_jobs` to guarantee no staff jobs are ever evaluated.
   - Bound total job evaluation attempts to `min(len(candidate_jobs), max_applies * 2)` to eliminate runaway loops.
   - Add consecutive failure circuit breaker (break after 5 consecutive submit failures).
   - In `apply_single_job()`: Implement resilient modal hydration wait `page.wait_for_selector('button:has-text("Nộp hồ sơ ngay")', timeout=12000, state="visible")` with scroll into view and fallback evaluation click.
3. Ledger Hygiene: Cleanse `vieclam24h/extracted_jobs_history.json` and `.txt` to eliminate all 131 non-managerial entries.
4. Orchestrator Safety: Ensure `run_pipeline.py` propagates limits properly and records platform summaries.
5. Verification: Dry-run and crawler execution locally and on GitHub Actions CI.

## Decision
**Decision: GO**
