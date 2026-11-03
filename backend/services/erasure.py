"""Deleting personal data on request.

Deleting a scan, erasing an organisation's data, and deleting an account all go through here, so
each one removes everything that hangs off the data: the stored original file, queued or finished
jobs (which hold the uploaded file and the result), usage records and idempotency keys.

Every erasure also leaves a tombstone (ids and a time only). Backups are not edited, so a restore
re-applies the tombstones afterwards and the deleted data does not come back. See backup.py.
"""
import logging
from typing import Optional

from accounts import ErasureSummary, Principal
from database import DatabaseError, database
from models import utc_now
from services import audit
from services.errors import ScanError
from storage import FileStorage, StorageError

logger = logging.getLogger(__name__)


async def _remove_file(storage: Optional[FileStorage], record: dict) -> bool:
    """Remove a stored original and its record. A file that cannot be removed keeps its record,
    due for the next retention sweep, so it is retried instead of forgotten."""
    removed = False
    if storage is not None:
        try:
            await storage.delete(record["key"])
            removed = True
        except StorageError as e:
            logger.error(f"Could not delete stored file {record.get('key')}: {e}")
            await database.expire_file_record_now(record["scan_id"], utc_now())
            return False
    await database.delete_file_record(record["scan_id"])
    return removed or storage is None


async def remove_scan_dependents(scan_id: str, storage: Optional[FileStorage]) -> dict:
    """Jobs and the stored original that belong to a scan that is being deleted"""
    jobs = await database.delete_jobs_for_scan(scan_id)
    record = await database.get_file_record(scan_id)
    files = 1 if record and await _remove_file(storage, record) else 0
    return {"jobs": jobs, "files": files}


async def erase_scan(scan_id: str, org_id: str, storage: Optional[FileStorage], actor_user_id: Optional[str]) -> bool:
    """Delete one scan and everything attached to it. False when it does not exist."""
    if not await database.delete_scan(scan_id, org_id):
        return False
    await remove_scan_dependents(scan_id, storage)
    await database.add_tombstone({"kind": "scan", "id": scan_id, "org_id": org_id, "erased_at": utc_now()})
    await audit.record("scan_deleted", org_id, actor_user_id, scan_id=scan_id)
    return True


async def erase_org_data(org_id: str, storage: Optional[FileStorage], actor_user_id: Optional[str]) -> ErasureSummary:
    """Delete all of an organisation's scans, jobs, files and usage. Accounts and the plan stay."""
    summary = ErasureSummary()
    for record in await database.list_file_records_for_org(org_id):
        if await _remove_file(storage, record):
            summary.files += 1
    summary.scans = await database.delete_scans_for_org(org_id)
    summary.jobs = await database.delete_jobs_for_org(org_id)
    summary.usage_records = await database.delete_usage_for_org(org_id)
    await database.delete_idempotency_keys_for_org(org_id)
    await database.add_tombstone({"kind": "org_data", "id": org_id, "erased_at": utc_now()})
    await audit.record("organization_data_erased", org_id, actor_user_id, **summary.model_dump())
    return summary


async def delete_account(principal: Principal, storage: Optional[FileStorage]) -> dict:
    """Delete a user. If they were the only member, their organisation and all its data go too.

    Refuses when the user owns an organisation that other people still use, because deleting it
    would take their data away. Returns what was removed.
    """
    user_id = principal.user_id
    deleted_orgs = []
    for membership in await database.list_memberships_for_user(user_id):
        org_id = membership["org_id"]
        members = await database.list_members(org_id)
        others = [m for m in members if m["user_id"] != user_id]
        if not others:
            continue
        other_owners = [m for m in others if m["role"] == "owner"]
        if membership["role"] == "owner" and not other_owners:
            org = await database.get_organization(org_id)
            raise ScanError(
                409,
                f"You are the only owner of '{org['name'] if org else org_id}', which other people still use. "
                "Another owner is needed before you can delete your account.",
            )

    for membership in await database.list_memberships_for_user(user_id):
        org_id = membership["org_id"]
        others = [m for m in await database.list_members(org_id) if m["user_id"] != user_id]
        if not others:
            await erase_org_data(org_id, storage, user_id)
            await database.delete_memberships_for_org(org_id)
            await database.delete_organization(org_id)
            await database.add_tombstone({"kind": "org", "id": org_id, "erased_at": utc_now()})
            deleted_orgs.append(org_id)

    await database.delete_memberships_for_user(user_id)
    await database.delete_user(user_id)
    await database.add_tombstone({"kind": "user", "id": user_id, "erased_at": utc_now()})
    await audit.record("account_deleted", None, user_id, organizations_deleted=len(deleted_orgs))
    return {"organizations_deleted": len(deleted_orgs)}
