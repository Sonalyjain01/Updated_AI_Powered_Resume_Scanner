import time
from datetime import timedelta

import pytest

import database as database_module
from models import utc_now
from tests.conftest import JOB_DESCRIPTION, make_encrypted_pdf, make_pdf


# One fixed file: every make_pdf() call embeds a new timestamp, so two calls are never byte-identical
PDF = make_pdf()


def create(client, content=None, key=None, job_description=JOB_DESCRIPTION, criteria=None, filename="cv.pdf"):
    headers = {"Idempotency-Key": key} if key is not None else {}
    data = {"job_description": job_description}
    if criteria is not None:
        data["criteria"] = criteria
    return client.post(
        "/api/v1/scans",
        files={"resume_file": (filename, PDF if content is None else content, "application/pdf")},
        data=data,
        headers=headers,
    )


def run_one(client):
    """Run the next queued job in the test's own event loop, like a worker would"""
    return client.portal.call(client.app.state.job_runner.run_next)


def collection(name):
    return getattr(database_module.database.db, name)


class TestEnqueue:
    def test_returns_202_with_a_job_to_poll(self, client, fake_provider):
        response = create(client)
        body = response.json()
        assert response.status_code == 202 and body["status"] == "queued"
        assert body["status_url"] == f"/api/v1/jobs/{body['job_id']}"
        assert response.headers["Location"] == body["status_url"]
        assert fake_provider.calls == []  # nothing slow happened in the request

    def test_no_scan_exists_until_a_worker_runs(self, client):
        create(client)
        assert client.get("/api/v1/scan_history").json()["total_count"] == 0

    def test_queued_job_shows_its_position(self, client):
        first, second = create(client).json()["job_id"], create(client).json()["job_id"]
        assert client.get(f"/api/v1/jobs/{first}").json()["queue_position"] == 0
        assert client.get(f"/api/v1/jobs/{second}").json()["queue_position"] == 1

    @pytest.mark.parametrize("kwargs,status", [
        ({"job_description": "short"}, 400),
        ({"content": b"garbage" * 40}, 400),
        ({"filename": "cv.exe"}, 400),
        ({"criteria": "not json"}, 400),
    ])
    def test_bad_requests_are_refused_without_creating_a_job(self, client, kwargs, status):
        assert create(client, **kwargs).status_code == status
        assert client.portal.call(collection("scan_jobs").count_documents, {}) == 0

    def test_infected_file_is_refused_before_it_is_queued(self, client, fake_scanner):
        fake_scanner.verdict = "Eicar-Test-Signature"
        assert create(client).status_code == 400
        assert client.portal.call(collection("scan_jobs").count_documents, {}) == 0

    def test_quota_is_checked_before_queueing(self, client, monkeypatch):
        monkeypatch.setenv("QUOTA_SCANS_PER_MONTH", "1")
        client.portal.call(collection("usage_records").insert_one, {
            "scan_id": "x", "tenant_id": "default", "created_at": utc_now(),
            "input_tokens": 1, "output_tokens": 1, "cost_usd": 0.0, "latency_ms": 1.0, "used_fallback": False,
        })
        response = create(client)
        assert response.status_code == 429 and "Monthly scan limit" in response.json()["detail"]

    def test_too_many_waiting_jobs_for_one_tenant(self, client, monkeypatch):
        monkeypatch.setenv("JOB_MAX_PENDING_PER_TENANT", "2")
        assert create(client).status_code == 202 and create(client).status_code == 202
        blocked = create(client)
        assert blocked.status_code == 429 and "waiting" in blocked.json()["detail"]

    def test_the_stored_upload_is_not_exposed_by_the_api(self, client):
        job_id = create(client).json()["job_id"]
        assert "file" not in client.get(f"/api/v1/jobs/{job_id}").json()


