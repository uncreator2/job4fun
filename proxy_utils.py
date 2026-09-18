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
        return None

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
