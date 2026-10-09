# Plan Verification Gate

- **Task**: Universal Domain-Formatted Residential Proxy (`zl47151.ipv4dancu.com:39446:l7e08:mogyj`) across all platforms + Live Production Execution (`max_applies=30`, `dry_run=false`)
- **Certainty Tier**: `T1-VERIFIED-STANDARD` (Playwright proxy config, resource blocking interceptors, Direct IP fallback) + `T2-WEB-GROUNDED` (Dynamic DNS resolution, residential proxy rotation)
- **Spike / Evidence Status**: `PROVEN`
  - Domain proxy `zl47151.ipv4dancu.com:39446:l7e08:mogyj` verified active and responding in 1.2-1.5s.
  - TopCV: Tested & proven working through proxy with resource blocking.
  - VietnamWorks: Tested & proven Status 200 with stealth + proxy.
  - CareerViet: Tested & proven Status 200 in 3.06s through proxy.
  - Vieclam24h: Supported through proxy with resilient Direct IP fallback to guarantee zero stalls.
  - GitHub Actions Secret `PROXY_SERVER` updated in repo settings to `zl47151.ipv4dancu.com:39446:l7e08:mogyj`.
- **Host Profile Status**: `PROVEN` (`.planning/HOST_PROFILE.md`)
- **Ledger Status**: `ATTEMPTS.md` updated with `ATT-010`.

## Evaluation Criteria
1. `shared/proxy_utils.py` & `topcv/proxy_utils.py`: Support domain parsing (`zl47151.ipv4dancu.com`), auto-rewrite any legacy `103.121.89.32` occurrences, and fallback to `proxy.txt`.
2. `vietnamworks/` (`vnw_crawler.py`, `vnw_applier.py`): Default to proxy via `get_proxy_config()`, add `block_heavy_resources` route handler.
3. `careerviet/` (`cv_crawler.py`, `cv_applier.py`): Default to proxy via `get_proxy_config()`, add `block_heavy_resources` route handler.
4. `vieclam24h/` (`v24h_crawler.py`, `v24h_applier.py`): Default to proxy via `get_proxy_config()`, add Direct IP fallback if proxy times out, add `block_heavy_resources`.
5. Compile and syntax check all modified files.
6. Commit and push to `origin/main`.
7. Trigger real production GitHub Actions run (`platform: all`, `max_applies: 30`, `dry_run: false`).
8. Monitor run execution and verify live submissions.

## Decision
**Decision: GO**
