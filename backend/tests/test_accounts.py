from datetime import timedelta

import pytest

import database as database_module
import security
from models import utc_now
from tests.helpers import (
    PASSWORD, PDF, add_member, collection, db_call, insert_scan, require_auth, scan, signup, token_headers,
)

HISTORY = "/api/v1/scan_history"


class TestSecurity:
    def test_password_rules(self):
        assert security.validate_password_strength("short") is not None
        assert security.validate_password_strength("a" * 200) is not None
        assert security.validate_password_strength("aaaaaaaaaaaa") is not None  # too repetitive
        assert security.validate_password_strength("me@example.com", "me@example.com") is not None
        assert security.validate_password_strength(PASSWORD) is None

    def test_hash_and_verify(self):
        hashed = security.hash_password(PASSWORD)
        assert hashed != PASSWORD and hashed.startswith("$argon2")
        assert security.verify_password(PASSWORD, hashed) is True
        assert security.verify_password("wrong password!", hashed) is False

    def test_unknown_account_is_checked_the_same_way(self):
        assert security.verify_password(PASSWORD, None) is False

    def test_token_round_trip(self):
        claims = security.decode_access_token(security.create_access_token("u1", "o1", 3))
        assert (claims["sub"], claims["org"], claims["tv"]) == ("u1", "o1", 3)

    def test_expired_token_is_refused(self, monkeypatch):
        monkeypatch.setenv("JWT_EXPIRE_MINUTES", "-1")
        with pytest.raises(security.AuthError, match="expired"):
            security.decode_access_token(security.create_access_token("u1", "o1", 0))

    def test_token_signed_with_another_secret_is_refused(self, monkeypatch):
        token = security.create_access_token("u1", "o1", 0)
        monkeypatch.setenv("JWT_SECRET", "a-completely-different-secret-" + "y" * 20)
        with pytest.raises(security.AuthError):
            security.decode_access_token(token)

    def test_short_secret_cannot_sign(self, monkeypatch):
        monkeypatch.setenv("JWT_SECRET", "too-short")
        with pytest.raises(security.AuthNotConfigured):
            security.create_access_token("u1", "o1", 0)


class TestRegistration:
    def test_creates_the_user_organisation_and_owner_membership(self, client):
        headers, body = signup(client)
        assert body["role"] == "owner" and body["organization"]["name"] == "Acme Hiring"
        assert body["organization"]["plan"]["id"] == "free" and body["organization"]["member_count"] == 1
        assert "password" not in str(body).lower().replace("password_hash", "")
        membership = db_call(client, database_module.database.get_membership, body["organization"]["id"], body["user"]["id"])
        assert membership["role"] == "owner"

    def test_password_is_stored_hashed(self, client):
        _, body = signup(client)
        stored = db_call(client, database_module.database.get_user, body["user"]["id"])
        assert stored["password_hash"].startswith("$argon2") and PASSWORD not in str(stored)

    def test_organisation_gets_a_default_name(self, client):
        response = client.post("/api/v1/auth/register", json={"email": "x@example.com", "password": PASSWORD, "name": "Xia"})
        assert response.json()["organization"]["name"] == "Xia's organisation"

    def test_same_email_cannot_register_twice_in_any_case(self, client):
        signup(client, email="dup@example.com")
        again = client.post("/api/v1/auth/register", json={"email": "DUP@Example.com", "password": PASSWORD, "name": "Dup"})
        assert again.status_code == 409 and "already exists" in again.json()["detail"]

    def test_email_is_stored_lowercase(self, client):
        _, body = signup(client, email="MiXeD@Example.com")
        assert body["user"]["email"] == "mixed@example.com"

    @pytest.mark.parametrize("password", ["short", "aaaaaaaaaaaa"])
    def test_weak_passwords_are_refused(self, client, password):
        response = client.post("/api/v1/auth/register", json={"email": "w@example.com", "password": password, "name": "W"})
        assert response.status_code == 400

    def test_invalid_email_is_refused(self, client):
        assert client.post("/api/v1/auth/register", json={"email": "nope", "password": PASSWORD, "name": "W"}).status_code == 422

    def test_registration_can_be_closed(self, client, monkeypatch):
        monkeypatch.setenv("REGISTRATION_ENABLED", "false")
        response = client.post("/api/v1/auth/register", json={"email": "c@example.com", "password": PASSWORD, "name": "C"})
        assert response.status_code == 403


