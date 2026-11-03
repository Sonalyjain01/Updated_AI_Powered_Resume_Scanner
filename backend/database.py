from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError, PyMongoError
from typing import List, Optional
import os
from models import ResumeAnalysisResponse
from migrations import run_migrations
import logging

logger = logging.getLogger(__name__)


class DatabaseError(Exception):
    """The database could not be reached or a query failed.

    Raised instead of returning an empty result, so callers can tell an outage
    from a genuinely empty collection.
    """


class Database:
    def __init__(self):
        self.mongo_url = os.getenv('MONGO_URL', 'mongodb://localhost:27017')
        self.db_name = os.getenv('DB_NAME', 'resume_scanner')
        self.client: Optional[AsyncIOMotorClient] = None
        self.db = None

    async def connect(self):
        """Connect to MongoDB"""
        try:
            self.client = AsyncIOMotorClient(self.mongo_url, tz_aware=True)
            self.db = self.client[self.db_name]

            # Test connection
            await self.client.admin.command('ping')
            logger.info(f"Connected to MongoDB: {self.db_name}")
            if self.db_name == 'test_database':
                logger.warning("DB_NAME is 'test_database'. Use a dedicated database name for real data.")

            await run_migrations(self.db)

        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {str(e)}")
            raise

    async def close(self):
        """Close database connection"""
        if self.client:
            self.client.close()
            logger.info("Database connection closed")

    async def ping(self) -> bool:
        """True when the database answers; never raises"""
        try:
            await self.client.admin.command('ping')
            return True
        except Exception as e:
            logger.error(f"Database ping failed: {str(e)}")
            return False

    def _collection(self):
        if self.db is None:
            raise DatabaseError("Database is not connected")
        return self.db.resume_scans

    async def save_scan_result(self, scan_result: ResumeAnalysisResponse) -> str:
        """Save scan result to database; raises DatabaseError on failure"""
        try:
            result = await self._collection().insert_one(scan_result.model_dump())
            logger.info(f"Saved scan result with ID: {result.inserted_id}")
            return str(result.inserted_id)

        except PyMongoError as e:
            logger.error(f"Error saving scan result: {str(e)}")
            raise DatabaseError("Failed to save scan result") from e

    async def get_scan_history(self, org_id: str, limit: int = 50, skip: int = 0) -> List[ResumeAnalysisResponse]:
        """One organisation's scans, newest first; raises DatabaseError on failure"""
        try:
            cursor = self._collection().find({"org_id": org_id}).sort("created_at", -1).skip(skip).limit(limit)

            scan_results = []
            async for doc in cursor:
                doc.pop('_id', None)
                try:
                    scan_results.append(ResumeAnalysisResponse(**doc))
                except ValueError as e:
                    # One unreadable record should not hide the rest of the history
                    logger.error(f"Skipping unreadable scan record {doc.get('id')}: {str(e)}")

            logger.info(f"Retrieved {len(scan_results)} scan results")
            return scan_results

        except PyMongoError as e:
            logger.error(f"Error retrieving scan history: {str(e)}")
            raise DatabaseError("Failed to retrieve scan history") from e

    async def get_total_scans_count(self, org_id: str) -> int:
        """Number of scans one organisation has; raises DatabaseError on failure"""
        try:
            return await self._collection().count_documents({"org_id": org_id})

        except PyMongoError as e:
            logger.error(f"Error getting scan count: {str(e)}")
            raise DatabaseError("Failed to count scans") from e

    async def get_scan_by_id(self, scan_id: str, org_id: str) -> Optional[ResumeAnalysisResponse]:
        """A scan, only if it belongs to the organisation. None when missing or not theirs; raises DatabaseError on failure"""
        try:
            doc = await self._collection().find_one({"id": scan_id, "org_id": org_id})

            if doc:
                doc.pop('_id', None)
                return ResumeAnalysisResponse(**doc)

            return None

        except (PyMongoError, ValueError) as e:
            logger.error(f"Error retrieving scan by ID {scan_id}: {str(e)}")
            raise DatabaseError("Failed to retrieve scan") from e

    async def delete_scan(self, scan_id: str, org_id: str) -> bool:
        """Delete one of the organisation's scans. False when missing or not theirs; raises DatabaseError on failure"""
        try:
            result = await self._collection().delete_one({"id": scan_id, "org_id": org_id})

            if result.deleted_count > 0:
                logger.info(f"Deleted scan with ID: {scan_id}")
                return True

            return False

        except PyMongoError as e:
            logger.error(f"Error deleting scan {scan_id}: {str(e)}")
            raise DatabaseError("Failed to delete scan") from e

    # --- Stored original files -------------------------------------------------
    # Each record says where a scan's original upload lives and when it must go.

    def _files(self):
        if self.db is None:
            raise DatabaseError("Database is not connected")
        return self.db.scan_files

    async def save_file_record(self, record: dict) -> None:
        try:
            await self._files().insert_one(dict(record))
        except PyMongoError as e:
            logger.error(f"Error saving file record for scan {record.get('scan_id')}: {str(e)}")
            raise DatabaseError("Failed to save file record") from e

    async def get_file_record(self, scan_id: str) -> Optional[dict]:
        try:
            doc = await self._files().find_one({"scan_id": scan_id})
            if doc:
                doc.pop('_id', None)
            return doc
        except PyMongoError as e:
            raise DatabaseError("Failed to read file record") from e

    async def delete_file_record(self, scan_id: str) -> None:
        try:
            await self._files().delete_one({"scan_id": scan_id})
        except PyMongoError as e:
            raise DatabaseError("Failed to delete file record") from e

    async def expire_file_record_now(self, scan_id: str, now) -> None:
        """Make a record due for the next sweep, used when its file could not be removed"""
        try:
            await self._files().update_one({"scan_id": scan_id}, {"$set": {"expires_at": now}})
        except PyMongoError as e:
            raise DatabaseError("Failed to update file record") from e

    async def list_expired_files(self, now, limit: int = 100) -> List[dict]:
        try:
            records = []
            async for doc in self._files().find({"expires_at": {"$lte": now}}).sort("expires_at", 1).limit(limit):
                doc.pop('_id', None)
                records.append(doc)
            return records
        except PyMongoError as e:
            raise DatabaseError("Failed to list expired files") from e

    # --- AI usage records ------------------------------------------------------

    def _usage(self):
        if self.db is None:
            raise DatabaseError("Database is not connected")
        return self.db.usage_records

    async def save_usage_record(self, record: dict) -> None:
        try:
            await self._usage().insert_one(dict(record))
        except PyMongoError as e:
            logger.error(f"Error saving usage record for scan {record.get('scan_id')}: {str(e)}")
            raise DatabaseError("Failed to save usage record") from e

    async def usage_totals(self, tenant_id: str, since) -> dict:
        """Scans, tokens, cost and latency for one tenant from `since` onwards"""
        try:
            cursor = self._usage().aggregate([
                {"$match": {"tenant_id": tenant_id, "created_at": {"$gte": since}}},
                {"$group": {
                    "_id": None,
                    "scans": {"$sum": 1},
                    "input_tokens": {"$sum": "$input_tokens"},
                    "output_tokens": {"$sum": "$output_tokens"},
                    "cost_usd": {"$sum": "$cost_usd"},
                    "latency_ms": {"$sum": "$latency_ms"},
                    "fallbacks": {"$sum": {"$cond": ["$used_fallback", 1, 0]}},
                }},
            ])
            rows = [row async for row in cursor]
        except PyMongoError as e:
            raise DatabaseError("Failed to read usage") from e
        row = rows[0] if rows else {}
        return {
            "scans": row.get("scans", 0),
            "input_tokens": row.get("input_tokens", 0),
            "output_tokens": row.get("output_tokens", 0),
            "cost_usd": round(row.get("cost_usd", 0.0), 6),
            "latency_ms": row.get("latency_ms", 0.0),
            "fallbacks": row.get("fallbacks", 0),
        }

    # --- Background scan jobs --------------------------------------------------

    def _jobs(self):
        if self.db is None:
            raise DatabaseError("Database is not connected")
        return self.db.scan_jobs

    # The uploaded file travels in the job document so any worker can pick it up; it is removed
    # when the job finishes. Reads never return it.
    _JOB_VIEW = {"_id": 0, "file": 0}

    async def create_job(self, job: dict) -> None:
        try:
            await self._jobs().insert_one(dict(job))
        except PyMongoError as e:
            logger.error(f"Error creating job {job.get('id')}: {str(e)}")
            raise DatabaseError("Failed to create job") from e

    async def claim_next_job(self, now, worker: str) -> Optional[dict]:
        """Atomically take the oldest queued job; two workers can never get the same one"""
        try:
            job = await self._jobs().find_one_and_update(
                {"status": "queued"},
                {"$set": {"status": "running", "started_at": now, "worker": worker}, "$inc": {"attempts": 1}},
                sort=[("seq", 1)],
                return_document=ReturnDocument.AFTER,
            )
            if job is not None:
                job.pop("_id", None)
            return job
        except PyMongoError as e:
            raise DatabaseError("Failed to claim a job") from e

    async def get_job(self, job_id: str, tenant_id: str) -> Optional[dict]:
        """A job, only if it belongs to the tenant"""
        try:
            return await self._jobs().find_one({"id": job_id, "tenant_id": tenant_id}, self._JOB_VIEW)
        except PyMongoError as e:
            raise DatabaseError("Failed to read job") from e

    async def finish_job(self, job_id: str, fields: dict) -> None:
        """Record the outcome and drop the stored upload"""
        try:
            await self._jobs().update_one({"id": job_id}, {"$set": fields, "$unset": {"file": ""}})
        except PyMongoError as e:
            raise DatabaseError("Failed to update job") from e

    async def count_pending_jobs(self, tenant_id: str) -> int:
        try:
            return await self._jobs().count_documents({"tenant_id": tenant_id, "status": {"$in": ["queued", "running"]}})
        except PyMongoError as e:
            raise DatabaseError("Failed to count jobs") from e

    async def queue_position(self, seq: int) -> int:
        """Queued jobs that will be taken before the job with this sequence number"""
        try:
            return await self._jobs().count_documents({"status": "queued", "seq": {"$lt": seq}})
        except PyMongoError as e:
            raise DatabaseError("Failed to read queue position") from e

    async def requeue_stale_jobs(self, started_before, max_attempts: int, now) -> dict:
        """Recover jobs whose worker vanished: run them again, or fail them after too many tries"""
        try:
            stale = {"status": "running", "started_at": {"$lt": started_before}}
            failed = await self._jobs().update_many(
                {**stale, "attempts": {"$gte": max_attempts}},
                {"$set": {"status": "failed", "finished_at": now,
                          "error": {"status_code": 500, "detail": "The analysis was interrupted too many times. Please upload the resume again."}},
                 "$unset": {"file": ""}},
            )
            requeued = await self._jobs().update_many(stale, {"$set": {"status": "queued"}})
            return {"requeued": requeued.modified_count, "failed": failed.modified_count}
        except PyMongoError as e:
            raise DatabaseError("Failed to recover stale jobs") from e

    async def purge_finished_jobs(self, before) -> int:
        try:
            result = await self._jobs().delete_many({"status": {"$in": ["succeeded", "failed"]}, "finished_at": {"$lt": before}})
            return result.deleted_count
        except PyMongoError as e:
            raise DatabaseError("Failed to purge jobs") from e

    # --- Idempotency keys ------------------------------------------------------

    def _keys(self):
        if self.db is None:
            raise DatabaseError("Database is not connected")
        return self.db.idempotency_keys

    async def reserve_idempotency_key(self, record: dict) -> bool:
        """True if this call reserved the key; False if the key already exists"""
        try:
            await self._keys().insert_one(dict(record))
            return True
        except DuplicateKeyError:
            return False
        except PyMongoError as e:
            raise DatabaseError("Failed to reserve idempotency key") from e

    async def get_idempotency_key(self, tenant_id: str, key: str) -> Optional[dict]:
        try:
            return await self._keys().find_one({"tenant_id": tenant_id, "key": key}, {"_id": 0})
        except PyMongoError as e:
            raise DatabaseError("Failed to read idempotency key") from e

    async def complete_idempotency_key(self, tenant_id: str, key: str, status_code: int, body: dict) -> None:
        try:
            await self._keys().update_one(
                {"tenant_id": tenant_id, "key": key},
                {"$set": {"state": "done", "status_code": status_code, "body": body}},
            )
        except PyMongoError as e:
            raise DatabaseError("Failed to complete idempotency key") from e

    async def release_idempotency_key(self, tenant_id: str, key: str) -> None:
        try:
            await self._keys().delete_one({"tenant_id": tenant_id, "key": key})
        except PyMongoError as e:
            raise DatabaseError("Failed to release idempotency key") from e

    async def purge_idempotency_keys(self, before) -> int:
        try:
            result = await self._keys().delete_many({"created_at": {"$lt": before}})
            return result.deleted_count
        except PyMongoError as e:
            raise DatabaseError("Failed to purge idempotency keys") from e

    # --- Bulk scan access for exports, erasure and retention ---------------------

    async def list_scans_for_org(self, org_id: str, limit: int = 10000) -> List[dict]:
        try:
            docs = []
            async for doc in self._collection().find({"org_id": org_id}).sort("created_at", 1).limit(limit):
                doc.pop("_id", None)
                docs.append(doc)
            return docs
        except PyMongoError as e:
            raise DatabaseError("Failed to list scans") from e

    async def delete_scans_for_org(self, org_id: str, created_before=None) -> int:
        try:
            query = {"org_id": org_id}
            if created_before is not None:
                query["created_at"] = {"$lte": created_before}
            return (await self._collection().delete_many(query)).deleted_count
        except PyMongoError as e:
            raise DatabaseError("Failed to delete scans") from e

    async def pop_expired_scans(self, org_ids: List[str], cutoff, limit: int = 500) -> List[dict]:
        """Delete up to `limit` scans of these organisations older than the cutoff and return
        their ids and organisations, so the caller can remove what hangs off them"""
        try:
            found = []
            async for doc in self._collection().find(
                {"org_id": {"$in": org_ids}, "created_at": {"$lt": cutoff}}, {"id": 1, "org_id": 1}
            ).limit(limit):
                found.append({"id": doc["id"], "org_id": doc["org_id"]})
            if found:
                await self._collection().delete_many({"id": {"$in": [f["id"] for f in found]}})
            return found
        except PyMongoError as e:
            raise DatabaseError("Failed to expire scans") from e

    async def delete_jobs_for_scan(self, scan_id: str) -> int:
        try:
            return (await self._jobs().delete_many({"scan_id": scan_id})).deleted_count
        except PyMongoError as e:
            raise DatabaseError("Failed to delete jobs") from e

    async def delete_jobs_for_org(self, org_id: str) -> int:
        try:
            return (await self._jobs().delete_many({"tenant_id": org_id})).deleted_count
        except PyMongoError as e:
            raise DatabaseError("Failed to delete jobs") from e

    async def delete_usage_for_org(self, org_id: str) -> int:
        try:
            return (await self._usage().delete_many({"tenant_id": org_id})).deleted_count
        except PyMongoError as e:
            raise DatabaseError("Failed to delete usage records") from e

    async def delete_idempotency_keys_for_org(self, org_id: str) -> int:
        try:
            return (await self._keys().delete_many({"tenant_id": org_id})).deleted_count
        except PyMongoError as e:
            raise DatabaseError("Failed to delete idempotency keys") from e

    async def list_file_records_for_org(self, org_id: str) -> List[dict]:
        try:
            records = []
            async for doc in self._files().find({"org_id": org_id}):
                doc.pop("_id", None)
                records.append(doc)
            return records
        except PyMongoError as e:
            raise DatabaseError("Failed to list stored files") from e

    # --- Users, organisations, memberships, plans ----------------------------------

    def _coll(self, name: str):
        if self.db is None:
            raise DatabaseError("Database is not connected")
        return self.db[name]

    async def _one(self, name: str, query: dict):
        try:
            doc = await self._coll(name).find_one(query)
        except PyMongoError as e:
            raise DatabaseError(f"Failed to read {name}") from e
        if doc:
            doc.pop("_id", None)
        return doc

    async def _many(self, name: str, query: dict, sort=None, limit: int = 1000) -> List[dict]:
        try:
            cursor = self._coll(name).find(query)
            if sort:
                cursor = cursor.sort(sort)
            docs = []
            async for doc in cursor.limit(limit):
                doc.pop("_id", None)
                docs.append(doc)
            return docs
        except PyMongoError as e:
            raise DatabaseError(f"Failed to read {name}") from e

    async def _insert(self, name: str, doc: dict) -> bool:
        """True when inserted, False when a unique index rejected it"""
        try:
            await self._coll(name).insert_one(dict(doc))
            return True
        except DuplicateKeyError:
            return False
        except PyMongoError as e:
            raise DatabaseError(f"Failed to write {name}") from e

    async def _update(self, name: str, query: dict, changes: dict) -> int:
        try:
            return (await self._coll(name).update_one(query, changes)).matched_count
        except PyMongoError as e:
            raise DatabaseError(f"Failed to update {name}") from e

    async def _delete(self, name: str, query: dict) -> int:
        try:
            return (await self._coll(name).delete_many(query)).deleted_count
        except PyMongoError as e:
            raise DatabaseError(f"Failed to delete from {name}") from e

    # users
    async def create_user(self, user: dict) -> bool:
        return await self._insert("users", user)

    async def get_user_by_email(self, email: str) -> Optional[dict]:
        return await self._one("users", {"email": email.lower()})

    async def get_user(self, user_id: str) -> Optional[dict]:
        return await self._one("users", {"id": user_id})

    async def update_user(self, user_id: str, set_fields: dict = None, inc_fields: dict = None, unset_fields: list = None) -> None:
        changes = {}
        if set_fields:
            changes["$set"] = set_fields
        if inc_fields:
            changes["$inc"] = inc_fields
        if unset_fields:
            changes["$unset"] = {name: "" for name in unset_fields}
        await self._update("users", {"id": user_id}, changes)

    async def delete_user(self, user_id: str) -> int:
        return await self._delete("users", {"id": user_id})

    # organisations
    async def create_organization(self, org: dict) -> bool:
        return await self._insert("organizations", org)

    async def get_organization(self, org_id: str) -> Optional[dict]:
        return await self._one("organizations", {"id": org_id})

    async def set_organization_plan(self, org_id: str, plan_id: str) -> bool:
        return bool(await self._update("organizations", {"id": org_id}, {"$set": {"plan_id": plan_id}}))

    async def list_organizations_on_plan(self, plan_id: str) -> List[dict]:
        return await self._many("organizations", {"plan_id": plan_id}, limit=100000)

    async def delete_organization(self, org_id: str) -> int:
        return await self._delete("organizations", {"id": org_id})

    # memberships
    async def create_membership(self, membership: dict) -> bool:
        return await self._insert("memberships", membership)

    async def get_membership(self, org_id: str, user_id: str) -> Optional[dict]:
        return await self._one("memberships", {"org_id": org_id, "user_id": user_id})

    async def list_members(self, org_id: str) -> List[dict]:
        return await self._many("memberships", {"org_id": org_id}, sort=[("created_at", 1)])

    async def list_memberships_for_user(self, user_id: str) -> List[dict]:
        return await self._many("memberships", {"user_id": user_id}, sort=[("created_at", 1)])

    async def delete_memberships_for_user(self, user_id: str) -> int:
        return await self._delete("memberships", {"user_id": user_id})

    async def delete_memberships_for_org(self, org_id: str) -> int:
        return await self._delete("memberships", {"org_id": org_id})

    # plans
    async def list_plans(self) -> List[dict]:
        return await self._many("plans", {}, sort=[("scans_per_month", 1)])

    async def get_plan(self, plan_id: str) -> Optional[dict]:
        return await self._one("plans", {"id": plan_id})

    # audit trail and erasure tombstones
    async def add_audit_event(self, event: dict) -> None:
        await self._insert("audit_events", event)

    async def purge_audit_events(self, before) -> int:
        return await self._delete("audit_events", {"created_at": {"$lt": before}})

    async def add_tombstone(self, tombstone: dict) -> None:
        await self._insert("erasure_tombstones", tombstone)

    async def list_tombstones(self) -> List[dict]:
        return await self._many("erasure_tombstones", {}, sort=[("erased_at", 1)], limit=1000000)

    async def purge_tombstones(self, before) -> int:
        return await self._delete("erasure_tombstones", {"erased_at": {"$lt": before}})

# Global database instance
database = Database()
