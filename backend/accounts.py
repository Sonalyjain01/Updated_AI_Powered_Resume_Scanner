"""Account, organisation and plan models, shared by the database layer and the API."""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

DEFAULT_ORG_ID = "default"  # the single organisation used while sign-in is not required

ROLES = ("owner", "admin", "member")
ADMIN_ROLES = ("owner", "admin")


class Plan(BaseModel):
    id: str
    name: str
    scans_per_month: int = Field(..., description="0 means unlimited")
    tokens_per_month: int = Field(..., description="0 means unlimited")
    max_members: int = Field(..., description="0 means unlimited")
    retention_days: int = Field(..., description="Scans are deleted after this many days; 0 keeps them until deleted")


class UserPublic(BaseModel):
    id: str
    email: str
    name: str
    created_at: datetime


class OrganizationPublic(BaseModel):
    id: str
    name: str
    plan: Plan
    member_count: int = 1
    created_at: Optional[datetime] = None


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    name: str = Field(..., min_length=1, max_length=100)
    organization_name: Optional[str] = Field(default=None, max_length=100)

    @field_validator("name", "organization_name")
    @classmethod
    def tidy(cls, value):
        return " ".join(value.split()) if value else value


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., max_length=256)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., max_length=256)
    new_password: str = Field(..., max_length=256)


class PasswordConfirmation(BaseModel):
    password: str = Field(..., max_length=256)


class ConfirmOrganizationName(BaseModel):
    organization_name: str = Field(..., max_length=100, description="Type the organisation's name to confirm")


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserPublic
    organization: OrganizationPublic
    role: str


class MeResponse(BaseModel):
    user: Optional[UserPublic] = None
    organization: Optional[OrganizationPublic] = None
    role: str
    auth_required: bool


class MemberPublic(BaseModel):
    user_id: str
    email: str
    name: str
    role: str
    joined_at: Optional[datetime] = None


class ErasureSummary(BaseModel):
    scans: int = 0
    jobs: int = 0
    files: int = 0
    usage_records: int = 0


@dataclass(frozen=True)
class Principal:
    """Who a request is from. user_id is None when sign-in is not required."""

    user_id: Optional[str]
    org_id: str
    role: str
    email: Optional[str] = None

    @property
    def is_admin(self) -> bool:
        return self.role in ADMIN_ROLES
