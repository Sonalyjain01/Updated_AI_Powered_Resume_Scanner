from typing import List

from fastapi import APIRouter, Depends

from accounts import (
    AuthResponse, ChangePasswordRequest, LoginRequest, MeResponse, PasswordConfirmation, Principal, RegisterRequest,
)
from database import database
from deps import get_file_storage, get_principal, require_user
from models import utc_now
from security import hash_password, validate_password_strength, verify_password
from services import account_service, audit, erasure
from services.errors import ScanError
from storage import FileStorage

router = APIRouter(prefix="/auth", tags=["Account"])


@router.post("/register", response_model=AuthResponse, status_code=201)
async def register(request: RegisterRequest):
    """Create an account and its organisation (on the free plan), and sign in."""
    return await account_service.register(request)


@router.post("/login", response_model=AuthResponse)
async def login(request: LoginRequest):
    """Sign in. After 5 wrong passwords the account is locked for 15 minutes."""
    return await account_service.login(request)


@router.get("/me", response_model=MeResponse)
async def me(principal: Principal = Depends(get_principal)):
    """Who you are signed in as, your organisation and its plan."""
    if principal.user_id is None:
        return MeResponse(role=principal.role, auth_required=account_service.auth_required())
    user = await database.get_user(principal.user_id)
    org = await database.get_organization(principal.org_id)
    return MeResponse(
        user=account_service.user_public(user),
        organization=await account_service.organization_public(org),
        role=principal.role,
        auth_required=account_service.auth_required(),
    )


@router.post("/logout-all", status_code=204)
async def logout_everywhere(principal: Principal = Depends(require_user)):
    """Sign out of every device: all tokens issued so far stop working."""
    await account_service.revoke_tokens(principal.user_id)


@router.post("/change-password", response_model=AuthResponse)
async def change_password(request: ChangePasswordRequest, principal: Principal = Depends(require_user)):
    """Change your password. Every other session is signed out; the response carries a fresh token."""
    user = await database.get_user(principal.user_id)
    if not verify_password(request.current_password, user["password_hash"]):
        raise ScanError(400, "Your current password is incorrect.")
    problem = validate_password_strength(request.new_password, user["email"])
    if problem:
        raise ScanError(400, problem)
    await database.update_user(
        user["id"], {"password_hash": hash_password(request.new_password)}, inc_fields={"token_version": 1}
    )
    await audit.record("password_changed", principal.org_id, user["id"])
    fresh = await database.get_user(user["id"])
    org = await database.get_organization(principal.org_id)
    return await account_service._auth_response(fresh, org, principal.role)


@router.get("/me/export")
async def export_my_data(principal: Principal = Depends(require_user)):
    """Everything stored about you: your profile, your memberships and the scans you ran."""
    user = await database.get_user(principal.user_id)
    memberships, scans = [], []
    for membership in await database.list_memberships_for_user(user["id"]):
        org = await database.get_organization(membership["org_id"])
        memberships.append({"organization_id": membership["org_id"], "organization": org["name"] if org else None,
                            "role": membership["role"], "joined_at": membership.get("created_at")})
        scans += [s for s in await database.list_scans_for_org(membership["org_id"]) if s.get("created_by") == user["id"]]
    await audit.record("user_data_exported", principal.org_id, user["id"], scans=len(scans))
    return {
        "exported_at": utc_now(),
        "user": account_service.user_public(user),
        "memberships": memberships,
        "scans_you_ran": scans,
    }


@router.post("/delete-account")
async def delete_my_account(
    confirmation: PasswordConfirmation,
    principal: Principal = Depends(require_user),
    storage: FileStorage = Depends(get_file_storage),
):
    """Permanently delete your account.

    If you are the only member of your organisation, the organisation and all its scans, stored
    resume files and usage records are deleted as well. If other people use it and you are its only
    owner, this is refused until another owner exists. This cannot be undone.
    """
    user = await database.get_user(principal.user_id)
    if not verify_password(confirmation.password, user["password_hash"]):
        raise ScanError(400, "Your password is incorrect.")
    return await erasure.delete_account(principal, storage)