class TestRunning:
    def test_worker_completes_the_job_with_the_full_result(self, client):
        job_id = create(client).json()["job_id"]
        assert run_one(client) is True
        job = client.get(f"/api/v1/jobs/{job_id}").json()
        assert job["status"] == "succeeded" and job["queue_position"] is None
        assert job["result"]["match_score"] == 82 and job["result"]["breakdown"]["matched_skills"] == ["python"]
        assert job["scan_id"] == job["result"]["id"]
        assert client.get(f"/api/v1/scan/{job['scan_id']}").status_code == 200

    def test_nothing_to_do_returns_false(self, client):
        assert run_one(client) is False

    def test_jobs_run_oldest_first(self, client):
        first, second = create(client).json()["job_id"], create(client).json()["job_id"]
        run_one(client)
        assert client.get(f"/api/v1/jobs/{first}").json()["status"] == "succeeded"
        assert client.get(f"/api/v1/jobs/{second}").json()["status"] == "queued"

    def test_the_upload_is_deleted_once_the_job_finishes(self, client):
        job_id = create(client).json()["job_id"]
        run_one(client)
        stored = client.portal.call(collection("scan_jobs").find_one, {"id": job_id})
        assert "file" not in stored

    def test_unreadable_file_fails_the_job_with_a_reason(self, client):
        job_id = create(client, content=make_encrypted_pdf()).json()["job_id"]
        run_one(client)
        job = client.get(f"/api/v1/jobs/{job_id}").json()
        assert job["status"] == "failed" and job["result"] is None
        assert job["error"]["status_code"] == 400 and "password-protected" in job["error"]["detail"]

    def test_failed_job_also_drops_the_upload(self, client):
        job_id = create(client, content=make_encrypted_pdf()).json()["job_id"]
        run_one(client)
        assert "file" not in client.portal.call(collection("scan_jobs").find_one, {"id": job_id})

    def test_unexpected_crash_fails_the_job_without_leaking_details(self, client, monkeypatch):
        import services.jobs as jobs_module

        async def boom(*args, **kwargs):
            raise RuntimeError("secret internal detail")
        monkeypatch.setattr(jobs_module, "process_scan", boom)
        job_id = create(client).json()["job_id"]
        run_one(client)
        job = client.get(f"/api/v1/jobs/{job_id}").json()
        assert job["status"] == "failed" and "secret" not in job["error"]["detail"]

    def test_quota_is_rechecked_when_the_job_starts(self, client, monkeypatch):
        job_id = create(client).json()["job_id"]
        monkeypatch.setenv("QUOTA_SCANS_PER_MONTH", "1")
        client.portal.call(collection("usage_records").insert_one, {
            "scan_id": "x", "tenant_id": "default", "created_at": utc_now(),
            "input_tokens": 1, "output_tokens": 1, "cost_usd": 0.0, "latency_ms": 1.0, "used_fallback": False,
        })
        run_one(client)
        job = client.get(f"/api/v1/jobs/{job_id}").json()
        assert job["status"] == "failed" and job["error"]["status_code"] == 429

    def test_usage_is_recorded_for_background_scans(self, client):
        create(client)
        run_one(client)
        assert client.get("/api/v1/usage").json()["scans"] == 1

    def test_result_survives_a_failed_save_through_the_job(self, client, monkeypatch):
        from tests.test_api import make_scan_saves_fail
        job_id = create(client).json()["job_id"]
        make_scan_saves_fail(monkeypatch)
        run_one(client)
        job = client.get(f"/api/v1/jobs/{job_id}").json()
        assert job["status"] == "succeeded" and job["result"]["saved"] is False

    def test_logs_of_a_job_carry_the_request_id_that_queued_it(self, client, caplog):
        import logging
        response = create(client)
        request_id = response.headers["X-Request-ID"]
        with caplog.at_level(logging.INFO):
            run_one(client)
        assert any(getattr(r, "request_id", None) == request_id and "Job " in r.getMessage() for r in caplog.records)


class TestJobAccess:
    def test_unknown_job_is_404(self, client):
        assert client.get("/api/v1/jobs/nope").status_code == 404

    def test_a_tenant_cannot_see_another_tenants_job(self, client):
        from deps import get_tenant_id
        job_id = create(client).json()["job_id"]
        client.app.dependency_overrides[get_tenant_id] = lambda: "someone-else"
        try:
            assert client.get(f"/api/v1/jobs/{job_id}").status_code == 404
        finally:
            client.app.dependency_overrides.clear()
        assert client.get(f"/api/v1/jobs/{job_id}").status_code == 200


