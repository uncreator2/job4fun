# Plan Verification Gate

- **Task**: Fix Playwright Headless Shell Missing Binary in GitHub Actions Runners (ATT-022)
- **Certainty Tier**: `T1-VERIFIED-STANDARD`
- **Spike / Evidence Status**: `PROVEN`
  - Downloaded and analyzed full job log for Run #66 (`116020338130`):
    `playwright._impl._errors.Error: BrowserType.launch: Executable doesn't exist at /home/runner/.cache/ms-playwright/chromium_headless_shell-1248/chrome-headless-shell-linux64/chrome-headless-shell`
  - Root cause identified: GitHub Actions cache restored an older `~/.cache/ms-playwright` directory. Because `cache-hit == 'true'`, the workflow executed `playwright install-deps chromium` (apt dependencies only) instead of `playwright install --with-deps chromium`. The updated Playwright package from PyPI required `chromium_headless_shell-1248`, which was missing from the cache.
  - Solution: Remove the conditional check and ensure `playwright install --with-deps chromium` is always invoked across all workflow definitions (`multi_platform_pipeline.yml`, `debug_parallel_pipeline.yml`, `test_site.yml`).
- **Host Profile Status**: `PROVEN` (`.planning/HOST_PROFILE.md`)
- **Ledger Status**: `ATTEMPTS.md` to be updated with `ATT-022`.

## Evaluation Criteria
1. Workflows always execute `playwright install --with-deps chromium`.
2. PyYAML validates syntax across all workflow files.
3. Test dispatch run confirms browser launches cleanly without `Executable doesn't exist`.

## Decision
**Decision: GO**
