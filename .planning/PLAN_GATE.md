# Plan Verification Gate

- **Task**: CareerViet Subsystem Integration (Credentials, Hanoi Management Search URLs, Crawler Engine)
- **Certainty Tier**: `T1-VERIFIED-STANDARD` (Credentials, search_urls.txt, history ledgers, regex filters) + `T2-WEB-GROUNDED` (CareerViet DOM parsing, session cookies, pagination scheme)
- **Spike / Evidence Status**: `PROVEN`
  - Cookie Extraction: Verified 28 active session cookies extracted from CDP session (port 9223).
  - Search URL Discovery: Verified exact canonical patterns:
    - Giám đốc kinh doanh tại Hà Nội: `https://careerviet.vn/viec-lam/giam-doc-kinh-doanh-tai-ha-noi-kl4-vi.html` (57 việc làm)
    - Trưởng phòng kinh doanh tại Hà Nội: `https://careerviet.vn/viec-lam/truong-phong-kinh-doanh-tai-ha-noi-kl4-vi.html` (74 việc làm)
    - Pagination pattern: `https://careerviet.vn/viec-lam/...-kl4-trang-N-vi.html`
  - Preflight Spike (`.planning/spikes/careerviet_spike.py`): Executed successfully, parsed 50 real job cards on page 1 with 100% field extraction (Title, Company, URL, Salary, Location).
- **Host Profile Status**: `PROVEN` (`.planning/HOST_PROFILE.md`)
- **Ledger Status**: `ATTEMPTS.md` updated with `ATT-005`.

## Evaluation Criteria
1. `careerviet/careerviet_cookies.json`: Export authenticated cookies from active CDP session.
2. `careerviet/env.txt`: Store credentials file for credential redundancy.
3. `careerviet/search_urls.txt`: Configure the target search URLs for Hanoi management positions.
4. `careerviet/cv_filter.py`: Implement role whitelist/blacklist matching candidate executive profile.
5. `careerviet/cv_crawler.py`: Playwright crawler adhering to standard mono-repo architecture (proxy support, cookie hydration, pagination, deduplication).
6. Ledger Integrity: Initialize `careerviet/extracted_jobs_history.json` and `.txt`.
7. Verification: Run `cv_crawler.py` locally and verify output populated with management jobs.

## Decision
**Decision: GO**
