"""Helpers for tests that use accounts."""
from datetime import timedelta

import database as database_module
import security
from models import ResumeAnalysisResponse, utc_now
from tests.conftest import JOB_DESCRIPTION, make_pdf

PASSWORD = "correct horse battery"
PDF = make_pdf()  # one fixed file; each make_pdf() call embeds a new timestamp


def db_call(client, function, *args, **kwargs):
    """Run a database coroutine in the app's own event loop"""
    return client.portal.call(lambda: function(*args, **kwargs))


def collection(name):
    return database_module.database.db[name]


def signup(client, email="owner@example.com", name="Olive Owner", org="Acme Hiring", password=PASSWORD):
    """Register through the API; returns (auth headers, response body)"""
    response = client.post("/api/v1/auth/register", json={
        "email": email, "password": password, "name": name, "organization_name": org,
    })
    assert response.status_code == 201, response.text
    body = response.json()
    return {"Authorization": f"Bearer {body['access_token']}"}, body


def token_headers(user_id, org_id):
    """A valid token for a user acting in an organisation (users sign in to their first one)"""
    user = None
    return {"Authorization": f"Bearer {security.create_access_token(user_id, org_id, 0)}"}


def add_member(client, org_id, email, role="member", name="Mia Member"):
    """Register another user (in their own organisation) and also make them a member of org_id.
    Returns headers that act inside org_id."""
    _, body = signup(client, email=email, name=name, org=f"{name}'s own org")
    user_id = body["user"]["id"]
    db_call(client, database_module.database.create_membership,
            {"org_id": org_id, "user_id": user_id, "role": role, "created_at": utc_now()})
    return token_headers(user_id, org_id), user_id


def scan(client, headers=None, content=None):
    return client.post(
        "/api/v1/scan_resume",
        files={"resume_file": ("cv.pdf", PDF if content is None else content, "application/pdf")},
        data={"job_description": JOB_DESCRIPTION},
        headers=headers or {},
    )


def insert_scan(client, org_id, age_days=0, created_by=None, scan_id=None):
    """Put a scan straight into the database, optionally made `age_days` ago"""
    record = ResumeAnalysisResponse(
        filename="cv.pdf",
        extracted_data={"skills": ["python"], "education": [], "experience": []},
        match_score=70, job_description=JOB_DESCRIPTION, analysis_summary="s",
        org_id=org_id, created_by=created_by, created_at=utc_now() - timedelta(days=age_days),
        **({"id": scan_id} if scan_id else {}),
    )
    db_call(client, database_module.database.save_scan_result, record)
    return record.id


def require_auth(monkeypatch):
    monkeypatch.setenv("AUTH_REQUIRED", "true")
