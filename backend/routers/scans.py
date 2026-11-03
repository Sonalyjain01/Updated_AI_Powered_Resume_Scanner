from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse

from ai_processor import AIResumeProcessor
from database import database
from accounts import Principal
from deps import get_ai_processor, get_file_storage, get_job_runner, get_principal, get_virus_scanner
from models import JobAccepted, ResumeAnalysisResponse, ScanHistoryResponse
from request_context import get_request_id
from services.erasure import erase_scan
from scoring import parse_criteria
from services.errors import ScanError
from services import idempotency, jobs
from services.jobs import JobRunner
from services.scan_service import accept_upload, run_scan
from storage import FileStorage
from virus_scan import VirusScanner

router = APIRouter()


def _first_error(error: ValueError) -> str:
    """One readable sentence from a pydantic validation error"""
    errors = getattr(error, "errors", None)
    if callable(errors) and errors():
        first = errors()[0]
        where = ".".join(str(p) for p in first.get("loc", ()))
        message = first.get("msg", "").removeprefix("Value error, ")
        return f"{where}: {message}" if where else message
    return str(error)


def _parse_criteria_or_400(raw: str):
    try:
        return parse_criteria(raw)
    except ValueError as e:
        raise ScanError(400, f"Invalid scoring criteria: {_first_error(e)}")


@router.post("/scans", status_code=202, response_model=JobAccepted, tags=["Resume Analysis"])
async def create_scan(
    request: Request,
    resume_file: UploadFile = File(..., description="Resume file (PDF or DOCX)"),
    job_description: str = Form(..., description="Job description to match against"),
    criteria: str = Form("", description="Optional JSON: skills_weight, experience_weight, education_weight (0-100, relative) and required_skills (list)"),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key", description="Unique value per scan. Repeating the request with the same key returns the original job instead of creating another."),
    scanner: VirusScanner = Depends(get_virus_scanner),
    runner: JobRunner = Depends(get_job_runner),
    principal: Principal = Depends(get_principal),
):
    """
    Queue a resume scan and return immediately with a job to poll.

    The upload is checked first (type, size, malware, quota), then analysed in the background.
    Poll `GET /jobs/{job_id}` until `status` is `succeeded` or `failed`.
    """
    tenant_id = principal.org_id
    key = idempotency.validate_key(idempotency_key)
    scoring_criteria = _parse_criteria_or_400(criteria)

    filename, content = await accept_upload(resume_file, job_description, scanner, tenant_id)
    content_type = resume_file.content_type or "application/octet-stream"

    if key:
        fingerprint = idempotency.fingerprint(
            content, filename, job_description, idempotency.canonical_json(scoring_criteria.model_dump())
        )
        replay = await idempotency.begin(tenant_id, key, fingerprint)
        if replay is not None:
            return JSONResponse(
                replay.body, status_code=replay.status_code,
                headers={"Location": replay.body["status_url"], "Idempotent-Replay": "true"},
            )

    try:
        job_id = await jobs.enqueue(
            tenant_id, filename, content, content_type, job_description, scoring_criteria, get_request_id(),
            created_by=principal.user_id,
        )
    except BaseException:
        if key:
            await idempotency.release(tenant_id, key)  # let the client retry with the same key
        raise

    base = str(request.url_for("get_job", job_id=job_id).path)
    body = {"job_id": job_id, "status": "queued", "status_url": base}
    if key:
        await idempotency.complete(tenant_id, key, 202, body)
    runner.notify()
    return JSONResponse(body, status_code=202, headers={"Location": base})


@router.post("/scan_resume", response_model=ResumeAnalysisResponse, tags=["Resume Analysis"], deprecated=True)
async def scan_resume(
    resume_file: UploadFile = File(..., description="Resume file (PDF or DOCX)"),
    job_description: str = Form(..., description="Job description to match against"),
    criteria: str = Form("", description="Optional JSON: skills_weight, experience_weight, education_weight (0-100, relative) and required_skills (list)"),
    ai_processor: AIResumeProcessor = Depends(get_ai_processor),
    scanner: VirusScanner = Depends(get_virus_scanner),
    storage: FileStorage = Depends(get_file_storage),
    principal: Principal = Depends(get_principal),
):
    """
    Scan and analyze a resume inside this request. **Deprecated:** it holds the connection open for
    the whole AI analysis. Use `POST /scans` and poll the job instead.

    - **resume_file**: PDF or DOCX file containing the resume
    - **job_description**: Job description text to match against

    Returns extracted skills, education, experience, and match score
    """
    scoring_criteria = _parse_criteria_or_400(criteria)
    return await run_scan(
        ai_processor, resume_file, job_description, scanner, storage, principal.org_id, scoring_criteria,
        created_by=principal.user_id,
    )


@router.get("/scan_history", response_model=ScanHistoryResponse, tags=["History"])
async def get_scan_history(limit: int = 20, skip: int = 0, principal: Principal = Depends(get_principal)):
    """
    Get scan history with pagination

    - **limit**: Number of results to return (max 100)
    - **skip**: Number of results to skip for pagination

    Responds 503 when the database is unavailable.
    """
    limit = min(max(1, limit), 100)  # Clamp between 1 and 100
    skip = max(0, skip)

    scans = await database.get_scan_history(principal.org_id, limit=limit, skip=skip)
    total_count = await database.get_total_scans_count(principal.org_id)

    return ScanHistoryResponse(scans=scans, total_count=total_count)


@router.get("/scan/{scan_id}", response_model=ResumeAnalysisResponse, tags=["History"])
async def get_scan_by_id(scan_id: str, principal: Principal = Depends(get_principal)):
    """Get one of your organisation's scans by ID"""
    scan_result = await database.get_scan_by_id(scan_id, principal.org_id)

    if not scan_result:
        raise HTTPException(status_code=404, detail="Scan result not found")

    return scan_result


@router.delete("/scan/{scan_id}", tags=["History"])
async def delete_scan(
    scan_id: str,
    storage: FileStorage = Depends(get_file_storage),
    principal: Principal = Depends(get_principal),
):
    """Delete a scan and everything attached to it: the stored resume file and any queued job.

    Owners and admins can delete any of the organisation's scans; members can delete their own.
    """
    scan = await database.get_scan_by_id(scan_id, principal.org_id)
    if scan is None:
        raise HTTPException(status_code=404, detail="Scan result not found")
    if principal.user_id and not principal.is_admin and scan.created_by != principal.user_id:
        raise HTTPException(status_code=403, detail="Only an owner, an admin or the person who ran the scan can delete it.")

    await erase_scan(scan_id, principal.org_id, storage, principal.user_id)
    return {"message": "Scan deleted successfully"}
