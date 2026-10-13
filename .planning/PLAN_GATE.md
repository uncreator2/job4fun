# Plan Verification Gate

- **Task**: Implement Sequential Execution (`max-parallel: 1`) for Scheduled Shifts & Dedicated Parallel Debug Workflow (ATT-021)
- **Certainty Tier**: `T1-VERIFIED-STANDARD`
- **Spike / Evidence Status**: `PROVEN`
  - Validated that `strategy.max-parallel: 1` runs matrix jobs sequentially across isolated runners in GitHub Actions while preserving separate logs, artifacts, and failure domains (`fail-fast: false`).
  - Optimized platform order: `careerviet` (~1 min) -> `vieclam24h` (~1 min) -> `vietnamworks` (~8 mins) -> `topcv` (~30 mins). Total execution fits comfortably within 45 mins.
  - Provided `debug_parallel_pipeline.yml` strictly for manual parallel debugging across all 4 platforms simultaneously.
- **Host Profile Status**: `PROVEN` (`.planning/HOST_PROFILE.md`)
- **Ledger Status**: `ATTEMPTS.md` to be updated with `ATT-021`.

## Evaluation Criteria
1. `multi_platform_pipeline.yml` contains `max-parallel: 1` and order `[careerviet, vieclam24h, vietnamworks, topcv]`.
2. Dedicated `debug_parallel_pipeline.yml` allows on-demand concurrent execution of all platforms for debugging.
3. Both workflow YAML files parse with zero syntax errors via PyYAML.
4. Changes committed and pushed to `origin/main` without affecting cron schedules.

## Decision
**Decision: GO**
