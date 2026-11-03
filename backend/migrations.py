"""Versioned schema changes for MongoDB.

Each migration runs once per database. Applied versions are recorded in the
`schema_migrations` collection. Migrations must be idempotent, because two
app instances starting at the same moment may both run the same one.

To change the schema, append a new numbered entry to MIGRATIONS. Never edit or
reorder an entry that has already shipped.
"""
import logging
from datetime import datetime, timezone

from pymongo import ASCENDING, DESCENDING

logger = logging.getLogger(__name__)


async def _001_scan_indexes(db) -> None:
    # Lookups, deletes and the unique guard all use the public scan id
    await db.resume_scans.create_index([("id", ASCENDING)], unique=True, name="uniq_scan_id")
    # The history list is always newest first
    await db.resume_scans.create_index([("created_at", DESCENDING)], name="scan_created_at_desc")


async def _002_backfill_scan_flags(db) -> None:
    # Scans stored before these fields existed
    await db.resume_scans.update_many({"is_fallback": {"$exists": False}}, {"$set": {"is_fallback": False}})
    await db.resume_scans.update_many({"fallback_notice": {"$exists": False}}, {"$set": {"fallback_notice": None}})
    await db.resume_scans.update_many({"saved": {"$exists": False}}, {"$set": {"saved": True}})


async def _003_scan_file_indexes(db) -> None:
    # One stored original per scan; the retention sweep looks up files by expiry date
    await db.scan_files.create_index([("scan_id", ASCENDING)], unique=True, name="uniq_file_scan_id")
    await db.scan_files.create_index([("expires_at", ASCENDING)], name="file_expires_at")


async def _004_usage_indexes(db) -> None:
    # Quota checks and usage summaries read one tenant's records for the current month
    await db.usage_records.create_index([("tenant_id", ASCENDING), ("created_at", DESCENDING)], name="usage_tenant_month")
    await db.usage_records.create_index([("scan_id", ASCENDING)], name="usage_scan_id")


async def _005_job_and_idempotency_indexes(db) -> None:
    await db.scan_jobs.create_index([("id", ASCENDING)], unique=True, name="uniq_job_id")
    # Workers claim the oldest queued job; per-tenant limits count a tenant's pending jobs
    await db.scan_jobs.create_index([("status", ASCENDING), ("seq", ASCENDING)], name="job_status_seq")
    await db.scan_jobs.create_index([("tenant_id", ASCENDING), ("status", ASCENDING)], name="job_tenant_status")
    # One idempotency key per tenant; the unique index is what makes two simultaneous retries safe
    await db.idempotency_keys.create_index(
        [("tenant_id", ASCENDING), ("key", ASCENDING)], unique=True, name="uniq_idempotency_key"
    )
    await db.idempotency_keys.create_index([("created_at", ASCENDING)], name="idempotency_created")


async def _006_accounts_plans_and_ownership(db) -> None:
    await db.users.create_index([("email", ASCENDING)], unique=True, name="uniq_user_email")
    await db.users.create_index([("id", ASCENDING)], unique=True, name="uniq_user_id")
    await db.organizations.create_index([("id", ASCENDING)], unique=True, name="uniq_org_id")
    await db.organizations.create_index([("plan_id", ASCENDING)], name="org_plan")
    await db.memberships.create_index([("org_id", ASCENDING), ("user_id", ASCENDING)], unique=True, name="uniq_membership")
    await db.memberships.create_index([("user_id", ASCENDING)], name="membership_user")
    await db.plans.create_index([("id", ASCENDING)], unique=True, name="uniq_plan_id")
    await db.resume_scans.create_index([("org_id", ASCENDING), ("created_at", DESCENDING)], name="scan_org_created")
    await db.scan_files.create_index([("org_id", ASCENDING)], name="file_org")
    await db.audit_events.create_index([("created_at", ASCENDING)], name="audit_created")
    await db.erasure_tombstones.create_index([("erased_at", ASCENDING)], name="tombstone_erased")

    # Plans live in the database so limits can change without a deploy. These numbers are starting
    # points: edit the documents (or run manage.py set-plan) to match what you actually sell.
    for plan in DEFAULT_PLANS:
        await db.plans.update_one({"id": plan["id"]}, {"$setOnInsert": plan}, upsert=True)

    # Everything stored before accounts existed belongs to the single default organisation
    await db.resume_scans.update_many({"org_id": {"$exists": False}}, {"$set": {"org_id": "default", "created_by": None}})
    await db.scan_files.update_many({"org_id": {"$exists": False}}, {"$set": {"org_id": "default"}})


DEFAULT_PLANS = [
    {"id": "free", "name": "Free", "scans_per_month": 20, "tokens_per_month": 200_000, "max_members": 1, "retention_days": 30},
    {"id": "pro", "name": "Pro", "scans_per_month": 500, "tokens_per_month": 5_000_000, "max_members": 5, "retention_days": 90},
    {"id": "business", "name": "Business", "scans_per_month": 5000, "tokens_per_month": 50_000_000, "max_members": 25, "retention_days": 365},
]

MIGRATIONS = [
    (1, "scan_indexes", _001_scan_indexes),
    (2, "backfill_scan_flags", _002_backfill_scan_flags),
    (3, "scan_file_indexes", _003_scan_file_indexes),
    (4, "usage_indexes", _004_usage_indexes),
    (5, "job_and_idempotency_indexes", _005_job_and_idempotency_indexes),
    (6, "accounts_plans_and_ownership", _006_accounts_plans_and_ownership),
]


async def run_migrations(db) -> int:
    """Apply every migration not yet recorded; returns how many ran"""
    applied = {doc["version"] async for doc in db.schema_migrations.find()}
    ran = 0
    for version, name, migrate in sorted(MIGRATIONS, key=lambda m: m[0]):
        if version in applied:
            continue
        logger.info(f"Applying migration {version:03d} {name}")
        await migrate(db)
        await db.schema_migrations.insert_one({
            "version": version,
            "name": name,
            "applied_at": datetime.now(timezone.utc),
        })
        ran += 1
    if ran:
        logger.info(f"Applied {ran} migration(s)")
    return ran
