def edit(p, pairs):
    s = open(p, encoding="utf-8").read()
    for a, b in pairs:
        assert s.count(a) == 1, (p, a[:70])
        s = s.replace(a, b)
    open(p, "w", encoding="utf-8").write(s)


edit("database.py", [
    ("# Global database instance", '''    # --- Sessions (refresh tokens) -------------------------------------------------

    async def create_session(self, session: dict) -> None:
        await self._insert("sessions", session)

    async def get_session(self, session_id: str) -> Optional[dict]:
        return await self._one("sessions", {"id": session_id})

    async def find_session_by_token_hash(self, token_hash: str) -> Optional[dict]:
        return await self._one("sessions", {"token_hash": token_hash})

    async def find_session_by_previous_hash(self, token_hash: str) -> Optional[dict]:
        return await self._one("sessions", {"prev_hash": token_hash})

    async def update_session(self, session_id: str, fields: dict) -> None:
        await self._update("sessions", {"id": session_id}, {"$set": fields})

    async def revoke_session(self, session_id: str, user_id: str, now) -> bool:
        """Revoke one of the user's sessions; False when it does not exist or is already revoked"""
        return bool(await self._update(
            "sessions", {"id": session_id, "user_id": user_id, "revoked_at": None}, {"$set": {"revoked_at": now}}
        ))

    async def revoke_user_sessions(self, user_id: str, now, except_session_id: str = None) -> None:
        try:
            query = {"user_id": user_id, "revoked_at": None}
            if except_session_id:
                query["id"] = {"$ne": except_session_id}
            await self._coll("sessions").update_many(query, {"$set": {"revoked_at": now}})
        except PyMongoError as e:
            raise DatabaseError("Failed to revoke sessions") from e

    async def list_active_sessions(self, user_id: str, now) -> List[dict]:
        return await self._many(
            "sessions", {"user_id": user_id, "revoked_at": None, "expires_at": {"$gt": now}}, sort=[("last_used_at", -1)]
        )

    async def delete_sessions_for_user(self, user_id: str) -> int:
        return await self._delete("sessions", {"user_id": user_id})

    async def purge_sessions(self, before) -> int:
        """Sessions that ended (expired or revoked) before `before`"""
        return await self._delete("sessions", {"$or": [
            {"expires_at": {"$lt": before}}, {"revoked_at": {"$lt": before}},
        ]})

    # --- One-time email tokens (verify email, reset password) -----------------------

    async def create_email_token(self, token: dict) -> None:
        await self._insert("email_tokens", token)

    async def use_email_token(self, kind: str, token_hash: str, now) -> Optional[dict]:
        """Atomically mark a valid, unused token as used and return it. A token works exactly once."""
        try:
            doc = await self._coll("email_tokens").find_one_and_update(
                {"kind": kind, "token_hash": token_hash, "used_at": None, "expires_at": {"$gt": now}},
                {"$set": {"used_at": now}},
                return_document=ReturnDocument.AFTER,
            )
        except PyMongoError as e:
            raise DatabaseError("Failed to use email token") from e
        if doc:
            doc.pop("_id", None)
        return doc

    async def invalidate_email_tokens(self, user_id: str, kind: str, now) -> None:
        try:
            await self._coll("email_tokens").update_many(
                {"user_id": user_id, "kind": kind, "used_at": None}, {"$set": {"used_at": now}}
            )
        except PyMongoError as e:
            raise DatabaseError("Failed to invalidate email tokens") from e

    async def delete_email_tokens_for_user(self, user_id: str) -> int:
        return await self._delete("email_tokens", {"user_id": user_id})

    async def purge_email_tokens(self, before) -> int:
        return await self._delete("email_tokens", {"expires_at": {"$lt": before}})

    # --- Invitations ---------------------------------------------------------------

    async def create_invitation(self, invitation: dict) -> bool:
        return await self._insert("invitations", invitation)

    async def list_pending_invitations(self, org_id: str, now) -> List[dict]:
        return await self._many(
            "invitations",
            {"org_id": org_id, "accepted_at": None, "revoked_at": None, "expires_at": {"$gt": now}},
            sort=[("created_at", -1)],
        )

    async def find_pending_invitation(self, org_id: str, email: str, now) -> Optional[dict]:
        return await self._one("invitations", {
            "org_id": org_id, "email": email, "accepted_at": None, "revoked_at": None, "expires_at": {"$gt": now},
        })

    async def get_invitation_by_hash(self, token_hash: str, now) -> Optional[dict]:
        """A pending (not accepted, revoked or expired) invitation"""
        return await self._one("invitations", {
            "token_hash": token_hash, "accepted_at": None, "revoked_at": None, "expires_at": {"$gt": now},
        })

    async def claim_invitation(self, invitation_id: str, now) -> bool:
        """Atomically accept an invitation; only one caller can win"""
        return bool(await self._update(
            "invitations", {"id": invitation_id, "accepted_at": None, "revoked_at": None},
            {"$set": {"accepted_at": now}},
        ))

    async def unclaim_invitation(self, invitation_id: str) -> None:
        await self._update("invitations", {"id": invitation_id}, {"$set": {"accepted_at": None}})

    async def revoke_invitation(self, org_id: str, invitation_id: str, now) -> bool:
        return bool(await self._update(
            "invitations", {"id": invitation_id, "org_id": org_id, "accepted_at": None, "revoked_at": None},
            {"$set": {"revoked_at": now}},
        ))

    async def delete_invitations_for_org(self, org_id: str) -> int:
        return await self._delete("invitations", {"org_id": org_id})

    async def purge_invitations(self, before) -> int:
        return await self._delete("invitations", {"expires_at": {"$lt": before}})

    # --- Members ---------------------------------------------------------------------

    async def set_member_role(self, org_id: str, user_id: str, role: str) -> bool:
        return bool(await self._update("memberships", {"org_id": org_id, "user_id": user_id}, {"$set": {"role": role}}))

    async def remove_membership(self, org_id: str, user_id: str) -> int:
        return await self._delete("memberships", {"org_id": org_id, "user_id": user_id})

    # --- Audit log and rate limits -------------------------------------------------

    async def list_audit_events(self, org_id: str, limit: int = 50, skip: int = 0, action: str = None) -> List[dict]:
        query = {"org_id": org_id}
        if action:
            query["action"] = action
        try:
            events = []
            async for doc in self._coll("audit_events").find(query).sort("created_at", -1).skip(skip).limit(limit):
                doc.pop("_id", None)
                events.append(doc)
            return events
        except PyMongoError as e:
            raise DatabaseError("Failed to read the audit log") from e

    async def count_audit_events(self, org_id: str, action: str = None) -> int:
        query = {"org_id": org_id}
        if action:
            query["action"] = action
        try:
            return await self._coll("audit_events").count_documents(query)
        except PyMongoError as e:
            raise DatabaseError("Failed to read the audit log") from e

    async def purge_rate_limits(self, before) -> int:
        return await self._delete("rate_limits", {"expires_at": {"$lt": before}})

# Global database instance'''),
])