class TestRecovery:
    def test_orphaned_running_job_is_requeued(self, client, monkeypatch):
        job_id = create(client).json()["job_id"]
        run_one_claim = client.portal.call(database_module.database.claim_next_job, utc_now() - timedelta(hours=1), "dead-worker")
        assert run_one_claim["status"] == "running"
        client.portal.call(client.app.state.job_runner.housekeeping)
        assert client.get(f"/api/v1/jobs/{job_id}").json()["status"] == "queued"
        assert run_one(client) is True
        assert client.get(f"/api/v1/jobs/{job_id}").json()["status"] == "succeeded"

    def test_recent_running_job_is_left_alone(self, client):
        job_id = create(client).json()["job_id"]
        client.portal.call(database_module.database.claim_next_job, utc_now(), "busy-worker")
        client.portal.call(client.app.state.job_runner.housekeeping)
        assert client.get(f"/api/v1/jobs/{job_id}").json()["status"] == "running"

    def test_job_that_keeps_dying_is_failed(self, client, monkeypatch):
        monkeypatch.setenv("JOB_MAX_ATTEMPTS", "2")
        job_id = create(client).json()["job_id"]
        old = utc_now() - timedelta(hours=1)
        for _ in range(2):  # claimed twice, never finished
            client.portal.call(database_module.database.claim_next_job, old, "dead-worker")
            client.portal.call(client.app.state.job_runner.housekeeping)
            if client.get(f"/api/v1/jobs/{job_id}").json()["status"] == "failed":
                break
        job = client.get(f"/api/v1/jobs/{job_id}").json()
        assert job["status"] == "failed" and "interrupted" in job["error"]["detail"]

    def test_old_finished_jobs_are_deleted(self, client):
        job_id = create(client).json()["job_id"]
        run_one(client)
        client.portal.call(collection("scan_jobs").update_one, {"id": job_id}, {"$set": {"finished_at": utc_now() - timedelta(days=2)}})
        client.portal.call(client.app.state.job_runner.housekeeping)
        assert client.get(f"/api/v1/jobs/{job_id}").status_code == 404

    def test_recent_finished_jobs_are_kept(self, client):
        job_id = create(client).json()["job_id"]
        run_one(client)
        client.portal.call(client.app.state.job_runner.housekeeping)
        assert client.get(f"/api/v1/jobs/{job_id}").status_code == 200


class TestBackgroundWorkers:
    def test_real_workers_finish_a_job_without_help(self, client, monkeypatch):
        import asyncio
        from services.jobs import JobRunner
        runner = JobRunner(client.app.state.ai_processor, None, workers=2)
        client.portal.call(runner.start)
        try:
            job_id = create(client).json()["job_id"]
            runner.notify()
            deadline = time.time() + 10
            status = "queued"
            while time.time() < deadline and status not in ("succeeded", "failed"):
                time.sleep(0.05)
                status = client.get(f"/api/v1/jobs/{job_id}").json()["status"]
            assert status == "succeeded"
        finally:
            client.portal.call(runner.stop)

    def test_many_jobs_each_run_exactly_once(self, client):
        from services.jobs import JobRunner
        runner = JobRunner(client.app.state.ai_processor, None, workers=3)
        client.portal.call(runner.start)
        try:
            ids = [create(client).json()["job_id"] for _ in range(6)]
            runner.notify()
            deadline = time.time() + 15
            while time.time() < deadline:
                statuses = [client.get(f"/api/v1/jobs/{i}").json()["status"] for i in ids]
                if all(s == "succeeded" for s in statuses):
                    break
                time.sleep(0.05)
            assert all(s == "succeeded" for s in statuses)
            assert client.get("/api/v1/scan_history").json()["total_count"] == 6
            assert client.get("/api/v1/usage").json()["scans"] == 6
        finally:
            client.portal.call(runner.stop)


