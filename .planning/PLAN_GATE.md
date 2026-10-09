# Plan Verification Gate

- **Task**: TopCV Cloudflare WAF Resolution & Vieclam24h Apply Quota Completion
- **Certainty Tier**: `T1-VERIFIED-STANDARD` & `T2-WEB-GROUNDED`
- **Spike / Evidence Status**: `PROVEN`
  - Run #50 proved that transparent session reporting works 100%, CareerViet (+2) and VietnamWorks (+2) succeeded, Vieclam24h login loop was eliminated.
  - Root cause of TopCV WAF block on job page identified: discarding `cf_clearance` cookie and aborting fonts/images needed by Cloudflare.
  - Root cause of Vieclam24h 0/2 applied identified: `max_eval_attempts` was capped at 2, halting the queue after 2 expired postings instead of continuing through the remaining 135 unapplied candidates.
- **Host Profile Status**: `PROVEN` (`.planning/HOST_PROFILE.md`)
- **Ledger Status**: `ATTEMPTS.md` updated with `ATT-015`.

## Evaluation Criteria
1. TopCV: Preserve `cf_clearance` and all cookies in `inject_cookies` across `topcv_applier.py` and `topcv_cron_runner.py`.
2. TopCV: Relax `route` blocking (do not abort fonts/images) so Cloudflare challenge resources execute naturally.
3. TopCV: Add Direct IP fallback if proxy triggers Cloudflare WAF block.
4. Vieclam24h: Expand evaluation queue traversal to check up to `min(len(candidate_jobs), max(max_applies * 5, 20))` candidates so expired jobs do not halt the quota.
5. Commit, push to `origin/main`, and trigger GitHub Actions matrix run to verify in remote runner.

## Decision
**Decision: GO**

