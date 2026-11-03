from typing import Optional

from fastapi import Depends, Header, HTTPException, Request

from accounts import Principal
from services import account_service
from services.errors import ScanError

from ai_processor import AIResumeProcessor
from storage import FileStorage
from virus_scan import VirusScanner


def get_ai_processor(request: Request) -> AIResumeProcessor:
    """Dependency that returns the AI processor created at startup"""
    processor = getattr(request.app.state, "ai_processor", None)
    if processor is None:
        raise HTTPException(status_code=500, detail="AI processor not initialized")
    return processor


def get_job_runner(request: Request):
    return request.app.state.job_runner


def get_virus_scanner(request: Request) -> VirusScanner:
    return request.app.state.virus_scanner


def get_file_storage(request: Request) -> Optional[FileStorage]:
    """None when originals are not kept"""
    return request.app.state.file_storage


async def get_principal(authorization: Optional[str] = Header(None)) -> Principal:
    """Who is calling.

    A valid `Authorization: Bearer <token>` always identifies the caller. Without one, the request
    is refused when AUTH_REQUIRED=true, and otherwise runs as the single default organisation
    (local development only). A token that is present but wrong is always refused.
    """
    if not authorization:
        if account_service.auth_required():
            raise ScanError(401, "Sign in to use this API.", account_service.BEARER)
        return account_service.anonymous_principal()
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise ScanError(401, "Authorization must be 'Bearer <token>'.", account_service.BEARER)
    return await account_service.principal_from_token(token.strip())


def get_tenant_id(principal: Principal = Depends(get_principal)) -> str:
    """The organisation the request belongs to: the owner of scans, quotas and usage.

    It comes from the verified token, never from a header or the request body.
    """
    return principal.org_id


def require_admin(principal: Principal = Depends(get_principal)) -> Principal:
    if not principal.is_admin:
        raise ScanError(403, "Only an owner or admin can do this.")
    return principal


def require_user(principal: Principal = Depends(get_principal)) -> Principal:
    """For actions that need a real account, not the anonymous development principal"""
    if principal.user_id is None:
        raise ScanError(401, "Sign in to do this.", account_service.BEARER)
    return principal
