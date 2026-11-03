import json
from datetime import timedelta

import pytest

import database as database_module
from models import utc_now
from tests.helpers import (
    PASSWORD, add_member, collection, db_call, insert_scan, scan, signup,
)

ORG = "/api/v1/orgs/current"


def run_worker(client):
    return client.portal.call(client.app.state.job_runner.run_next)


def count(client, name, query=None):
    return db_call(client, collection(name).count_documents, query or {})


def stored_files(storage):
    return list(storage.root.rglob("cv.pdf"))


def queue_job(client, headers):
    return client.post("/api/v1/scans", headers=headers, files={"resume_file": ("cv.pdf", __import__("tests.helpers", fromlist=["PDF"]).PDF, "application/pdf")},
                       data={"job_description": "We need a python engineer with strong backend and API design experience."}).json()


class TestDeleteScan:
    def test_removes_the_scan_its_file_and_its_job(self, client, storage):
        headers, _ = signup(client)
        job = queue_job(client, headers)
        run_worker(client)
        scan_id = client.get(job["status_url"], headers=headers).json()["scan_id"]
        assert stored_files(storage) and count(client, "scan_jobs") == 1

        assert client.delete(f"/api/v1/scan/{scan_id}", headers=headers).status_code == 200
        assert client.get(f"/api/v1/scan/{scan_id}", headers=headers).status_code == 404
        assert not stored_files(storage) and count(client, "scan_files") == 0 and count(client, "scan_jobs") == 0

    def test_leaves_a_tombstone_and_an_audit_event_without_personal_data(self, client):
        headers, body = signup(client)
        scan_id = scan(client, headers).json()["id"]
        client.delete(f"/api/v1/scan/{scan_id}", headers=headers)
        tombstone = db_call(client, collection("erasure_tombstones").find_one, {"id": scan_id})
        assert tombstone["kind"] == "scan" and tombstone["org_id"] == body["organization"]["id"]
        event = db_call(client, collection("audit_events").find_one, {"action": "scan_deleted"})
        assert event["details"] == {"scan_id": scan_id} and event["user_id"] == body["user"]["id"]
        assert "owner@example.com" not in json.dumps(event, default=str)

    def test_a_file_that_cannot_be_deleted_is_retried_later(self, client, storage, monkeypatch):
        from storage import StorageError
        headers, _ = signup(client)
        scan_id = scan(client, headers).json()["id"]

        async def fail(key):
            raise StorageError("unreachable")
        real_delete = storage.delete
        monkeypatch.setattr(storage, "delete", fail)
        assert client.delete(f"/api/v1/scan/{scan_id}", headers=headers).status_code == 200
        assert count(client, "scan_files") == 1  # record kept, due for the next sweep
        monkeypatch.setattr(storage, "delete", real_delete)
        client.portal.call(__import__("services.retention", fromlist=["x"]).purge_expired, storage)
        assert count(client, "scan_files") == 0 and not stored_files(storage)


class TestEraseOrganisationData:
    def erase(self, client, headers, name="Acme Hiring"):
        return client.post(f"{ORG}/erase-data", headers=headers, json={"organization_name": name})

    def test_deletes_everything_but_keeps_the_accounts(self, client, storage):
        headers, body = signup(client)
        scan(client, headers)
        scan(client, headers)
        queue_job(client, headers)
        result = self.erase(client, headers)
        assert result.status_code == 200
        assert result.json()["scans"] == 2 and result.json()["files"] == 2 and result.json()["usage_records"] == 2
        assert count(client, "resume_scans") == 0 and count(client, "scan_files") == 0
        assert count(client, "usage_records") == 0 and count(client, "scan_jobs") == 0
        assert not stored_files(storage)
        assert client.get("/api/v1/auth/me", headers=headers).status_code == 200  # still signed in

    def test_other_organisations_are_untouched(self, client, storage):
        a, _ = signup(client, email="a@example.com", org="Org A")
        b, _ = signup(client, email="b@example.com", org="Org B")
        scan(client, a)
        scan(client, b)
        assert self.erase(client, a, "Org A").status_code == 200
        assert client.get("/api/v1/scan_history", headers=b).json()["total_count"] == 1
        assert len(stored_files(storage)) == 1

    def test_the_organisation_name_must_be_typed_exactly(self, client):
        headers, _ = signup(client)
        scan(client, headers)
        assert self.erase(client, headers, "acme").status_code == 400
        assert client.get("/api/v1/scan_history", headers=headers).json()["total_count"] == 1

    def test_only_the_owner_can_erase(self, client):
        owner, body = signup(client)
        admin, _ = add_member(client, body["organization"]["id"], "admin@example.com", "admin")
        member, _ = add_member(client, body["organization"]["id"], "member@example.com", "member")
        scan(client, owner)
        assert self.erase(client, admin).status_code == 403
        assert self.erase(client, member).status_code == 403
        assert self.erase(client, owner).status_code == 200

    def test_records_a_tombstone(self, client):
        headers, body = signup(client)
        self.erase(client, headers)
        tombstone = db_call(client, collection("erasure_tombstones").find_one, {"kind": "org_data"})
        assert tombstone["id"] == body["organization"]["id"]