class TestLogin:
    def login(self, client, email="owner@example.com", password=PASSWORD):
        return client.post("/api/v1/auth/login", json={"email": email, "password": password})

    def test_correct_password_signs_in(self, client):
        signup(client)
        response = self.login(client)
        assert response.status_code == 200 and response.json()["access_token"] and response.json()["role"] == "owner"

    def test_email_case_does_not_matter(self, client):
        signup(client)
        assert self.login(client, email="OWNER@example.com").status_code == 200

    def test_wrong_password_and_unknown_email_look_identical(self, client):
        signup(client)
        wrong = self.login(client, password="not the password")
        unknown = self.login(client, email="nobody@example.com")
        assert wrong.status_code == unknown.status_code == 401
        assert wrong.json() == unknown.json() and wrong.headers["WWW-Authenticate"] == "Bearer"

    def test_account_locks_after_repeated_failures(self, client):
        signup(client)
        for _ in range(5):
            assert self.login(client, password="wrong password!").status_code == 401
        locked = self.login(client)  # even the right password is refused now
        assert locked.status_code == 429 and "Try again in" in locked.json()["detail"]

    def test_lock_expires(self, client):
        _, body = signup(client)
        for _ in range(5):
            self.login(client, password="wrong password!")
        db_call(client, database_module.database.update_user, body["user"]["id"], {"locked_until": utc_now() - timedelta(minutes=1)})
        assert self.login(client).status_code == 200

    def test_success_resets_the_failure_count(self, client):
        signup(client)
        for _ in range(4):
            self.login(client, password="wrong password!")
        assert self.login(client).status_code == 200
        for _ in range(4):
            assert self.login(client, password="wrong password!").status_code == 401  # not locked yet
        assert self.login(client).status_code == 200


class TestTokens:
    def test_me_describes_the_signed_in_user(self, client, monkeypatch):
        require_auth(monkeypatch)
        headers, body = signup(client)
        me = client.get("/api/v1/auth/me", headers=headers).json()
        assert me["user"]["email"] == "owner@example.com" and me["organization"]["id"] == body["organization"]["id"]
        assert me["role"] == "owner" and me["auth_required"] is True

    def test_requests_without_a_token_are_refused_when_auth_is_required(self, client, monkeypatch):
        require_auth(monkeypatch)
        response = client.get(HISTORY)
        assert response.status_code == 401 and response.headers["WWW-Authenticate"] == "Bearer"

    @pytest.mark.parametrize("value", ["Bearer", "Bearer garbage", "Basic abc", "garbage"])
    def test_bad_authorization_headers_are_refused(self, client, value):
        assert client.get(HISTORY, headers={"Authorization": value}).status_code == 401

    def test_without_required_auth_unsigned_requests_use_the_default_organisation(self, client):
        assert client.get(HISTORY).status_code == 200
        me = client.get("/api/v1/auth/me").json()
        assert me["user"] is None and me["role"] == "owner" and me["auth_required"] is False

    def test_a_valid_token_is_used_even_when_auth_is_not_required(self, client):
        headers, body = signup(client)
        scan(client, headers)
        assert client.get(HISTORY, headers=headers).json()["total_count"] == 1
        assert client.get(HISTORY).json()["total_count"] == 0  # the shared default organisation is separate

    def test_logout_everywhere_revokes_existing_tokens(self, client):
        headers, _ = signup(client)
        assert client.post("/api/v1/auth/logout-all", headers=headers).status_code == 204
        assert client.get("/api/v1/auth/me", headers=headers).status_code == 401
        assert client.post("/api/v1/auth/login", json={"email": "owner@example.com", "password": PASSWORD}).status_code == 200

    def test_changing_the_password_signs_out_other_sessions(self, client):
        old_headers, _ = signup(client)
        response = client.post("/api/v1/auth/change-password", headers=old_headers,
                               json={"current_password": PASSWORD, "new_password": "a brand new passphrase"})
        assert response.status_code == 200
        new_headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
        assert client.get("/api/v1/auth/me", headers=old_headers).status_code == 401
        assert client.get("/api/v1/auth/me", headers=new_headers).status_code == 200
        assert client.post("/api/v1/auth/login", json={"email": "owner@example.com", "password": PASSWORD}).status_code == 401
        assert client.post("/api/v1/auth/login", json={"email": "owner@example.com", "password": "a brand new passphrase"}).status_code == 200

    def test_changing_the_password_needs_the_current_one(self, client):
        headers, _ = signup(client)
        response = client.post("/api/v1/auth/change-password", headers=headers,
                               json={"current_password": "wrong password!", "new_password": "a brand new passphrase"})
        assert response.status_code == 400

    def test_token_of_a_deleted_user_stops_working(self, client):
        headers, body = signup(client)
        db_call(client, database_module.database.delete_user, body["user"]["id"])
        assert client.get("/api/v1/auth/me", headers=headers).status_code == 401

    def test_token_for_an_organisation_the_user_left_stops_working(self, client):
        _, body = signup(client)
        headers = token_headers(body["user"]["id"], "some-other-org")
        assert client.get("/api/v1/auth/me", headers=headers).status_code == 401

    def test_missing_secret_is_reported_clearly(self, client, monkeypatch):
        monkeypatch.setenv("JWT_SECRET", "")
        response = client.post("/api/v1/auth/register", json={"email": "s@example.com", "password": PASSWORD, "name": "S"})
        assert response.status_code == 503


