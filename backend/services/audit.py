"""A short record of who did what to personal data.

Events hold ids and counts only, never names, emails or resume content, so the trail can be kept
longer than the data it describes (AUDIT_RETENTION_DAYS, default 365).
"""
import logging
import uuid

from database import DatabaseError, database
from models import utc_now
from request_context import get_request_id

logger = logging.getLogger(__name__)


async def record(action: str, org_id: str = None, user_id: str = None, **details) -> None:
    """Never raises: failing to write the trail must not block the action it describes"""
    try:
        await database.add_audit_event({
            "id": uuid.uuid4().hex,
            "action": action,
            "org_id": org_id,
            "user_id": user_id,
            "details": details,
            "request_id": get_request_id(),
            "created_at": utc_now(),
        })
    except DatabaseError:
        logger.error(f"Audit event '{action}' could not be recorded")
