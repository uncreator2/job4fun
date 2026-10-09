# Plan Verification Gate

- **Task**: Eliminate Fake Success Labels, Deploy Seasonal Cookies, Fix TopCV Cloudflare & Vieclam24h Multi-Re-login Loop
- **Certainty Tier**: `T1-VERIFIED-STANDARD` & `T2-WEB-GROUNDED`
- **Spike / Evidence Status**: `PROVEN`
  - Fresh seasonal cookies extracted from active CDP browser: TopCV (24 cookies), Vieclam24h (31 cookies).
  - GitHub Secrets (`COOKIES`, `V24H_COOKIES`, `PROXY_SERVER`) updated directly on GitHub repository.
  - Root cause of fake label success pinpointed to `run_pipeline.py` checking exit code 0 rather than real application results.
  - Root cause of Vieclam24h re-login loop identified as redundant per-job header check.
- **Host Profile Status**: `PROVEN` (`.planning/HOST_PROFILE.md`)
- **Ledger Status**: `ATTEMPTS.md` updated with `ATT-014`.

## Evaluation Criteria
1. Whitelist `topcv/topcv_cookies.json` and `vieclam24h/vieclam24h_cookies.json` in `.gitignore`.
2. Update `v24h_applier.py` to eliminate redundant per-job login checks and verify session via `access_token` cookie.
3. Update `topcv_applier.py` to verify session via `lich-su-ung-tuyen` and prevent Turnstile form fallback.
4. Export standardized `session_report.json` across all 4 platforms (`topcv`, `vietnamworks`, `vieclam24h`, `careerviet`).
5. Overhaul `run_pipeline.py` reporting to display itemized To-Do jobs, applied jobs with titles/companies/URLs, and skipped/failed breakdowns.
6. Commit and push all changes to `origin/main`.
7. Trigger and monitor GitHub Actions execution strictly within GitHub Actions runner environment.

## Decision
**Decision: GO**
