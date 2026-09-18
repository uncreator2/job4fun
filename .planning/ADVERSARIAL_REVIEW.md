# Adversarial Review Ledger

| Review ID | Category | Threat / Edge Case | Mitigation | Status |
| :--- | :--- | :--- | :--- | :--- |
| ADV-001 | Malformed Proxy Input | User enters proxy with special chars or invalid format | Regex fallback handles 5 distinct formats, defaults gracefully to direct string | MITIGATED |
| ADV-002 | Credential Leakage | Proxy username & password logged to public Actions stdout | `proxy_utils.py` masks auth in log messages, logs only server hostname/port | MITIGATED |
