from fastapi import APIRouter, Depends, HTTPException

from deps import get_tenant_id
from models import JobResponse
from services import jobs

router = APIRouter(tags=["Resume Analysis"])


@router.get("/jobs/{job_id}", response_model=JobResponse, name="get_job")
async def get_job(job_id: str, tenant_id: str = Depends(get_tenant_id)):
    """
    Status of a queued scan.

    `status` is `queued`, `running`, `succeeded` or `failed`. When it succeeds, `result` holds the
    finished scan (the same object `GET /scan/{id}` returns). When it fails, `error` says why.
    Finished jobs are kept for 24 hours.
    """
    job = await jobs.describe(job_id, tenant_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
