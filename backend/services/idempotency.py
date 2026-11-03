"""Idempotency keys for creating scans.

A client sends `Idempotency-Key: <unique value>` with POST /scans. If the request is repeated
with the same key (a retry after a dropped connection, a double click), the original response is
returned and no second scan, and no second AI bill, is created.

  same key, same upload and settings   -> the stored response, with `Idempotent-Replay: true`
  same key, different upload/settings  -> 422, because the key is being reused for something else
  same key, first request still running -> 409; try again in a moment

Keys are scoped to a tenant and forgotten after IDEMPOTENCY_TTL_HOURS (default 24).
"""
import hashlib
import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Optional

from database import DatabaseError, database
from models import utc_now
from services.errors import ScanError

logger = logging.getLogger(__name__)

HEADER = "Idempotency-Key"
_VALID_KEY = re.compile(r"^[A-Za-z0-9_.:-]{1,100}$")


@dataclass
class Replay:
    status_code: int
    body: dict


def ttl_hours() -> float:
    return float(os.getenv("IDEMPOTENCY_TTL_HOURS", "24"))


def validate_key(key: Optional[str]) -> Optional[str]:
    if key is None or key == "":
        return None
    if not _VALID_KEY.match(key):
        raise ScanError(400, f"{HEADER} must be 1 to 100 characters: letters, digits, and _ . : -")
    return key


def fingerprint(content: bytes, filename: str, job_description: str, criteria_json: str) -> str:
    """Identifies what a request asks for, so a reused key with a different request is caught"""
    digest = hashlib.sha256()
    for part in (hashlib.sha256(content).hexdigest(), filename, job_description, criteria_json):
        digest.update(part.encode("utf-8"))
        digest.update(b"\x00")
    return digest.hexdigest()


def canonical_json(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


async def begin(tenant_id: str, key: str, request_fingerprint: str) -> Optional[Replay]:
    """Reserve the key, or return the stored response if this request was already handled.

    Returns None when the caller should go ahead and do the work (it now owns the key).
    """
    record = {
        "tenant_id": tenant_id,
        "key": key,
        "fingerprint": request_fingerprint,
        "state": "in_progress",
        "created_at": utc_now(),
    }
    if await database.reserve_idempotency_key(record):
        return None

    existing = await database.get_idempotency_key(tenant_id, key)
    if existing is None:
        # Expired or released between the two calls; one more try
        if await database.reserve_idempotency_key(record):
            return None
        existing = await database.get_idempotency_key(tenant_id, key)
        if existing is None:
            raise ScanError(409, "Please try again.")

    if existing["fingerprint"] != request_fingerprint:
        raise ScanError(422, f"This {HEADER} was already used with a different upload or settings. Use a new key for a new scan.")
    if existing["state"] != "done":
        raise ScanError(409, "A request with this key is still being processed. Try again in a moment.")
    return Replay(existing["status_code"], existing["body"])


async def complete(tenant_id: str, key: str, status_code: int, body: dict) -> None:
    try:
        await database.complete_idempotency_key(tenant_id, key, status_code, body)
    except DatabaseError:
        # The job exists; only replay protection is lost. Release so a retry is not stuck on 409.
        logger.error(f"Could not store the response for idempotency key {key}")
        await release(tenant_id, key)


async def release(tenant_id: str, key: str) -> None:
    """Give the key back after a failed attempt, so the client can retry with the same key"""
    try:
        await database.release_idempotency_key(tenant_id, key)
    except DatabaseError:
        logger.error(f"Could not release idempotency key {key}")
