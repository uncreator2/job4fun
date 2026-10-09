# Plan Verification Gate

- **Task**: Network & Proxy Optimization (Direct IP default for VietnamWorks & Vieclam24h; Resource blocking & 5x speedup for TopCV)
- **Certainty Tier**: `T1-VERIFIED-STANDARD` (Direct IP routing, resource abort rules) + `T2-WEB-GROUNDED` (TopCV Cloudflare resilience)
- **Spike / Evidence Status**: `PROVEN`
  - VNW & V24H: Benchmarks prove Direct IP is 10-18x faster (VNW: 0.44s vs 8.16s; V24H: 15s vs 28s). Cloud runners are not IP-blocked by either platform.
  - TopCV: Proven that blocking images, fonts, and 3rd-party tracking scripts reduces Playwright page load time from 17.97s down to 2.91s through the proxy, eliminating Page.goto 30s/35s timeouts.
- **Host Profile Status**: `PROVEN` (`.planning/HOST_PROFILE.md`)
- **Ledger Status**: `ATTEMPTS.md` updated with `ATT-009`.

## Evaluation Criteria
1. `vietnamworks/`: Set Direct IP as default in crawler and applier, eliminating 30s timeouts.
2. `vieclam24h/`: Set Direct IP as default in crawler and applier, eliminating 30s timeouts.
3. `topcv/`: In crawler and applier, add Playwright `route()` interceptor to abort images, fonts, and third-party trackers, bringing load times to ~2.9s.
4. Dry-run verify locally, compile, commit to main, and trigger GitHub Actions verification run.

## Decision
**Decision: GO**