edit("migrations.py", [
    ("DEFAULT_PLANS = [", '''async def _007_sessions_invitations_and_roles(db) -> None:
    await db.sessions.create_index([("id", ASCENDING)], unique=True, name="uniq_session_id")
    await db.sessions.create_index([("token_hash", ASCENDING)], name="session_token")
    await db.sessions.create_index([("prev_hash", ASCENDING)], name="session_prev_token", sparse=True)
    await db.sessions.create_index([("user_id", ASCENDING)], name="session_user")
    await db.email_tokens.create_index([("id", ASCENDING)], unique=True, name="uniq_email_token_id")
    await db.email_tokens.create_index([("token_hash", ASCENDING)], name="email_token_hash")
    await db.invitations.create_index([("id", ASCENDING)], unique=True, name="uniq_invitation_id")
    await db.invitations.create_index([("token_hash", ASCENDING)], name="invitation_token")
    await db.invitations.create_index([("org_id", ASCENDING), ("email", ASCENDING)], name="invitation_org_email")
    await db.rate_limits.create_index([("key", ASCENDING), ("window", ASCENDING)], unique=True, name="uniq_rate_window")
    await db.audit_events.create_index([("org_id", ASCENDING), ("created_at", DESCENDING)], name="audit_org_created")

    # The roles are now owner, admin, recruiter and viewer; what used to be "member" is a recruiter
    await db.memberships.update_many({"role": "member"}, {"$set": {"role": "recruiter"}})
    # People who registered before email confirmation existed keep working
    await db.users.update_many({"email_verified": {"$exists": False}}, {"$set": {"email_verified": True}})


DEFAULT_PLANS = ['''),
    ('    (6, "accounts_plans_and_ownership", _006_accounts_plans_and_ownership),\n',
     '    (6, "accounts_plans_and_ownership", _006_accounts_plans_and_ownership),\n    (7, "sessions_invitations_and_roles", _007_sessions_invitations_and_roles),\n'),
])

