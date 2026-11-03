"""Who is really calling, and over what protocol, when the app sits behind proxies.

Forwarding headers (X-Forwarded-For, X-Forwarded-Proto) are only believed when
TRUSTED_PROXY_COUNT says how many proxies sit in front of the app. Otherwise anyone could send
a fake X-Forwarded-For and dodge rate limits, or fake X-Forwarded-Proto to skip the HTTPS check.

TRUSTED_PROXY_COUNT   proxies in front of the app that you control (default 0 = none)
"""
import os
from typing import Mapping, Optional, Tuple


def trusted_proxy_count() -> int:
    return max(0, int(os.getenv("TRUSTED_PROXY_COUNT", "0")))


def client_ip_from(headers: Mapping[str, str], peer: Optional[str]) -> str:
    """The client address. With N trusted proxies, the Nth entry from the right of X-Forwarded-For
    is the address our outermost proxy saw; anything further left was supplied by the client."""
    count = trusted_proxy_count()
    if count > 0:
        forwarded = [part.strip() for part in headers.get("x-forwarded-for", "").split(",") if part.strip()]
        if len(forwarded) >= count:
            return forwarded[-count]
    return peer or "unknown"


def is_https_from(headers: Mapping[str, str], scheme: str) -> bool:
    if scheme in ("https", "wss"):
        return True
    return trusted_proxy_count() > 0 and headers.get("x-forwarded-proto", "").split(",")[0].strip().lower() == "https"


def client_ip(request) -> str:
    return client_ip_from(request.headers, request.client.host if request.client else None)


def user_agent(request) -> str:
    return request.headers.get("user-agent", "")[:200]


def scope_info(scope) -> Tuple[dict, str, Optional[str]]:
    """Headers (lower-case names), scheme and peer address from an ASGI scope"""
    headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}
    client = scope.get("client")
    return headers, scope.get("scheme", "http"), client[0] if client else None
