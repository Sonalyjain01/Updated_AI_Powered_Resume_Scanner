import logging
import uuid
from typing import Optional, Tuple

from fastapi import UploadFile

from ai_processor import AIResumeProcessor
from database import DatabaseError, database
from file_processor import ExtractedText, FileProcessor
from models import ExtractedData, ResumeAnalysisResponse, utc_now
from scoring import ScoringCriteria
from services.errors import ScanError
from services.quota import check_quota
from services.retention import archive_original
from services.upload import read_upload_limited
from storage import FileStorage
from virus_scan import MalwareDetected, ScannerUnavailable, VirusScanner

logger = logging.getLogger(__name__)

MIN_JOB_DESCRIPTION_CHARS = 50
MIN_RESUME_TEXT_CHARS = 100

FALLBACK_NOTICE = (
    "The AI service could not complete this analysis, so a basic keyword comparison was used instead. "
    "Treat this score as a rough estimate and scan again for a full AI analysis."
)


def validate_job_description(job_description: str) -> None:
    if not job_description.strip():
        raise ScanError(400, "Job description cannot be empty")
    if len(job_description.strip()) < MIN_JOB_DESCRIPTION_CHARS:
        raise ScanError(400, f"Job description too short (minimum {MIN_JOB_DESCRIPTION_CHARS} characters)")


def validate_upload_headers(upload: UploadFile) -> str:
    """Cheap checks on extension and declared content type; returns the filename"""
    filename = upload.filename or ""
    if not FileProcessor.is_supported_file(filename):
        raise ScanError(
            400,
            f"Unsupported file type. Supported types: {', '.join(sorted(FileProcessor.SUPPORTED_EXTENSIONS))}"
        )
    try:
        FileProcessor.validate_mime_type(upload.content_type, filename)
    except ValueError as e:
        raise ScanError(400, str(e))
    return filename


async def scan_for_malware(scanner: VirusScanner, content: bytes, filename: str) -> None:
    """Refuse infected files, and refuse everything while the scanner is down (unless fail-open)"""
    try:
        await scanner.scan(content)
    except MalwareDetected as e:
        logger.warning(f"Rejected upload {filename}: {e}")
        raise ScanError(400, "This file was rejected because it contains malware.")
    except ScannerUnavailable as e:
        logger.error(f"Virus scanner unavailable: {e}")
        raise ScanError(503, "Uploads are temporarily unavailable because the virus scanner cannot be reached. Please try again shortly.")


async def extract_resume_text(content: bytes, filename: str) -> ExtractedText:
    """Extract the resume text, using OCR for scanned PDFs"""
    logger.info(f"Processing resume file: {filename}")

    try:
        extracted = await FileProcessor.extract_document(content, filename)
    except ValueError as e:
        raise ScanError(400, str(e))
    resume_text = extracted.text

    if len(resume_text.strip()) < MIN_RESUME_TEXT_CHARS:
        raise ScanError(
            400,
            "Resume appears to be too short or empty. Please ensure the file contains readable text."
        )
    logger.info(f"Extracted {len(resume_text)} characters from resume (OCR: {extracted.used_ocr})")
    return extracted


async def accept_upload(
    upload: UploadFile,
    job_description: str,
    scanner: VirusScanner,
    tenant_id: str,
) -> Tuple[str, bytes]:
    """Everything that can be refused before any real work: inputs, quota, size, malware, file type.

    Returns (filename, content).
    """
    validate_job_description(job_description)
    filename = validate_upload_headers(upload)
    await check_quota(tenant_id)
    content = await read_upload_limited(upload, FileProcessor.MAX_FILE_SIZE)
    await scan_for_malware(scanner, content, filename)
    try:
        # Cheap signature check, so a renamed or unsupported file is refused now, not minutes later
        FileProcessor.validate_magic_bytes(content, filename)
    except ValueError as e:
        raise ScanError(400, str(e))
    return filename, content


async def process_scan(
    ai_processor: AIResumeProcessor,
    content: bytes,
    filename: str,
    content_type: str,
    job_description: str,
    storage: Optional[FileStorage],
    tenant_id: str = "default",
    criteria: Optional[ScoringCriteria] = None,
    scan_id: Optional[str] = None,
    recheck_quota: bool = False,
    created_by: Optional[str] = None,
) -> ResumeAnalysisResponse:
    """Read, analyse and store one already-accepted resume. Used by the worker and the inline endpoint."""
    usage = ai_processor.new_usage_tracker()
    scan_id = scan_id or str(uuid.uuid4())
    used_fallback = True
    try:
        if recheck_quota:
            await check_quota(tenant_id)  # the allowance may have been used up while this job waited
        extracted = await extract_resume_text(content, filename)
        resume_text = extracted.text

        # One request id per scan; both AI calls share it and nothing else does
        scan_request_id = uuid.uuid4().hex
        extracted_data_dict, extraction_fallback = await ai_processor.extract_resume_data(
            resume_text, scan_request_id, usage
        )
        match = await ai_processor.calculate_match_score(
            resume_text, job_description, extracted_data_dict, scan_request_id, criteria, usage
        )
        match_score = match.score
        used_fallback = extraction_fallback or match.used_fallback

        analysis = ResumeAnalysisResponse(
            id=scan_id,
            filename=filename,
            extracted_data=ExtractedData(**extracted_data_dict),
            match_score=match_score,
            job_description=job_description,
            analysis_summary=match.summary,
            breakdown=match.breakdown,
            is_fallback=used_fallback,
            fallback_notice=FALLBACK_NOTICE if used_fallback else None,
            ocr_used=extracted.used_ocr,
            org_id=tenant_id,
            created_by=created_by,
        )

        # The AI work is already paid for, so a failed save still returns the result,
        # but the response says it was not stored instead of pretending it was.
        try:
            await database.save_scan_result(analysis)
        except DatabaseError:
            analysis.saved = False
        else:
            # Keep the original for the retention period; a failure here is logged, not shown
            await archive_original(
                storage, analysis.id, filename, content, content_type or "application/octet-stream", org_id=tenant_id
            )

        logger.info(f"Resume scan completed - Match Score: {match_score}% (fallback: {used_fallback})")
        return analysis

    except ScanError:
        raise
    except Exception as e:
        logger.error(f"Resume scan error: {str(e)}")
        raise ScanError(500, f"Resume processing failed: {str(e)}")
    finally:
        # Any scan that reached the AI is recorded, even one that later failed: the calls were made
        if usage.calls:
            try:
                await database.save_usage_record(usage.to_record(scan_id, tenant_id, utc_now(), used_fallback))
            except DatabaseError:
                logger.error(f"Usage for scan {scan_id} could not be recorded")


async def run_scan(
    ai_processor: AIResumeProcessor,
    upload: UploadFile,
    job_description: str,
    scanner: VirusScanner,
    storage: Optional[FileStorage],
    tenant_id: str = "default",
    criteria: Optional[ScoringCriteria] = None,
    created_by: Optional[str] = None,
) -> ResumeAnalysisResponse:
    """Do a whole scan inside the request. Kept for the original /scan_resume endpoint;
    new clients should queue a job with POST /scans instead."""
    filename, content = await accept_upload(upload, job_description, scanner, tenant_id)
    return await process_scan(
        ai_processor, content, filename, upload.content_type or "application/octet-stream",
        job_description, storage, tenant_id, criteria, created_by=created_by,
    )