edit("accounts.py", [
    ('ROLES = ("owner", "admin", "member")\nADMIN_ROLES = ("owner", "admin")\n',
     'from permissions import ROLES, can  # noqa: E402  (roles and what they may do live in permissions.py)\n\nADMIN_ROLES = ("owner", "admin")\n'),
    ('''class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserPublic''', '''class AuthResponse(BaseModel):
    access_token: str = Field(..., description="Short-lived; send as 'Authorization: Bearer ...'")
    refresh_token: str = Field(..., description="Long-lived and single-use: exchange it at /auth/refresh for a new pair")
    token_type: str = "bearer"
    expires_in: int = Field(..., description="Seconds until the access token expires")
    session_id: str
    user: UserPublic'''),
    ('''    @property
    def is_admin(self) -> bool:
        return self.role in ADMIN_ROLES''', '''    session_id: Optional[str] = None

    @property
    def is_admin(self) -> bool:
        return self.role in ADMIN_ROLES

    def can(self, permission: str) -> bool:
        return can(self.role, permission)'''),
    ("class MemberPublic(BaseModel):", '''class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., max_length=200)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., max_length=200)
    new_password: str = Field(..., max_length=256)


class EmailTokenRequest(BaseModel):
    token: str = Field(..., max_length=200)


class ResendVerificationRequest(BaseModel):
    email: EmailStr


class InvitationRequest(BaseModel):
    email: EmailStr
    role: str = Field("recruiter", description="owner, admin, recruiter or viewer; what you may assign depends on your role")


class AcceptInvitationRequest(BaseModel):
    token: str = Field(..., max_length=200)
    name: Optional[str] = Field(default=None, max_length=100, description="Needed when the invited email has no account yet")
    password: Optional[str] = Field(default=None, max_length=256, description="Needed when the invited email has no account yet")


class InvitationPublic(BaseModel):
    id: str
    email: str
    role: str
    invited_by: Optional[str] = None
    created_at: datetime
    expires_at: datetime


class InvitationPreview(BaseModel):
    organization: str
    email: str
    role: str
    account_exists: bool


class ChangeRoleRequest(BaseModel):
    role: str


class SwitchOrganizationRequest(BaseModel):
    organization_id: str = Field(..., max_length=64)


class SessionPublic(BaseModel):
    id: str
    created_at: datetime
    last_used_at: datetime
    ip: Optional[str] = None
    user_agent: Optional[str] = None
    current: bool = False


class AuditEventPublic(BaseModel):
    id: str
    action: str
    user_id: Optional[str] = None
    details: dict = Field(default_factory=dict)
    ip: Optional[str] = None
    request_id: Optional[str] = None
    created_at: datetime


class AuditLogPage(BaseModel):
    events: list
    total: int


class MemberPublic(BaseModel):'''),
    ("    email: str\n    name: str\n    created_at: datetime\n\n\nclass OrganizationPublic", "    email: str\n    name: str\n    created_at: datetime\n    email_verified: bool = True\n\n\nclass OrganizationPublic"),
])
print("ok")