class TestExport:
    def test_organisation_export_contains_its_scans_for_admins_only(self, client):
        owner, body = signup(client)
        member, _ = add_member(client, body["organization"]["id"], "member@example.com", "member")
        scan(client, owner)
        exported = client.get(f"{ORG}/export", headers=owner).json()
        assert len(exported["scans"]) == 1 and exported["organization"]["name"] == "Acme Hiring"
        assert exported["usage_this_month"]["scans"] == 1
        assert client.get(f"{ORG}/export", headers=member).status_code == 403

    def test_export_does_not_include_other_organisations(self, client):
        a, _ = signup(client, email="a@example.com", org="Org A")
        b, _ = signup(client, email="b@example.com", org="Org B")
        scan(client, b)
        assert client.get(f"{ORG}/export", headers=a).json()["scans"] == []

    def test_personal_export_has_your_profile_and_only_your_scans(self, client):
        owner, body = signup(client)
        member, _ = add_member(client, body["organization"]["id"], "member@example.com", "member")
        scan(client, owner)
        scan(client, member)
        mine = client.get("/api/v1/auth/me/export", headers=owner).json()
        assert mine["user"]["email"] == "owner@example.com" and len(mine["scans_you_ran"]) == 1
        assert "password_hash" not in json.dumps(mine)
        assert mine["memberships"][0]["role"] == "owner"

    def test_exports_are_audited(self, client):
        headers, _ = signup(client)
        client.get(f"{ORG}/export", headers=headers)
        client.get("/api/v1/auth/me/export", headers=headers)
        actions = {e["action"] for e in db_call(client, collection("audit_events").find({}).to_list, 100)}
        assert {"organization_data_exported", "user_data_exported"} <= actions


class TestDeleteAccount:
    def delete(self, client, headers, password=PASSWORD):
        return client.post("/api/v1/auth/delete-account", headers=headers, json={"password": password})

    def test_a_sole_member_takes_the_organisation_and_all_its_data_with_them(self, client, storage):
        headers, body = signup(client)
        scan(client, headers)
        assert self.delete(client, headers).json() == {"organizations_deleted": 1}
        for name in ("users", "organizations", "memberships", "resume_scans", "scan_files", "usage_records"):
            assert count(client, name) == 0, name
        assert not stored_files(storage)
        assert client.get("/api/v1/auth/me", headers=headers).status_code == 401
        assert client.post("/api/v1/auth/login", json={"email": "owner@example.com", "password": PASSWORD}).status_code == 401

    def test_needs_the_password(self, client):
        headers, _ = signup(client)
        assert self.delete(client, headers, "wrong password!").status_code == 400
        assert client.get("/api/v1/auth/me", headers=headers).status_code == 200

    def test_the_only_owner_of_a_shared_organisation_cannot_leave(self, client):
        owner, body = signup(client)
        add_member(client, body["organization"]["id"], "member@example.com", "member")
        response = self.delete(client, owner)
        assert response.status_code == 409 and "only owner" in response.json()["detail"]
        assert client.get("/api/v1/auth/me", headers=owner).status_code == 200

    def test_a_member_leaving_does_not_delete_the_organisation(self, client):
        owner, body = signup(client)
        scan(client, owner)
        member, member_id = add_member(client, body["organization"]["id"], "member@example.com", "member")
        member_own_org_scans = scan(client, member)  # runs in the shared organisation
        assert member_own_org_scans.status_code == 200
        from tests.helpers import token_headers
        from services import account_service
        result = client.post("/api/v1/auth/delete-account", headers=member, json={"password": PASSWORD})
        assert result.status_code == 200
        assert client.get("/api/v1/scan_history", headers=owner).json()["total_count"] == 2  # their scan stays with the organisation
        assert db_call(client, database_module.database.get_user, member_id) is None

    def test_a_second_owner_lets_the_first_leave(self, client):
        owner, body = signup(client)
        add_member(client, body["organization"]["id"], "co@example.com", "owner")
        assert self.delete(client, owner).status_code == 200

    def test_deletion_is_recorded_without_the_email(self, client):
        headers, body = signup(client)
        self.delete(client, headers)
        event = db_call(client, collection("audit_events").find_one, {"action": "account_deleted"})
        assert event["user_id"] == body["user"]["id"] and "owner@example.com" not in json.dumps(event, default=str)
        kinds = {t["kind"] for t in db_call(client, collection("erasure_tombstones").find({}).to_list, 100)}
        assert {"user", "org", "org_data"} <= kinds

    def test_needs_a_real_account(self, client):
        assert client.post("/api/v1/auth/delete-account", json={"password": PASSWORD}).status_code == 401


