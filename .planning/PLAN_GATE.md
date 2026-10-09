# Plan Verification Gate

- **Task**: Modular Per-Site Test & Repair Framework (`test_site.py` & `.github/workflows/test_site.yml`) for isolated platform testing and debugging
- **Certainty Tier**: `T1-VERIFIED-STANDARD` (Local CLI diagnostics, Playwright dry-runs, GitHub Actions workflow dispatch)
- **Spike / Evidence Status**: `PROVEN`
  - All 4 platform engines (`topcv/`, `vietnamworks/`, `careerviet/`, `vieclam24h/`) are modular and runnable independently.
  - Previous Production Run #47 confirmed 100% green execution across all platforms.
  - Isolating each site allows 1-minute test runs instead of the 35-minute full pipeline.
- **Host Profile Status**: `PROVEN` (`.planning/HOST_PROFILE.md`)
- **Ledger Status**: `ATTEMPTS.md` updated with `ATT-011`.

## Evaluation Criteria
1. Implement `test_site.py` with `--site <site>` (`topcv`, `vietnamworks`, `careerviet`, `vieclam24h`) and `--mode <diagnose|crawl_test|apply_test|all>`.
2. Implement `.github/workflows/test_site.yml` supporting isolated workflow dispatch per platform.
3. Verify `test_site.py --site <site> --mode diagnose` locally across all 4 platforms.
4. Compile, commit, and push to `origin/main`.
5. Trigger `.github/workflows/test_site.yml` on GitHub Actions and verify rapid (<2 min) isolated execution.

## Decision
**Decision: GO**
