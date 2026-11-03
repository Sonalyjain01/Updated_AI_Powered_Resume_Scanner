"""Request ids: one id per request, on every log line and in the X-Request-ID response header.

A caller (or a gateway in front of the app) may send its own X-Request-ID so one id follows a
request across systems. Anything that is not a short, plain token is replaced, so a header can
never inject odd characters into the logs.
"""
import contextvars
import logging
import re
import uuid
from typing import Optional

REQUEST_ID_HEADER = "X-Request-ID"
_VALID_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")

_request_id: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")


def get_request_id() -> str:
    return _request_id.get()


def set_request_id(value: str) -> contextvars.Token:
    """Used by background workers to keep logging under the id of the request that queued the work"""
    return _request_id.set(value)


def reset_request_id(token: contextvars.Token) -> None:
    _request_id.reset(token)


def new_request_id() -> str:
    return uuid.uuid4().hex


def accept_or_generate(incoming: Optional[str]) -> str:
    if incoming and _VALID_ID.match(incoming):
        return incoming
    return new_request_id()


def install_log_record_factory() -> None:
    """Give every log record a request_id attribute, whichever handler formats it"""
    previous = logging.getLogRecordFactory()
    if getattr(previous, "_adds_request_id", False):
        return

    def factory(*args, **kwargs):
        record = previous(*args, **kwargs)
        record.request_id = _request_id.get()
        return record

    factory._adds_request_id = True
    logging.setLogRecordFactory(factory)


class RequestIdMiddleware:
    """Pure ASGI middleware, so the id is visible to the endpoint and to everything it awaits"""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = None
        for name, value in scope.get("headers", []):
            if name == b"x-request-id":
                incoming = value.decode("latin-1")
                break
        request_id = accept_or_generate(incoming)
        token = _request_id.set(request_id)
        scope.setdefault("state", {})["request_id"] = request_id

        async def send_with_id(message):
            if message["type"] == "http.response.start":
                headers = [h for h in message.get("headers", []) if h[0].lower() != b"x-request-id"]
                headers.append((b"x-request-id", request_id.encode("latin-1")))
                message = {**message, "headers": headers}
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        finally:
            _request_id.reset(token)