class TestRetention:
    def purge(self, client, storage):
        from services.retention import purge_expired_scans
        return client.portal.call(purge_expired_scans, storage)

    def test_scans_past_their_plan_retention_are_deleted_with_their_files(self, client, storage):
        headers, body = signup(client)
        org_id = body["organization"]["id"]
        old = scan(client, headers).json()["id"]
        db_call(client, collection("resume_scans").update_one, {"id": old}, {"$set": {"created_at": utc_now() - timedelta(days=45)}})
        fresh = scan(client, headers).json()["id"]  # free plan keeps scans for 30 days
        assert self.purge(client, storage) == 1
        assert client.get(f"/api/v1/scan/{old}", headers=headers).status_code == 404
        assert client.get(f"/api/v1/scan/{fresh}", headers=headers).status_code == 200
        assert len(stored_files(storage)) == 1 and count(client, "scan_files") == 1

    def test_a_plan_with_no_retention_keeps_everything(self, client, storage):
        headers, body = signup(client)
        db_call(client, collection("plans").update_one, {"id": "free"}, {"$set": {"retention_days": 0}})
        insert_scan(client, body["organization"]["id"], age_days=1000)
        assert self.purge(client, storage) == 0 and count(client, "resume_scans") == 1

    def test_each_organisation_follows_its_own_plan(self, client, storage):
        a, body_a = signup(client, email="a@example.com", org="Org A")
        b, body_b = signup(client, email="b@example.com", org="Org B")
        db_call(client, database_module.database.set_organization_plan, body_b["organization"]["id"], "business")
        insert_scan(client, body_a["organization"]["id"], age_days=60)   # free keeps 30 days: expired
        insert_scan(client, body_b["organization"]["id"], age_days=60)   # business keeps 365: kept
        assert self.purge(client, storage) == 1
        assert client.get("/api/v1/scan_history", headers=a).json()["total_count"] == 0
        assert client.get("/api/v1/scan_history", headers=b).json()["total_count"] == 1

    def test_the_default_organisation_follows_scan_retention_days(self, client, storage, monkeypatch):
        insert_scan(client, "default", age_days=10)
        assert self.purge(client, storage) == 0  # off by default
        monkeypatch.setenv("SCAN_RETENTION_DAYS", "5")
        assert self.purge(client, storage) == 1

    def test_housekeeping_runs_retention_and_prunes_old_records(self, client):
        headers, body = signup(client)
        insert_scan(client, body["organization"]["id"], age_days=90)
        old = utc_now() - timedelta(days=400)
        db_call(client, collection("audit_events").insert_one, {"id": "old", "action": "x", "created_at": old})
        db_call(client, collection("erasure_tombstones").insert_one, {"kind": "scan", "id": "t", "erased_at": utc_now() - timedelta(days=100)})
        client.portal.call(client.app.state.job_runner.housekeeping)
        assert count(client, "resume_scans") == 0
        assert count(client, "audit_events", {"id": "old"}) == 0
        assert count(client, "erasure_tombstones", {"id": "t"}) == 0

    def test_recent_tombstones_are_kept(self, client):
        db_call(client, collection("erasure_tombstones").insert_one, {"kind": "scan", "id": "t", "erased_at": utc_now() - timedelta(days=10)})
        client.portal.call(client.app.state.job_runner.housekeeping)
        assert count(client, "erasure_tombstones", {"id": "t"}) == 1


class TestMigrationOwnership:
    def test_scans_stored_before_accounts_belong_to_the_default_organisation(self, client):
        from migrations import _006_accounts_plans_and_ownership
        db_call(client, collection("resume_scans").insert_one, {"id": "legacy", "filename": "old.pdf"})
        db_call(client, collection("scan_files").insert_one, {"scan_id": "legacy", "key": "k"})
        client.portal.call(_006_accounts_plans_and_ownership, database_module.database.db)
        assert db_call(client, collection("resume_scans").find_one, {"id": "legacy"})["org_id"] == "default"
        assert db_call(client, collection("scan_files").find_one, {"scan_id": "legacy"})["org_id"] == "default"

    def test_rerunning_does_not_duplicate_or_reset_plans(self, client):
        from migrations import _006_accounts_plans_and_ownership
        db_call(client, collection("plans").update_one, {"id": "free"}, {"$set": {"scans_per_month": 7}})
        client.portal.call(_006_accounts_plans_and_ownership, database_module.database.db)
        assert count(client, "plans") == 3
        assert db_call(client, collection("plans").find_one, {"id": "free"})["scans_per_month"] == 7
