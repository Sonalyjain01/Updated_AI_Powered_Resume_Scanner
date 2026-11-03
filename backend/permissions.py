"""Who may do what.

Roles, from most to least access:

  owner      everything, including erasing the organisation's data and promoting admins
  admin      runs the team: invites and removes recruiters and viewers, exports data, reads the audit log
  recruiter  runs scans, sees every scan in the organisation, deletes their own scans
  viewer     reads scans and results; cannot upload or delete anything

Every endpoint asks for a permission, never for a role name, so changing what a role can do is a
change to the table below and nowhere else.
"""
from typing import Dict, FrozenSet, Tuple

ROLES: Tuple[str, ...] = ("owner", "admin", "recruiter", "viewer")

SCANS_CREATE = "scans:create"
SCANS_READ = "scans:read"
SCANS_DELETE_OWN = "scans:delete_own"
SCANS_DELETE_ANY = "scans:delete_any"
ORG_VIEW = "org:view"
MEMBERS_READ = "org:members_read"
MEMBERS_MANAGE = "org:members_manage"
INVITE = "org:invite"
EXPORT = "org:export"
AUDIT_READ = "org:audit_read"
ERASE_DATA = "org:erase_data"

ALL: FrozenSet[str] = frozenset({
    SCANS_CREATE, SCANS_READ, SCANS_DELETE_OWN, SCANS_DELETE_ANY,
    ORG_VIEW, MEMBERS_READ, MEMBERS_MANAGE, INVITE, EXPORT, AUDIT_READ, ERASE_DATA,
})

PERMISSIONS: Dict[str, FrozenSet[str]] = {
    "owner": ALL,
    "admin": ALL - {ERASE_DATA},
    "recruiter": frozenset({SCANS_CREATE, SCANS_READ, SCANS_DELETE_OWN, ORG_VIEW}),
    "viewer": frozenset({SCANS_READ, ORG_VIEW}),
}


def can(role: str, permission: str) -> bool:
    return permission in PERMISSIONS.get(role, frozenset())


def assignable_roles(actor_role: str) -> Tuple[str, ...]:
    """Roles the actor may give to other people. Only an owner can create owners and admins."""
    if actor_role == "owner":
        return ROLES
    if actor_role == "admin":
        return ("recruiter", "viewer")
    return ()


def can_manage_member(actor_role: str, target_role: str) -> bool:
    """Whether the actor may change or remove a member who currently has `target_role`.
    Admins manage recruiters and viewers; only owners manage admins and other owners."""
    return can(actor_role, MEMBERS_MANAGE) and target_role in assignable_roles(actor_role)
