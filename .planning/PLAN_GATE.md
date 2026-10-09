# Plan Verification Gate

- **Task**: Fix CareerViet Crawler Job Extraction & Fallback Parsing (ATT-016)
- **Certainty Tier**: `T3-REASONED-CUSTOM`
- **Spike / Evidence Status**: `PROVEN`
  - Investigated live CareerViet response: 50+ cards (.job-item) with valid management titles exist on target search URL.
  - Root cause identified: Next.js client-side rendering latency under proxy causes document.querySelectorAll('.job-item') to return empty before cards attach, due to absence of explicit wait_for_selector and lack of SSR HTML fallback.
- **Host Profile Status**: `PROVEN` (`.planning/HOST_PROFILE.md`)
- **Ledger Status**: `ATTEMPTS.md` updated with `ATT-016`.

## Evaluation Criteria
1. Explicit wait for `.job-item` selector with resilient timeout and scrolling.
2. Dual-layer extraction: if DOM querySelector returns 0 cards, fallback to parsing server-rendered Next.js HTML from `page.content()`.
3. Granular, transparent logging in `cv_crawler.py`: raw cards found -> management filtered -> new jobs added to history.
4. Remote verification on GitHub Actions runner environment.

## Decision
**Decision: GO**