class TestStartupChecks:
    def test_required_auth_needs_a_real_secret(self, monkeypatch):
        import config
        monkeypatch.setenv("AUTH_REQUIRED", "true")
        monkeypatch.setenv("JWT_SECRET", "short")
        with pytest.raises(config.ConfigError, match="JWT_SECRET"):
            config.validate_settings()

    def test_open_mode_is_warned_about(self, monkeypatch, caplog):
        import config
        monkeypatch.setenv("AUTH_REQUIRED", "false")
        with caplog.at_level("WARNING"):
            config.validate_settings()
        assert "AUTH_REQUIRED" in caplog.text


class TestIsolation:
    def two_orgs(self, client):
        a, body_a = signup(client, email="a@example.com", org="Org A")
        b, body_b = signup(client, email="b@example.com", org="Org B")
        return a, body_a, b, body_b

    def test_scans_belong_to_the_organisation_and_user_that_ran_them(self, client):
        a, body_a, _, _ = self.two_orgs(client)
        result = scan(client, a).json()
        assert result["org_id"] == body_a["organization"]["id"] and result["created_by"] == body_a["user"]["id"]

    def test_history_shows_only_your_own_organisation(self, client):
        a, _, b, _ = self.two_orgs(client)
        scan(client, a)
        scan(client, a)
        scan(client, b)
        assert client.get(HISTORY, headers=a).json()["total_count"] == 2
        assert client.get(HISTORY, headers=b).json()["total_count"] == 1

    def test_another_organisations_scan_cannot_be_read_or_deleted(self, client):
        a, _, b, _ = self.two_orgs(client)
        scan_id = scan(client, a).json()["id"]
        assert client.get(f"/api/v1/scan/{scan_id}", headers=b).status_code == 404
        assert client.delete(f"/api/v1/scan/{scan_id}", headers=b).status_code == 404
        assert client.get(f"/api/v1/scan/{scan_id}", headers=a).status_code == 200  # still there

    def test_jobs_are_private_to_the_organisation(self, client):
        a, _, b, _ = self.two_orgs(client)
        job = client.post("/api/v1/scans", headers=a, files={"resume_file": ("cv.pdf", PDF, "application/pdf")},
                          data={"job_description": "We need a python engineer with strong backend and API design experience."}).json()
        assert client.get(job["status_url"], headers=a).status_code == 200
        assert client.get(job["status_url"], headers=b).status_code == 404

    def test_background_scan_is_owned_by_the_user_who_queued_it(self, client):
        a, body_a, _, _ = self.two_orgs(client)
        job = client.post("/api/v1/scans", headers=a, files={"resume_file": ("cv.pdf", PDF, "application/pdf")},
                          data={"job_description": "We need a python engineer with strong backend and API design experience."}).json()
        client.portal.call(client.app.state.job_runner.run_next)
        result = client.get(job["status_url"], headers=a).json()["result"]
        assert result["org_id"] == body_a["organization"]["id"] and result["created_by"] == body_a["user"]["id"]

    def test_usage_is_counted_per_organisation(self, client):
        a, _, b, _ = self.two_orgs(client)
        scan(client, a)
        scan(client, a)
        assert client.get("/api/v1/usage", headers=a).json()["scans"] == 2
        assert client.get("/api/v1/usage", headers=b).json()["scans"] == 0


