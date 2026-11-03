"""Per-tenant monthly limits, checked before a scan starts.

QUOTA_SCANS_PER_MONTH    scans each tenant may run per calendar month (UTC); 0 = unlimited
QUOTA_TOKENS_PER_MONTH   AI tokens each tenant may use per month; 0 = unlimited

Usage is read from the usage records saved after every scan, so the numbers match what a
bill would be built from. The tenant comes from deps.get_tenant_id.
"""
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from accounts import DEFAULT_ORG_ID
from database import DatabaseError, database
from models import utc_now
from services.errors import ScanError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Quota:
    scans_per_month: int = 0
    tokens_per_month: int = 0


def env_quota() -> Quota:
    return Quota(
        scans_per_month=int(os.getenv("QUOTA_SCANS_PER_MONTH", "0")),
        tokens_per_month=int(os.getenv("QUOTA_TOKENS_PER_MONTH", "0")),
    )


async def load_quota(org_id: str) -> Quota:
    """The organisation's plan limits. An organisation with no record (the single default one
    used while sign-in is off) uses the QUOTA_* settings instead."""
    org = await database.get_organization(org_id)
    if org is None:
        return env_quota()
    plan = await database.get_plan(org.get("plan_id", ""))
    if plan is None:
        return env_quota()
    return Quota(scans_per_month=plan["scans_per_month"], tokens_per_month=plan["tokens_per_month"])


def month_start(now: Optional[datetime] = None) -> datetime:
    now = now or utc_now()
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


async def check_quota(tenant_id: str) -> None:
    """Raise a 429 ScanError when the tenant has used up its monthly allowance.

    If usage cannot be read (database down), the scan is allowed: scans already carry on
    without the database, and refusing paying users over a storage outage is worse than a
    brief overshoot.
    """
    try:
        quota = await load_quota(tenant_id)
        if quota.scans_per_month <= 0 and quota.tokens_per_month <= 0:
            return
        used = await database.usage_totals(tenant_id, month_start())
    except DatabaseError as e:
        logger.error(f"Quota check skipped, usage unavailable: {e}")
        return

    if quota.scans_per_month > 0 and used["scans"] >= quota.scans_per_month:
        raise ScanError(429, f"Monthly scan limit reached ({quota.scans_per_month} scans). The limit resets on the 1st.")
    tokens_used = used["input_tokens"] + used["output_tokens"]
    if quota.tokens_per_month > 0 and tokens_used >= quota.tokens_per_month:
        raise ScanError(429, "Monthly AI usage limit reached. The limit resets on the 1st.")


async def usage_report(tenant_id: str) -> dict:
    """This month's usage and what is left, for the usage endpoint"""
    quota = await load_quota(tenant_id)
    start = month_start()
    used = await database.usage_totals(tenant_id, start)
    tokens = used["input_tokens"] + used["output_tokens"]

    def remaining(limit: int, spent: int) -> Optional[int]:
        return None if limit <= 0 else max(0, limit - spent)

    return {
        "period_start": start,
        "scans": used["scans"],
        "fallback_scans": used["fallbacks"],
        "input_tokens": used["input_tokens"],
        "output_tokens": used["output_tokens"],
        "total_tokens": tokens,
        "cost_usd": used["cost_usd"],
        "average_latency_ms": round(used["latency_ms"] / used["scans"], 1) if used["scans"] else 0.0,
        "limits": {"scans": quota.scans_per_month or None, "tokens": quota.tokens_per_month or None},
        "remaining": {
            "scans": remaining(quota.scans_per_month, used["scans"]),
            "tokens": remaining(quota.tokens_per_month, tokens),
        },
    }
