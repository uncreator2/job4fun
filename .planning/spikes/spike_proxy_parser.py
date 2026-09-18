import os
import re

def parse_proxy_setting(proxy_str: str):
    """
    Parses various proxy formats into Playwright proxy dictionary:
    - http://user:pass@host:port
    - http://host:port
    - socks5://user:pass@host:port
    - host:port:user:pass (common commercial format)
    - host:port
    """
    if not proxy_str:
        return None

    proxy_str = proxy_str.strip()

    # Format 1: host:port:user:pass
    m_quad = re.match(r"^([a-zA-Z0-9.\-]+):(\d+):([^:@]+):([^:@]+)$", proxy_str)
    if m_quad:
        host, port, user, password = m_quad.groups()
        return {
            "server": f"http://{host}:{port}",
            "username": user,
            "password": password
        }

    # Format 2: Standard URI scheme (http://, https://, socks5://)
    if re.match(r"^(https?|socks5)://", proxy_str):
        # Extract user:pass if embedded in URL
        m_auth = re.match(r"^(https?|socks5)://([^:@]+):([^@]+)@([^/]+)$", proxy_str)
        if m_auth:
            proto, user, password, host_port = m_auth.groups()
            return {
                "server": f"{proto}://{host_port}",
                "username": user,
                "password": password
            }
        return {"server": proxy_str}

    # Format 3: host:port (assumed http)
    if re.match(r"^([a-zA-Z0-9.\-]+):(\d+)$", proxy_str):
        return {"server": f"http://{proxy_str}"}

    return {"server": proxy_str}

if __name__ == "__main__":
    test_cases = [
        "http://proxy.example.com:8080",
        "http://myuser:mypass123@1.2.3.4:9999",
        "socks5://alice:secret@10.0.0.1:1080",
        "vn-res.proxy.net:3128:testuser:testpass",
        "192.168.1.1:8080"
    ]
    for tc in test_cases:
        res = parse_proxy_setting(tc)
        print(f"Input: {tc} -> Parsed: {res}")
