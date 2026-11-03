"""Rate limiting, so one caller cannot run up the AI bill or hammer the sign-in form.

Limits use a sliding window: the count for the last N seconds is estimated from the current and
previous fixed windows, which avoids the burst that a plain fixed window allows at its edges.

RATE_LIMIT_ENABLED            true by default
RATE_LIMIT_BACKEND            memory (default; counted per process) or mongo (shared by every process)
RATE_LIMIT_<NAME>             override one limit (requests per window); 0 turns that limit off

  GENERAL (300/min per IP)   LOGIN (10/min per IP)        REGISTER (5/hour per IP)
  REFRESH (30/min per IP)    PASSWORD_RESET (5/hour per IP) INVITATIONS (20/hour per user)
  SCANS (10/min per user)    ORG_SCANS (60/min per organisation)

Requests over a limit get 429 with Retry-After. If the counter store fails, requests are allowed
and the error is logged: an outage must not lock everyone out.
"""
import logging
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, List

from fastapi import Depends, Request, Response
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError, PyMongoError

from accounts import Principal
from client_info import client_ip
from deps import get_principal
from services.errors import ScanError

logger = logging.getLogger(__name__)


@dataclass
class Hit:
    allowed: bool
    limit: int
    remaining: int
    retry_after: int  # seconds until enough of the window has passed


class Limiter(ABC):
    @abstractmethod
    async def hit(self, key: str, limit: int, window: int) -> Hit:
        """Count one request against `key` and say whether it is within `limit` per `window` seconds"""


def _estimate(current: int, previous: int, elapsed: float, window: int) -> float:
    return current + previous * (1 - elapsed / window)


def _result(estimated: float, limit: int, elapsed: float, window: int) -> Hit:
    allowed = estimated <= limit
    return Hit(allowed, limit, max(0, int(limit - estimated)), max(1, int(window - elapsed) + 1))


class MemoryLimiter(Limiter):
    def __init__(self, clock=time.time):
        self._clock = clock
        self._counts: Dict[str, List[int]] = {}  # key -> [window index, current, previous]

    async def hit(self, key: str, limit: int, window: int) -> Hit:
        now = self._clock()
        index, elapsed = int(now // window), now % window
        entry = self._counts.get(key)
        if entry is None:
            entry = self._counts[key] = [index, 0, 0]
        elif entry[0] != index:
            entry[1:] = [entry[1], 0] if entry[0] == index - 1 else [0, 0]
            entry[0] = index
        entry[1] += 1
        if len(self._counts) > 20000:  # forget callers not seen for two windows
            self._counts = {k: v for k, v in self._counts.items() if v[0] >= index - 1}
        return _result(_estimate(entry[1], entry[2], elapsed, window), limit, elapsed, window)


class MongoLimiter(Limiter):
    """Counters in MongoDB, so every app process shares them. One upsert per request."""

    def __init__(self, db_getter, clock=time.time):
        self._db = db_getter
        self._clock = clock

    async def hit(self, key: str, limit: int, window: int) -> Hit:
        now = self._clock()
        index, elapsed = int(now // window), now % window
        coll = self._db().rate_limits
        expires = datetime.fromtimestamp(now, timezone.utc) + timedelta(seconds=2 * window + 60)
        update = {"$inc": {"count": 1}, "$setOnInsert": {"expires_at": expires}}
        for attempt in (1, 2):
            try:
                current = await coll.find_one_and_update(
                    {"key": key, "window": index}, update, upsert=True, return_document=ReturnDocument.AFTER
                )
                break
            except DuplicateKeyError:  # two processes inserted the same window at once; the second retries
                if attempt == 2:
                    raise
        previous = await coll.find_one({"key": key, "window": index - 1})
        return _result(_estimate(current["count"], previous["count"] if previous else 0, elapsed, window), limit, elapsed, window)


def enabled() -> bool:
    return os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"


def create_limiter(db_getter) -> Limiter:
    backend = os.getenv("RATE_LIMIT_BACKEND", "memory").lower()
    if backend == "mongo":
        return MongoLimiter(db_getter)
    if backend != "memory":
        raise ValueError("RATE_LIMIT_BACKEND must be 'memory' or 'mongo'.")
    return MemoryLimiter()


async def check(request: Request, response: Response, name: str, identity: str, default: int, window: int) -> None:
    """Count a request and raise 429 when it is over the limit"""
    if not enabled():
        return
    limit = int(os.getenv(f"RATE_LIMIT_{name.upper()}", str(default)))
    if limit <= 0:
        return
    limiter = getattr(request.app.state, "rate_limiter", None)
    if limiter is None:
        return
    try:
        hit = await limiter.hit(f"{name}:{identity}", limit, window)
    except (PyMongoError, DuplicateKeyError) as e:
        logger.error(f"Rate limiter unavailable, allowing the request: {e}")
        return
    headers = {"X-RateLimit-Limit": str(hit.limit), "X-RateLimit-Remaining": str(hit.remaining)}
    if not hit.allowed:
        wait = hit.retry_after
        raise ScanError(429, f"Too many requests. Try again in {wait} second(s).", {**headers, "Retry-After": str(wait)})
    response.headers.update(headers)


def limit_by_ip(name: str, default: int, window: int = 60):
    """Dependency: at most `default` requests per `window` seconds from one IP address"""
    async def dependency(request: Request, response: Response):
        await check(request, response, name, client_ip(request), default, window)
    return dependency


def limit_by_user(name: str, default: int, window: int = 60):
    """Dependency: at most `default` requests per `window` seconds from one signed-in user.
    Without sign-in (development), the organisation is the caller."""
    async def dependency(request: Request, response: Response, principal: Principal = Depends(get_principal)):
        await check(request, response, name, principal.user_id or f"org:{principal.org_id}", default, window)
    return dependency


def limit_by_org(name: str, default: int, window: int = 60):
    """Dependency: at most `default` requests per `window` seconds from one organisation, all users together"""
    async def dependency(request: Request, response: Response, principal: Principal = Depends(get_principal)):
        await check(request, response, name, principal.org_id, default, window)
    return dependency
