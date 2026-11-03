"""Background scan jobs.

POST /scans stores the upload as a job and returns at once; workers do the slow part (text
extraction, OCR, the AI calls) and the client polls GET /jobs/{id}.

The queue lives in MongoDB (`scan_jobs`), so jobs survive a restart and any number of app
processes can share it: a job is claimed with one atomic update, so two workers never run the
same one. Workers run inside the app by default (JOB_WORKERS), and the same JobRunner can be
started on its own in a separate process for heavier loads.

JOB_WORKERS                  concurrent workers in this process (default 2; 0 = do not run any)
JOB_POLL_SECONDS             how often an idle worker checks for jobs queued by other processes (default 1)
JOB_MAX_PENDING_PER_TENANT   queued + running jobs one tenant may have at once (default 20)
JOB_STALE_SECONDS            a running job older than this is assumed orphaned and re-queued (default 600)
JOB_MAX_ATTEMPTS             how many times a job may be started before it is failed (default 2)
JOB_RETENTION_HOURS          finished jobs, with their results, are deleted after this (default 24)
"""
import asyncio
import logging
import os
import time
import uuid
from datetime import timedelta
from typing import List, Optional

from ai_processor import AIResumeProcessor
from database import DatabaseError, database
from models import JobResponse, ResumeAnalysisResponse, utc_now
from request_context import reset_request_id, set_request_id
from scoring import ScoringCriteria
from services.errors import ScanError
from services.scan_service import process_scan
from storage import FileStorage

logger = logging.getLogger(__name__)

HOUSEKEEPING_INTERVAL_SECONDS = 300


def _int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


_last_seq = 0


def next_sequence() -> int:
    """A queue order number that always increases within this process.

    Database timestamps only have millisecond precision, so jobs queued in the same millisecond
    would tie. Nanosecond time keeps different processes in order; the max() handles a coarse clock.
    """
    global _last_seq
    _last_seq = max(time.time_ns(), _last_seq + 1)
    return _last_seq


def max_pending_per_tenant() -> int:
    return _int("JOB_MAX_PENDING_PER_TENANT", 20)


async def enqueue(
    tenant_id: str,
    filename: str,
    content: bytes,
    content_type: str,
    job_description: str,
    criteria: ScoringCriteria,
    request_id: str,
    created_by: Optional[str] = None,
) -> str:
    """Store a job and return its id. Raises a 429 ScanError when the tenant has too many waiting."""
    limit = max_pending_per_tenant()
    if limit > 0 and await database.count_pending_jobs(tenant_id) >= limit:
        raise ScanError(429, f"You already have {limit} scans waiting. Wait for some to finish, then try again.")

    job_id = uuid.uuid4().hex
    await database.create_job({
        "id": job_id,
        "tenant_id": tenant_id,
        "created_by": created_by,
        "status": "queued",
        "filename": filename,
        "content_type": content_type,
        "job_description": job_description,
        "criteria": criteria.model_dump(),
        "request_id": request_id,
        "file": content,
        "attempts": 0,
        "seq": next_sequence(),
        "created_at": utc_now(),
        "started_at": None,
        "finished_at": None,
        "scan_id": None,
        "result": None,
        "error": None,
    })
    return job_id


async def describe(job_id: str, tenant_id: str) -> Optional[JobResponse]:
    """The job as the API shows it, or None when it does not exist (or belongs to someone else)"""
    doc = await database.get_job(job_id, tenant_id)
    if doc is None:
        return None
    position = await database.queue_position(doc["seq"]) if doc["status"] == "queued" else None
    return JobResponse(
        id=doc["id"],
        status=doc["status"],
        filename=doc["filename"],
        created_at=doc["created_at"],
        started_at=doc.get("started_at"),
        finished_at=doc.get("finished_at"),
        queue_position=position,
        scan_id=doc.get("scan_id"),
        result=doc.get("result"),
        error=doc.get("error"),
    )