class TestIdempotency:
    def test_same_key_and_upload_returns_the_same_job(self, client):
        first = create(client, key="order-1")
        second = create(client, key="order-1")
        assert second.status_code == 202 and second.json() == first.json()
        assert second.headers["Idempotent-Replay"] == "true" and "Idempotent-Replay" not in first.headers
        assert client.portal.call(collection("scan_jobs").count_documents, {}) == 1

    def test_replay_after_the_job_finished_still_points_to_it(self, client):
        first = create(client, key="k-1").json()
        run_one(client)
        assert create(client, key="k-1").json() == first
        assert client.get(first["status_url"]).json()["status"] == "succeeded"

    def test_retry_does_not_cost_a_second_scan(self, client, fake_provider):
        create(client, key="k-2")
        create(client, key="k-2")
        while run_one(client):
            pass
        assert client.get("/api/v1/usage").json()["scans"] == 1

    def test_same_key_with_a_different_file_is_rejected(self, client):
        create(client, key="k-3")
        other = create(client, content=make_pdf("A completely different resume. " * 10), key="k-3")
        assert other.status_code == 422 and "different upload" in other.json()["detail"]

    def test_same_key_with_different_settings_is_rejected(self, client):
        create(client, key="k-4")
        assert create(client, key="k-4", criteria='{"skills_weight": 90}').status_code == 422
        assert create(client, key="k-4", job_description=JOB_DESCRIPTION + " Extra detail.").status_code == 422

    def test_equivalent_criteria_spelled_differently_match(self, client):
        first = create(client, key="k-5", criteria='{"skills_weight": 50, "experience_weight": 30}')
        second = create(client, key="k-5", criteria='{"experience_weight":30,"skills_weight":50}')
        assert second.json() == first.json()

    def test_request_still_in_progress_gets_409(self, client):
        from services import idempotency
        fingerprint = idempotency.fingerprint(PDF, "cv.pdf", JOB_DESCRIPTION, idempotency.canonical_json(
            __import__("scoring").ScoringCriteria().model_dump()))
        client.portal.call(collection("idempotency_keys").insert_one, {
            "tenant_id": "default", "key": "k-6", "fingerprint": fingerprint, "state": "in_progress", "created_at": utc_now()})
        response = create(client, key="k-6")
        assert response.status_code == 409 and "still being processed" in response.json()["detail"]

    def test_keys_are_per_tenant(self, client):
        from accounts import Principal
        from deps import get_principal
        first = create(client, key="shared").json()
        client.app.dependency_overrides[get_principal] = lambda: Principal(user_id=None, org_id="other-tenant", role="owner")
        try:
            second = create(client, key="shared").json()
        finally:
            client.app.dependency_overrides.clear()
        assert second["job_id"] != first["job_id"]

    @pytest.mark.parametrize("key", ["has space", "x" * 101, "semi;colon", "slash/key"])
    def test_malformed_keys_are_rejected(self, client, key):
        response = create(client, key=key)
        assert response.status_code == 400 and "Idempotency-Key" in response.json()["detail"]

    def test_without_a_key_every_request_is_a_new_job(self, client):
        assert create(client).json()["job_id"] != create(client).json()["job_id"]

    def test_a_refused_attempt_releases_the_key_for_a_retry(self, client, fake_scanner):
        fake_scanner.verdict = "Eicar-Test-Signature"
        assert create(client, key="k-7").status_code == 400
        fake_scanner.verdict = None
        retry = create(client, key="k-7")
        assert retry.status_code == 202 and "Idempotent-Replay" not in retry.headers

    def test_failure_while_queueing_releases_the_key(self, client, monkeypatch):
        monkeypatch.setenv("JOB_MAX_PENDING_PER_TENANT", "1")
        create(client)
        assert create(client, key="k-8").status_code == 429
        run_one(client)
        assert create(client, key="k-8").status_code == 202

    def test_old_keys_are_forgotten(self, client):
        create(client, key="k-9")
        client.portal.call(collection("idempotency_keys").update_one, {"key": "k-9"},
                           {"$set": {"created_at": utc_now() - timedelta(days=2)}})
        client.portal.call(client.app.state.job_runner.housekeeping)
        assert client.portal.call(collection("idempotency_keys").count_documents, {}) == 0
