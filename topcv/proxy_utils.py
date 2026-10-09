import os
import re

def get_proxy_config():
    """
    Reads PROXY_SERVER environment variable and formats it for Playwright browser.new_context(proxy=...)
    Supported formats:
    - http://user:pass@host:port
    - http://host:port
    - socks5://user:pass@host:port
    - host:port:user:pass (commercial residential proxies standard format)
    - host:port
    """
    proxy_str = os.environ.get("PROXY_SERVER", "").strip()
    if not proxy_str:
        candidates = [
            os.path.join(os.path.dirname(__file__), "proxy.txt"),
            os.path.join(os.path.dirname(__file__), "..", "topcv", "proxy.txt"),
            os.path.join(os.getcwd(), "proxy.txt"),
            os.path.join(os.getcwd(), "topcv", "proxy.txt")
        ]
        for p in candidates:
            if os.path.exists(p):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        line = f.read().strip()
                        if line:
                            proxy_str = line
                            break
                except Exception:
                    pass

    if not proxy_str:
        return None

    # Auto-migrate any legacy hardcoded IP to the dynamic domain hostname
    proxy_str = proxy_str.replace("103.121.89.32", "zl47151.ipv4dancu.com")

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
