"""Keeping original resumes, and deleting them on schedule.

Every stored file has a record in `scan_files` with an `expires_at` date. A background
sweep removes expired files from storage and then drops their records. Deleting a scan
removes its file straight away.

FILE_RETENTION_DAYS        how long originals are kept (default 30)
RETENTION_SWEEP_MINUTES    how often the sweep runs (default 60)
"""
import asyncio
import hashlib
import logging
import os
from datetime import timedelta
from typing import Optional

from database import DatabaseError, database
from models import utc_now
from storage import FileStorage, StorageError, make_key

logger = logging.getLogger(__name__)


def retention_days() -> int:
    return int(os.getenv("FILE_RETENTION_DAYS", "30"))


def sweep_interval_seconds() -> float:
    return float(os.getenv("RETENTION_SWEEP_MINUTES", "60")) * 60


async def archive_original(
    storage: Optional[FileStorage], scan_id: str, filename: str, content: bytes, content_type: str,
    org_id: str = "default",
) -> bool:
    """Store a scan's original upload. Returns False (and logs) on failure; never raises."""
    if storage is None:
        return False

    key = make_key(scan_id, filename)
    now = utc_now()
    record = {
        "scan_id": scan_id,
        "org_id": org_id,
        "key": key,
        "filename": filename,
        "content_type": content_type,
        "size": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
        "created_at": now,
        "expires_at": now + timedelta(days=retention_days()),
    }
    try:
        await storage.put(key, content, content_type)
    except StorageError as e:
        logger.error(f"Could not store original for scan {scan_id}: {e}")
        return False

    try:
        await database.save_file_record(record)
    except DatabaseError:
        # A file nobody can find would never be deleted, so take it back out
        try:
            await storage.delete(key)
        except StorageError as e:
            logger.error(f"Orphaned stored file {key}: {e}")
        return False
    return True


async def delete_original(storage: Optional[FileStorage], scan_id: str) -> None:
    """Remove a scan's stored file. If storage fails, the record is made due for the next sweep."""
    if storage is None:
        return
    try:
        record = await database.get_file_record(scan_id)
        if not record:
            return
        try:
            await storage.delete(record["key"])
        except StorageError as e:
            logger.error(f"Could not delete stored file for scan {scan_id}, will retry in the next sweep: {e}")
            await database.expire_file_record_now(scan_id, utc_now())
            return
        await database.delete_file_record(scan_id)
    except DatabaseError as e:
        logger.error(f"Could not clean up stored file for scan {scan_id}: {e}")


async def purge_expired(storage: Optional[FileStorage], batch_size: int = 100) -> int:
    """Delete every file past its expiry date; returns how many were removed"""
    if storage is None:
        return 0
    removed = 0
    for record in await database.list_expired_files(utc_now(), limit=batch_size):
        try:
            await storage.delete(record["key"])
            await database.delete_file_record(record["scan_id"])
            removed += 1
        except (StorageError, DatabaseError) as e:
            logger.error(f"Retention sweep could not remove {record.get('key')}: {e}")
    if removed:
        logger.info(f"Retention sweep removed {removed} expired file(s)")
    return removed


async def retention_loop(storage: Optional[FileStorage]) -> None:
    """Run the sweep now and then repeatedly until cancelled"""
    while True:
        try:
            await purge_expired(storage)
        except asyncio.CancelledError:
            raise
        except Exception as e:  # the loop must survive a bad sweep
            logger.error(f"Retention sweep failed: {e}")
        await asyncio.sleep(sweep_interval_seconds())


async def purge_expired_scans(storage: Optional[FileStorage], batch_size: int = 500) -> int:
    """Delete scans older than their organisation's plan allows, with their stored files and jobs.

    Each plan has `retention_days` (0 keeps scans until someone deletes them). The default
    organisation used while sign-in is off follows SCAN_RETENTION_DAYS (0 = keep). A run handles
    up to `batch_size` scans per plan, and the next housekeeping run continues.
    """
    from services.erasure import remove_scan_dependents

    now = utc_now()
    groups = []  # (org ids, retention days)
    for plan in await database.list_plans():
        if plan["retention_days"] > 0:
            org_ids = [org["id"] for org in await database.list_organizations_on_plan(plan["id"])]
            if org_ids:
                groups.append((org_ids, plan["retention_days"]))
    default_days = int(os.getenv("SCAN_RETENTION_DAYS", "0"))
    if default_days > 0:
        groups.append(([os.getenv("DEFAULT_TENANT_ID", "default")], default_days))

    removed = 0
    for org_ids, days in groups:
        for scan in await database.pop_expired_scans(org_ids, now - timedelta(days=days), batch_size):
            await remove_scan_dependents(scan["id"], storage)
            removed += 1
    if removed:
        logger.info(f"Retention removed {removed} expired scan(s)")
    return removed