class TestPlansAndQuota:
    def test_plans_are_listed(self, client):
        plans = {p["id"]: p for p in client.get("/api/v1/plans").json()}
        assert set(plans) == {"free", "pro", "business"}
        assert plans["free"]["scans_per_month"] < plans["pro"]["scans_per_month"] < plans["business"]["scans_per_month"]

    def test_new_organisations_start_on_the_free_plan(self, client):
        headers, _ = signup(client)
        org = client.get("/api/v1/orgs/current", headers=headers).json()
        assert org["plan"]["id"] == "free" and org["member_count"] == 1

    def test_the_plan_limit_applies_to_that_organisation_only(self, client):
        a, body_a = signup(client, email="p1@example.com", org="P1")
        b, _ = signup(client, email="p2@example.com", org="P2")
        db_call(client, collection("plans").update_one, {"id": "free"}, {"$set": {"scans_per_month": 1}})
        assert scan(client, a).status_code == 200
        blocked = scan(client, a)
        assert blocked.status_code == 429 and "Monthly scan limit reached (1 scans)" in blocked.json()["detail"]
        assert scan(client, b).status_code == 200  # a different organisation has its own allowance

    def test_moving_to_a_bigger_plan_lifts_the_limit(self, client):
        headers, body = signup(client)
        db_call(client, collection("plans").update_one, {"id": "free"}, {"$set": {"scans_per_month": 1}})
        scan(client, headers)
        assert scan(client, headers).status_code == 429
        db_call(client, database_module.database.set_organization_plan, body["organization"]["id"], "pro")
        assert scan(client, headers).status_code == 200

    def test_usage_report_shows_the_plan_limits(self, client):
        headers, _ = signup(client)
        scan(client, headers)
        report = client.get("/api/v1/usage", headers=headers).json()
        free = {p["id"]: p for p in client.get("/api/v1/plans").json()}["free"]
        assert report["limits"]["scans"] == free["scans_per_month"] and report["remaining"]["scans"] == free["scans_per_month"] - 1

    def test_default_organisation_still_uses_the_environment_limits(self, client, monkeypatch):
        monkeypatch.setenv("QUOTA_SCANS_PER_MONTH", "1")
        assert scan(client).status_code == 200
        assert scan(client).status_code == 429


class TestRoles:
    def setup_org(self, client):
        owner, body = signup(client)
        org_id = body["organization"]["id"]
        member, member_id = add_member(client, org_id, "member@example.com", "member")
        admin, admin_id = add_member(client, org_id, "admin@example.com", "admin", name="Ada Admin")
        return owner, member, admin, org_id, member_id

    def test_only_admins_can_list_members(self, client):
        owner, member, admin, _, _ = self.setup_org(client)
        assert client.get("/api/v1/orgs/current/members", headers=member).status_code == 403
        listed = client.get("/api/v1/orgs/current/members", headers=admin).json()
        assert sorted(m["role"] for m in listed) == ["admin", "member", "owner"]

    def test_everyone_in_the_organisation_sees_its_scans(self, client):
        owner, member, _, _, _ = self.setup_org(client)
        scan(client, owner)
        assert client.get(HISTORY, headers=member).json()["total_count"] == 1

    def test_a_member_can_delete_their_own_scan_but_not_someone_elses(self, client):
        owner, member, _, _, _ = self.setup_org(client)
        theirs = scan(client, owner).json()["id"]
        mine = scan(client, member).json()["id"]
        assert client.delete(f"/api/v1/scan/{theirs}", headers=member).status_code == 403
        assert client.delete(f"/api/v1/scan/{mine}", headers=member).status_code == 200

    def test_an_admin_can_delete_any_scan(self, client):
        owner, _, admin, _, _ = self.setup_org(client)
        scan_id = scan(client, owner).json()["id"]
        assert client.delete(f"/api/v1/scan/{scan_id}", headers=admin).status_code == 200