class JobRunner:
    """Workers that take queued jobs and run them"""

    def __init__(self, ai_processor: AIResumeProcessor, storage: Optional[FileStorage],
                 workers: Optional[int] = None):
        self.ai_processor = ai_processor
        self.storage = storage
        self.worker_count = _int("JOB_WORKERS", 2) if workers is None else workers
        self._wakeup = asyncio.Event()
        self._tasks: List[asyncio.Task] = []

    def notify(self) -> None:
        """Tell idle workers a job was just queued"""
        self._wakeup.set()

    async def start(self) -> None:
        if self.worker_count <= 0:
            logger.info("Background workers are off (JOB_WORKERS=0); jobs wait for a separate worker process")
            return
        await self.housekeeping()
        for index in range(self.worker_count):
            self._tasks.append(asyncio.create_task(self._work_loop(f"worker-{index}")))
        self._tasks.append(asyncio.create_task(self._housekeeping_loop()))
        logger.info(f"Started {self.worker_count} background worker(s)")

    async def stop(self) -> None:
        for task in self._tasks:
            task.cancel()
        for task in self._tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._tasks.clear()

    async def _work_loop(self, name: str) -> None:
        poll = float(os.getenv("JOB_POLL_SECONDS", "1"))
        while True:
            try:
                ran = await self.run_next(name)
            except asyncio.CancelledError:
                raise
            except Exception as e:  # a worker must survive any single failure
                logger.error(f"{name} error: {e}")
                ran = False
            if ran:
                continue
            self._wakeup.clear()
            try:
                await asyncio.wait_for(self._wakeup.wait(), timeout=poll)
            except asyncio.TimeoutError:
                pass

    async def run_next(self, worker: str = "inline") -> bool:
        """Claim and run one job. Returns False when nothing was waiting."""
        try:
            job = await database.claim_next_job(utc_now(), worker)
        except DatabaseError as e:
            logger.error(f"Could not claim a job: {e}")
            return False
        if job is None:
            return False
        await self._run(job)
        return True

    async def _run(self, job: dict) -> None:
        token = set_request_id(job.get("request_id") or "-")  # logs stay under the original request id
        try:
            logger.info(f"Job {job['id']} started (attempt {job.get('attempts', 1)})")
            outcome = await self._execute(job)
        finally:
            reset_request_id(token)
        try:
            await database.finish_job(job["id"], outcome)
        except DatabaseError as e:
            # The result is lost, but the job would be re-run after JOB_STALE_SECONDS, not stuck
            logger.error(f"Could not save the outcome of job {job['id']}: {e}")

    async def _execute(self, job: dict) -> dict:
        try:
            result: ResumeAnalysisResponse = await process_scan(
                self.ai_processor,
                bytes(job["file"]),
                job["filename"],
                job.get("content_type") or "application/octet-stream",
                job["job_description"],
                self.storage,
                tenant_id=job["tenant_id"],
                criteria=ScoringCriteria(**job.get("criteria", {})),
                recheck_quota=True,
                created_by=job.get("created_by"),
            )
            return {
                "status": "succeeded",
                "finished_at": utc_now(),
                "scan_id": result.id,
                "result": result.model_dump(),
            }
        except ScanError as e:
            logger.info(f"Job {job['id']} failed: {e.detail}")
            return {"status": "failed", "finished_at": utc_now(), "error": {"status_code": e.status_code, "detail": e.detail}}
        except Exception as e:
            logger.error(f"Job {job['id']} crashed: {e}")
            return {
                "status": "failed",
                "finished_at": utc_now(),
                "error": {"status_code": 500, "detail": "The analysis could not be completed. Please try again."},
            }

    async def housekeeping(self) -> None:
        """Recover orphaned jobs and delete old jobs and idempotency keys"""
        now = utc_now()
        try:
            stale = timedelta(seconds=_int("JOB_STALE_SECONDS", 600))
            recovered = await database.requeue_stale_jobs(now - stale, _int("JOB_MAX_ATTEMPTS", 2), now)
            if recovered["requeued"] or recovered["failed"]:
                logger.warning(f"Recovered orphaned jobs: {recovered}")
                self.notify()
            old_jobs = await database.purge_finished_jobs(now - timedelta(hours=_int("JOB_RETENTION_HOURS", 24)))
            from services.idempotency import ttl_hours
            old_keys = await database.purge_idempotency_keys(now - timedelta(hours=ttl_hours()))
            if old_jobs or old_keys:
                logger.info(f"Housekeeping removed {old_jobs} finished job(s) and {old_keys} idempotency key(s)")

            # Personal data past its retention period, and the records that outlive it
            from services.retention import purge_expired_scans
            await purge_expired_scans(self.storage)
            await database.purge_audit_events(now - timedelta(days=_int("AUDIT_RETENTION_DAYS", 365)))
            await database.purge_tombstones(now - timedelta(days=_int("TOMBSTONE_RETENTION_DAYS", 90)))
        except DatabaseError as e:
            logger.error(f"Housekeeping skipped: {e}")

    async def _housekeeping_loop(self) -> None:
        while True:
            await asyncio.sleep(HOUSEKEEPING_INTERVAL_SECONDS)
            try:
                await self.housekeeping()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"Housekeeping failed: {e}")
