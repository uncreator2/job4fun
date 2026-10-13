# Plan Verification Gate

- **Task**: Fix TopCV False-Positive `ALREADY_APPLIED` Full-Page Text Match & Purge 208 False-Positive Records (ATT-019)
- **Certainty Tier**: `T3-REASONED-CUSTOM`
- **Spike / Evidence Status**: `PROVEN`
  - Audited `topcv/session_report.json` in Run #55 (`a8c2f0b`): 89 out of 120 scanned jobs returned `ALREADY_APPLIED` (`"Đã ứng tuyển trước đó trên TopCV"`).
  - Inspected `topcv/topcv_applier.py` lines 368–383: `bodyTextLower.includes(kw)` scanned the entire `document.body.innerText` for `"đã ứng tuyển"` and `"applied"`, which matched the logged-in TopCV top navigation bar menu item `"Việc làm đã ứng tuyển"` (and English job descriptions containing `"applied"`) on 100% of active job pages.
- **Host Profile Status**: `PROVEN` (`.planning/HOST_PROFILE.md`)
- **Ledger Status**: `ATTEMPTS.md` updated with `ATT-019`.

## Evaluation Criteria
1. `topcv/topcv_applier.py` checks `reapplyKeywords` and `alreadyAppliedKeywords` strictly against the apply buttons (`applyBtns`) and the job action container (`.box-apply-current, .job-detail__information-detail--actions, .box-apply`), never against full `document.body.innerText`.
2. `topcv/topcv_applier.py` handles `NO_APPLY_BTN` in the main loop and records expired/closed postings without an apply button.
3. `topcv/applied_jobs_history.json` and `topcv/applied_jobs_history.txt` are sanitized to remove the 208 false-positive `"Đã ứng tuyển trước đó trên TopCV"` records while preserving all 130 genuine records (60 synced from TopCV portal, 58 real cover-letter applications, 12 expired jobs).

## Decision
**Decision: GO**

