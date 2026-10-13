# Plan Verification Gate

- **Task**: Split Cron Schedule into 4 Independent Off-Peak Prime Rules & Fix TopCV/VNW Queue Traversal + Expired Archiving (ATT-018)
- **Certainty Tier**: `T3-REASONED-CUSTOM`
- **Spike / Evidence Status**: `PROVEN`
  - Audited 36 historical `event:schedule` runs on GitHub Actions (Sep 28 – Oct 12): single combined `cron: '35 1,6,9,13 * * 1-5'` rule caused GitHub scheduler coalescing and dropped `01:35 UTC` and `09:35 UTC` shifts.
  - Audited `topcv/session_report.json` (Run #54): `jobs_to_apply` truncated to `max_applies` (30) prior to loop caused 25 `ALREADY_APPLIED` + 3 `EXPIRED` to exhaust the 30-item slice with `applied_count = 0`, leaving 470 unapplied jobs untouched in `extracted_jobs_history.txt`. Furthermore, `EXPIRED` jobs on TopCV were not persisted to `applied_jobs_history`.
- **Host Profile Status**: `PROVEN` (`.planning/HOST_PROFILE.md`)
- **Ledger Status**: `ATTEMPTS.md` updated with `ATT-018`.

## Evaluation Criteria
1. `.github/workflows/multi_platform_pipeline.yml` defines 4 separate `- cron:` entries at prime off-peak minutes (`17 1 * * 1-5`, `23 6 * * 1-5`, `41 9 * * 1-5`, `47 13 * * 1-5`).
2. `topcv/topcv_applier.py` archives `EXPIRED` postings into `applied_jobs_history` so expired URLs are never re-visited, and traverses up to `max_applies * 4` candidates until `applied_count >= max_applies`.
3. `vietnamworks/vnw_applier.py` buffers `unapplied_jobs[:max_applies * 3]` and filters against `applied_dict` after portal sync so `applied_count` can reach the full `max_applies` quota.
4. Remote verification on GitHub Actions runner environment via live dispatch for today's morning shift (13/10).

## Decision
**Decision: GO**
