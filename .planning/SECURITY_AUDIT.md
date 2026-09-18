# Security & SAST Audit Ledger

| Audit ID | Scope | Finding | Resolution | Status |
| :--- | :--- | :--- | :--- | :--- |
| SEC-001 | Secrets Handling | Ensure proxy credentials and TopCV auth cookies are not committed to public repo | Handled via GitHub Secrets (`COOKIES`, `ENV_TXT`, `PROXY_SERVER`) + `.gitignore` | PASSED |
| SEC-002 | Dependency Integrity | Ensure `playwright-stealth` has no malicious network callbacks | Verified local PyPI wheel checksum and import behavior | PASSED |
