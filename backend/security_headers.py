"""HTTPS enforcement, secure response headers, and a cap on request size.

TLS itself is terminated by a reverse proxy or load balancer in front of the app (see
deploy/nginx.conf.example); these middlewares make sure the app behaves correctly behind it.

FORCE_HTTPS          true: plain-HTTP requests are redirected to HTTPS and HSTS is sent (default false)
TRUSTED_PROXY_COUNT  proxies whose X-Forwarded-Proto / X-Forwarded-For are believed (see client_info.py)
MAX_REQUEST_BYTES    largest request body accepted (default 12 MiB: a 10 MiB resume plus form fields)
"""
import os

from client_info import is_https_from, scope_info

HSTS = "max-age=31536000; includeSubDomains"
# The API returns JSON and loads nothing, so nothing may be loaded from it. The docs pages need scripts.
API_CSP = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
DOC_PATHS = ("/docs", "/redoc", "/openapi.json")
# Load balancers probe these over plain HTTP from inside the network
HTTPS_EXEMPT = ("/api/v1/health", "/api/v1/", "/api/health", "/api/")


def force_https() -> bool:
    return os.getenv("FORCE_HTTPS", "false").lower() == "true"


def max_request_bytes() -> int:
    return int(os.getenv("MAX_REQUEST_BYTES", str(12 * 1024 * 1024)))


class HttpsRedirectMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not force_https():
            await self.app(scope, receive, send)
            return
        headers, scheme, _ = scope_info(scope)
        if is_https_from(headers, scheme) or scope["path"] in HTTPS_EXEMPT:
            await self.app(scope, receive, send)
            return
        host = headers.get("host", "")
        query = scope.get("query_string", b"").decode("latin-1")
        target = f"https://{host}{scope['path']}" + (f"?{query}" if query else "")
        # 308 keeps the method and body, so a POST is not turned into a GET
        await send({"type": "http.response.start", "status": 308,
                    "headers": [(b"location", target.encode("latin-1")), (b"content-length", b"0")]})
        await send({"type": "http.response.body", "body": b""})


class SecurityHeadersMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers, scheme, _ = scope_info(scope)
        path = scope["path"]
        secure = is_https_from(headers, scheme) or force_https()

        extra = {
            b"x-content-type-options": b"nosniff",
            b"x-frame-options": b"DENY",
            b"referrer-policy": b"no-referrer",
            b"permissions-policy": b"camera=(), microphone=(), geolocation=(), payment=()",
            b"cross-origin-opener-policy": b"same-origin",
        }
        if not path.startswith(DOC_PATHS):
            extra[b"content-security-policy"] = API_CSP.encode()
        if path.startswith("/api/"):
            extra[b"cache-control"] = b"no-store"  # responses hold personal data and tokens
        if secure:
            extra[b"strict-transport-security"] = HSTS.encode()

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                present = {h[0].lower() for h in message.get("headers", [])}
                message = {**message, "headers": list(message.get("headers", [])) + [
                    (k, v) for k, v in extra.items() if k not in present]}
            await send(message)

        await self.app(scope, receive, send_with_headers)


class _TooLarge(Exception):
    pass


class BodySizeLimitMiddleware:
    """Refuse oversized bodies before they are read into memory or onto disk.

    Content-Length is checked up front. A body sent in chunks, with no length, is counted as it
    arrives and stopped when it passes the limit.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        limit = max_request_bytes()
        headers, _, _ = scope_info(scope)
        declared = headers.get("content-length")
        if declared and declared.isdigit() and int(declared) > limit:
            await self._refuse(send)
            return

        received = 0
        started = False

        async def counting_receive():
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    raise _TooLarge()
            return message

        async def tracking_send(message):
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, counting_receive, tracking_send)
        except _TooLarge:
            if not started:
                await self._refuse(send)

    @staticmethod
    async def _refuse(send):
        body = b'{"detail":"The request is too large."}'
        await send({"type": "http.response.start", "status": 413,
                    "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]})
        await send({"type": "http.response.body", "body": body})
