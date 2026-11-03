from typing import List

from fastapi import APIRouter, Depends, HTTPException

from accounts import ConfirmOrganizationName, ErasureSummary, MemberPublic, OrganizationPublic, Plan, Principal
from database import database
from deps import get_file_storage, get_principal, require_admin
from models import utc_now
from services import account_service, audit, erasure
from services.errors import ScanError
from services.quota import usage_report
from storage import FileStorage

router = APIRouter(tags=["Organisation"])


async def _organization(principal: Principal) -> dict:
    org = await database.get_organization(principal.org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organisation not found. Accounts are not in use on this server.")
    return org


@router.get("/plans", response_model=List[Plan])
async def list_plans():
    """The available plans and their limits."""
    return [Plan(**doc) for doc in await database.list_plans()]


@router.get("/orgs/current", response_model=OrganizationPublic)
async def current_organization(principal: Principal = Depends(get_principal)):
    """Your organisation, its plan and how many people belong to it."""
    return await account_service.organization_public(await _organization(principal))


@router.get("/orgs/current/members", response_model=List[MemberPublic])
async def members(principal: Principal = Depends(require_admin)):
    """The people in your organisation. Owners and admins only."""
    await _organization(principal)
    result = []
    for membership in await database.list_members(principal.org_id):
        user = await database.get_user(membership["user_id"])
        if user:
            result.append(MemberPublic(user_id=user["id"], email=user["email"], name=user["name"],
                                       role=membership["role"], joined_at=membership.get("created_at")))
    return result


@router.get("/orgs/current/export")
async def export_organization_data(principal: Principal = Depends(require_admin)):
    """Everything stored for your organisation, as JSON: the organisation, its scans and this month's usage.
    Owners and admins only. Stored resume files are not included."""
    org = await _organization(principal)
    scans = await database.list_scans_for_org(principal.org_id)
    await audit.record("organization_data_exported", principal.org_id, principal.user_id, scans=len(scans))
    return {
        "exported_at": utc_now(),
        "organization": await account_service.organization_public(org),
        "scans": scans,
        "usage_this_month": await usage_report(principal.org_id),
    }


@router.post("/orgs/current/erase-data", response_model=ErasureSummary)
async def erase_organization_data(
    confirmation: ConfirmOrganizationName,
    principal: Principal = Depends(require_admin),
    storage: FileStorage = Depends(get_file_storage),
):
    """Permanently delete all of your organisation's scans, stored resume files, queued jobs and usage
    records. Accounts and the plan stay. Type the organisation's name to confirm. This cannot be undone."""
    org = await _organization(principal)
    if principal.user_id and principal.role != "owner":
        raise ScanError(403, "Only an owner can erase the organisation's data.")
    if " ".join(confirmation.organization_name.split()) != org["name"]:
        raise ScanError(400, "The name does not match the organisation's name.")
    return await erasure.erase_org_data(principal.org_id, storage, principal.user_id)
