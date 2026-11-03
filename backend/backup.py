"""Database backups, and restoring them without bringing deleted data back.

A backup is one file: gzip-compressed JSON lines, optionally encrypted with Fernet. The first line
describes it; every other line is one document. It holds accounts, organisations, plans, scans,
stored-file records, usage, the audit trail and erasure tombstones. It does not hold queued jobs
(they carry uploaded files and are short-lived), idempotency keys, or the resume files themselves:
back those up with the storage provider (S3 versioning or replication).

  BACKUP_DIR                  where backups go (default backend/backups). Copy them off this machine.
  BACKUP_ENCRYPTION_KEY       a Fernet key; set it, because backups contain personal data.
                              Make one with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
  BACKUP_RETENTION_DAYS       backups older than this are deleted (default 14)
  BACKUP_INTERVAL_HOURS       run a backup this often inside the app (default 0 = only when asked)

Deleting data does not edit existing backups. So every erasure also leaves a tombstone, and a restore
re-applies the tombstones afterwards. Erased data therefore disappears from backups for good once
they pass BACKUP_RETENTION_DAYS, and never reappears in the live database after a restore.
"""
import asyncio
import gzip
import io
import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

from bson import json_util

logger = logging.getLogger(__name__)

FORMAT_VERSION = 1
BACKED_UP = [
    "users", "organizations", "memberships", "plans",
    "resume_scans", "scan_files", "usage_records",
    "audit_events", "erasure_tombstones",
]
# Dates must come back timezone-aware (UTC), like the dates the app stores and compares against
JSON_OPTIONS = json_util.JSONOptions(json_mode=json_util.JSONMode.RELAXED, tz_aware=True, tzinfo=timezone.utc)
_NAME = re.compile(r"^backup-(\d{8}T\d{6}Z)\.jsonl\.gz(\.enc)?$")


class BackupError(Exception):
    pass


def backup_dir() -> Path:
    return Path(os.getenv("BACKUP_DIR") or Path(__file__).parent / "backups")


def retention_days() -> int:
    return int(os.getenv("BACKUP_RETENTION_DAYS", "14"))


def _fernet(key: Optional[str]):
    if not key:
        return None
    from cryptography.fernet import Fernet
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except ValueError as e:
        raise BackupError("BACKUP_ENCRYPTION_KEY is not a valid Fernet key.") from e


async def create_backup(db, directory: Optional[Path] = None, encryption_key: Optional[str] = None,
                        now: Optional[datetime] = None) -> Path:
    """Write a backup of the database and return the file. Encrypts when a key is given."""
    directory = Path(directory or backup_dir())
    directory.mkdir(parents=True, exist_ok=True)
    now = now or datetime.now(timezone.utc)
    key = encryption_key if encryption_key is not None else os.getenv("BACKUP_ENCRYPTION_KEY")
    fernet = _fernet(key)
    if fernet is None:
        logger.warning("Writing an UNENCRYPTED backup. Set BACKUP_ENCRYPTION_KEY: backups contain personal data.")

    lines, counts = [], {}
    for name in BACKED_UP:
        docs = [doc async for doc in db[name].find({}, {"_id": 0})]
        counts[name] = len(docs)
        lines += [json_util.dumps({"c": name, "d": doc}, json_options=JSON_OPTIONS) for doc in docs]
    header = json_util.dumps({
        "type": "header", "version": FORMAT_VERSION, "created_at": now, "counts": counts, "encrypted": fernet is not None,
    }, json_options=JSON_OPTIONS)

    payload = gzip.compress(("\n".join([header] + lines) + "\n").encode("utf-8"))
    if fernet is not None:
        payload = fernet.encrypt(payload)

    path = directory / f"backup-{now.strftime('%Y%m%dT%H%M%SZ')}.jsonl.gz{'.enc' if fernet else ''}"
    tmp = path.with_suffix(path.suffix + ".part")
    tmp.write_bytes(payload)
    os.replace(tmp, path)  # never leave a half-written file that looks like a backup
    logger.info(f"Backup written: {path.name} ({sum(counts.values())} documents)")
    return path


def read_backup(path: Path, encryption_key: Optional[str] = None) -> Dict[str, List[dict]]:
    """Load a backup file into {collection: [documents]}"""
    path = Path(path)
    raw = path.read_bytes()
    if path.name.endswith(".enc"):
        fernet = _fernet(encryption_key if encryption_key is not None else os.getenv("BACKUP_ENCRYPTION_KEY"))
        if fernet is None:
            raise BackupError("This backup is encrypted. Provide BACKUP_ENCRYPTION_KEY.")
        from cryptography.fernet import InvalidToken
        try:
            raw = fernet.decrypt(raw)
        except InvalidToken as e:
            raise BackupError("Wrong encryption key, or the backup is corrupted.") from e
    try:
        text = gzip.decompress(raw).decode("utf-8")
    except (OSError, EOFError, UnicodeDecodeError) as e:
        raise BackupError("The backup file is corrupted.") from e

    rows = [json_util.loads(line, json_options=JSON_OPTIONS) for line in text.splitlines() if line.strip()]
    if not rows or rows[0].get("type") != "header":
        raise BackupError("This is not a backup file.")
    if rows[0]["version"] > FORMAT_VERSION:
        raise BackupError("This backup was made by a newer version of the app.")

    data: Dict[str, List[dict]] = {name: [] for name in BACKED_UP}
    for row in rows[1:]:
        if row["c"] in data:
            data[row["c"]].append(row["d"])
    for name, expected in rows[0]["counts"].items():
        if name in data and len(data[name]) != expected:
            raise BackupError(f"The backup is incomplete: {name} has {len(data[name])} of {expected} documents.")
    return data


