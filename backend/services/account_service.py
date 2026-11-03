"""Registering, signing in, and looking up who a request is from."""
import logging
import os
import uuid
from datetime import timedelta
from typing import Optional

from accounts import (
    DEFAULT_ORG_ID, AuthResponse, LoginRequest, OrganizationPublic, Plan, Principal, RegisterRequest, UserPublic,
)
from database import database
from models import utc_now
from security import (
    AuthError, AuthNotConfigured, create_access_token, decode_access_token, hash_password,
    password_needs_rehash, token_lifetime_seconds, validate_password_strength, verify_password,
)
from services import audit
from services.errors import ScanError

logger = logging.getLogger(__name__)

DEFAULT_PLAN_ID = "free"
BEARER = {"WWW-Authenticate": "Bearer"}


def auth_required() -> bool:
    """Whether every request must be signed in. Off only for local development."""
    return os.getenv("AUTH_REQUIRED", "false").lower() == "true"


def registration_enabled() -> bool:
    return os.getenv("REGISTRATION_ENABLED", "true").lower() == "true"


def _login_limits():
    return int(os.getenv("LOGIN_MAX_FAILURES", "5")), int(os.getenv("LOGIN_LOCK_MINUTES", "15"))


def normalize_email(email: str) -> str:
    return email.strip().lower()


def anonymous_principal() -> Principal:
    """Used when sign-in is not required: everything belongs to one organisation"""
    return Principal(user_id=None, org_id=os.getenv("DEFAULT_TENANT_ID", DEFAULT_ORG_ID), role="owner")


def user_public(user: dict) -> UserPublic:
    return UserPublic(id=user["id"], email=user["email"], name=user["name"], created_at=user["created_at"])


async def plan_of(org: Optional[dict]) -> Plan:
    """The plan an organisation is on; falls back to the free plan if its plan was removed"""
    for plan_id in ((org or {}).get("plan_id"), DEFAULT_PLAN_ID):
        doc = await database.get_plan(plan_id) if plan_id else None
        if doc:
            return Plan(**doc)
    return Plan(id=DEFAULT_PLAN_ID, name="Free", scans_per_month=20, tokens_per_month=200_000, max_members=1, retention_days=30)


async def organization_public(org: dict) -> OrganizationPublic:
    members = await database.list_members(org["id"])
    return OrganizationPublic(
        id=org["id"], name=org["name"], plan=await plan_of(org), member_count=len(members), created_at=org.get("created_at"),
    )


def _issue_token(user: dict, org_id: str) -> str:
    try:
        return create_access_token(user["id"], org_id, user.get("token_version", 0))
    except AuthNotConfigured as e:
        logger.error(str(e))
        raise ScanError(503, "Sign-in is not configured on this server.")


async def _auth_response(user: dict, org: dict, role: str) -> AuthResponse:
    return AuthResponse(
        access_token=_issue_token(user, org["id"]),
        expires_in=token_lifetime_seconds(),
        user=user_public(user),
        organization=await organization_public(org),
        role=role,
    )


async def register(request: RegisterRequest) -> AuthResponse:
    if not registration_enabled():
        raise ScanError(403, "Registration is closed.")
    email = normalize_email(request.email)
    problem = validate_password_strength(request.password, email)
    if problem:
        raise ScanError(400, problem)

    now = utc_now()
    user = {
        "id": uuid.uuid4().hex, "email": email, "name": request.name,
        "password_hash": hash_password(request.password),
        "token_version": 0, "failed_logins": 0, "locked_until": None,
        "created_at": now, "last_login_at": now,
    }
    org = {
        "id": uuid.uuid4().hex,
        "name": request.organization_name or f"{request.name}'s organisation",
        "plan_id": DEFAULT_PLAN_ID, "created_by": user["id"], "created_at": now,
    }
    if not await database.create_user(user):
        raise ScanError(409, "An account with this email already exists. Sign in instead.")
    try:
        await database.create_organization(org)
        await database.create_membership({"org_id": org["id"], "user_id": user["id"], "role": "owner", "created_at": now})
    except Exception:
        # No multi-document transactions on a single MongoDB server, so undo by hand
        await database.delete_memberships_for_user(user["id"])
        await database.delete_organization(org["id"])
        await database.delete_user(user["id"])
        raise

    await audit.record("account_registered", org["id"], user["id"])
    return await _auth_response(user, org, "owner")


async def login(request: LoginRequest) -> AuthResponse:
    email = normalize_email(request.email)
    user = await database.get_user_by_email(email)
    max_failures, lock_minutes = _login_limits()
    now = utc_now()

    if user and user.get("locked_until") and user["locked_until"] > now:
        minutes = max(1, int((user["locked_until"] - now).total_seconds() // 60) + 1)
        raise ScanError(429, f"Too many failed sign-in attempts. Try again in {minutes} minute(s).")

    # Always do the password work, so a missing account takes as long as a wrong password
    if not verify_password(request.password, user["password_hash"] if user else None) or not user:
        if user:
            failures = user.get("failed_logins", 0) + 1
            if failures >= max_failures:
                await database.update_user(user["id"], {"failed_logins": 0, "locked_until": now + timedelta(minutes=lock_minutes)})
                await audit.record("login_locked", None, user["id"])
            else:
                await database.update_user(user["id"], {"failed_logins": failures})
        raise ScanError(401, "Email or password is incorrect.", BEARER)

    memberships = await database.list_memberships_for_user(user["id"])
    org = await database.get_organization(memberships[0]["org_id"]) if memberships else None
    if org is None:
        raise ScanError(403, "This account does not belong to an organisation.")

    changes = {"failed_logins": 0, "locked_until": None, "last_login_at": now}
    if password_needs_rehash(user["password_hash"]):
        changes["password_hash"] = hash_password(request.password)
    await database.update_user(user["id"], changes)
    return await _auth_response({**user, **changes}, org, memberships[0]["role"])


async def principal_from_token(token: str) -> Principal:
    """Who a bearer token belongs to. Checks the user still exists, the token has not been
    revoked, and the user is still a member of the organisation in the token."""
    try:
        claims = decode_access_token(token)
    except AuthError as e:
        raise ScanError(401, str(e), BEARER)
    except AuthNotConfigured:
        raise ScanError(503, "Sign-in is not configured on this server.")

    user = await database.get_user(claims["sub"])
    if user is None or user.get("token_version", 0) != claims["tv"]:
        raise ScanError(401, "Your session is no longer valid. Sign in again.", BEARER)
    membership = await database.get_membership(claims["org"], user["id"])
    if membership is None:
        raise ScanError(401, "You no longer have access to this organisation. Sign in again.", BEARER)
    return Principal(user_id=user["id"], org_id=claims["org"], role=membership["role"], email=user["email"])


async def revoke_tokens(user_id: str) -> None:
    """Invalidate every token issued so far"""
    await database.update_user(user_id, inc_fields={"token_version": 1})