def list_backups(directory: Optional[Path] = None) -> List[Path]:
    directory = Path(directory or backup_dir())
    if not directory.is_dir():
        return []
    return sorted(p for p in directory.iterdir() if _NAME.match(p.name))


def prune_backups(directory: Optional[Path] = None, keep_days: Optional[int] = None,
                  now: Optional[datetime] = None) -> int:
    """Delete backups older than the retention period (by the date in the file name). Returns how many."""
    keep_days = retention_days() if keep_days is None else keep_days
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=keep_days)
    removed = 0
    for path in list_backups(directory):
        made = datetime.strptime(_NAME.match(path.name).group(1), "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        if made < cutoff:
            path.unlink(missing_ok=True)
            removed += 1
    if removed:
        logger.info(f"Removed {removed} expired backup(s)")
    return removed


async def apply_tombstones(db, tombstones: List[dict]) -> Dict[str, int]:
    """Delete again whatever was erased after a backup was taken. Returns what was removed."""
    removed = {"scans": 0, "users": 0, "organizations": 0}
    for t in tombstones:
        kind, ident, erased_at = t["kind"], t["id"], t["erased_at"]
        if kind == "scan":
            removed["scans"] += (await db.resume_scans.delete_many({"id": ident})).deleted_count
            await db.scan_files.delete_many({"scan_id": ident})
        elif kind in ("org_data", "org"):
            # Only what existed when the erasure happened; later scans are new data
            scans = [d async for d in db.resume_scans.find({"org_id": ident, "created_at": {"$lte": erased_at}}, {"id": 1})]
            ids = [d["id"] for d in scans]
            removed["scans"] += (await db.resume_scans.delete_many({"id": {"$in": ids}})).deleted_count
            await db.scan_files.delete_many({"scan_id": {"$in": ids}})
            await db.usage_records.delete_many({"tenant_id": ident, "created_at": {"$lte": erased_at}})
            if kind == "org":
                removed["organizations"] += (await db.organizations.delete_many({"id": ident})).deleted_count
                await db.memberships.delete_many({"org_id": ident})
        elif kind == "user":
            removed["users"] += (await db.users.delete_many({"id": ident})).deleted_count
            await db.memberships.delete_many({"user_id": ident})
    return removed


async def restore_backup(db, path: Path, encryption_key: Optional[str] = None, replace: bool = False,
                         extra_tombstones: Optional[List[dict]] = None) -> Dict[str, int]:
    """Load a backup into `db`, then re-apply every erasure made since.

    Refuses to touch a database that already has data unless replace=True. When replacing, the
    tombstones already in that database are kept and re-applied, which is what stops erased data
    returning when you restore over a live database.
    """
    data = read_backup(path, encryption_key)

    existing = sum([await db[name].count_documents({}) for name in BACKED_UP])
    if existing and not replace:
        raise BackupError("The target database already has data. Pass replace to overwrite it.")

    live_tombstones = [t async for t in db.erasure_tombstones.find({}, {"_id": 0})]
    for name in BACKED_UP:
        await db[name].delete_many({})
        if data[name]:
            await db[name].insert_many([dict(doc) for doc in data[name]])

    # Union of what the backup knew, what the live database had, and anything the caller supplies
    def aware(moment):
        return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)

    seen, tombstones = set(), []
    for t in data["erasure_tombstones"] + live_tombstones + list(extra_tombstones or []):
        marker = (t["kind"], t["id"], aware(t["erased_at"]))
        if marker not in seen:
            seen.add(marker)
            tombstones.append(t)
    in_backup = {(t["kind"], t["id"], aware(t["erased_at"])) for t in data["erasure_tombstones"]}
    missing = [t for t in tombstones if (t["kind"], t["id"], aware(t["erased_at"])) not in in_backup]
    if missing:
        await db.erasure_tombstones.insert_many([dict(t) for t in missing])

    removed = await apply_tombstones(db, tombstones)
    logger.info(f"Restored {path.name}; re-applied {len(tombstones)} erasure(s): {removed}")
    return {name: len(docs) for name, docs in data.items()} | {"reapplied_erasures": len(tombstones)}


async def backup_loop(db_getter, interval_hours: float) -> None:
    """Take a backup every `interval_hours` and prune old ones, until cancelled"""
    while True:
        try:
            await create_backup(db_getter())
            prune_backups()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"Scheduled backup failed: {e}")
        await asyncio.sleep(interval_hours * 3600)
