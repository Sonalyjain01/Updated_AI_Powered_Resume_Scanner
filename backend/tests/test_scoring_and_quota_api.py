import json
from datetime import timedelta

import pytest

import database as database_module
from models import utc_now
from scoring import ScoringCriteria, parse_criteria
from tests.conftest import JOB_DESCRIPTION, make_pdf, match_reply
from tests.test_api import post_scan


def scan_with(client, criteria=None, **fields):
    data = {"job_description": JOB_DESCRIPTION, **fields}
    if criteria is not None:
        data["criteria"] = criteria if isinstance(criteria, str) else json.dumps(criteria)
    return client.post("/api/v1/scan_resume", files={"resume_file": ("cv.pdf", make_pdf(), "application/pdf")}, data=data)


class TestCriteriaModel:
    def test_defaults_sum_to_one(self):
        assert sum(ScoringCriteria().weights().values()) == pytest.approx(1.0)

    def test_weights_are_relative(self):
        weights = ScoringCriteria(skills_weight=2, experience_weight=1, education_weight=1).weights()
        assert weights == {"skills": 0.5, "experience": 0.25, "education": 0.25}

    def test_all_zero_weights_are_rejected(self):
        with pytest.raises(ValueError, match="above zero"):
            ScoringCriteria(skills_weight=0, experience_weight=0, education_weight=0)

    @pytest.mark.parametrize("weight", [-1, 101])
    def test_weight_range(self, weight):
        with pytest.raises(ValueError):
            ScoringCriteria(skills_weight=weight)

    def test_skills_are_cleaned_and_deduplicated(self):
        criteria = ScoringCriteria(required_skills=["  Python ", "python", "", "Machine   Learning"])
        assert criteria.required_skills == ["Python", "Machine Learning"]

    def test_too_many_skills_rejected(self):
        with pytest.raises(ValueError, match="At most"):
            ScoringCriteria(required_skills=[f"skill{i}" for i in range(21)])

    def test_empty_field_means_defaults(self):
        assert parse_criteria("") == ScoringCriteria() and parse_criteria(None) == ScoringCriteria()


class TestExplainableScan:
    def test_response_explains_the_score(self, client):
        body = scan_with(client).json()
        names = [c["name"] for c in body["breakdown"]["criteria"]]
        assert names == ["skills", "experience", "education"]
        assert sum(c["contribution"] for c in body["breakdown"]["criteria"]) == pytest.approx(body["match_score"], abs=0.2)
        assert body["breakdown"]["matched_skills"] == ["python"]
        assert body["breakdown"]["missing_skills"] == ["kubernetes"]

    def test_custom_weights_change_the_score(self, client, fake_provider):
        reply = match_reply(skills=100, experience=0, education=0)
        fake_provider.replies = None
        original = fake_provider.complete

        async def complete(prompt, system_message, request_id=None):
            return reply if "skills_score" in prompt else await original(prompt, system_message, request_id)
        fake_provider.complete = complete

        assert scan_with(client).json()["match_score"] == 50.0
        weighted = scan_with(client, {"skills_weight": 100, "experience_weight": 0, "education_weight": 0}).json()
        assert weighted["match_score"] == 100.0
        assert weighted["breakdown"]["criteria"][0]["weight"] == 1.0

    def test_required_skills_reach_the_model_and_the_breakdown(self, client, fake_provider):
        body = scan_with(client, {"required_skills": ["Python", "Docker"]}).json()
        assert [s["skill"] for s in body["breakdown"]["skills"]] == ["Python", "Docker"]
        assert body["breakdown"]["custom_required_skills"] is True
        assert any('["Python", "Docker"]' in prompt for prompt, _ in fake_provider.calls)

    def test_breakdown_is_saved_with_the_scan(self, client):
        scan_id = scan_with(client).json()["id"]
        assert client.get(f"/api/v1/scan/{scan_id}").json()["breakdown"]["matched_skills"] == ["python"]

    def test_fallback_scan_has_no_breakdown(self, client, fake_provider):
        fake_provider.replies = [RuntimeError("down")] * 8
        body = scan_with(client).json()
        assert body["is_fallback"] is True and body["breakdown"] is None

    @pytest.mark.parametrize("criteria,message", [
        ("not json", "Invalid scoring criteria"),
        ({"skills_weight": 0, "experience_weight": 0, "education_weight": 0}, "above zero"),
        ({"skills_weight": 500}, "skills_weight"),
        ({"required_skills": [f"s{i}" for i in range(30)]}, "At most"),
    ])
    def test_bad_criteria_are_rejected_before_any_ai_call(self, client, fake_provider, criteria, message):
        response = scan_with(client, criteria)
        assert response.status_code == 400 and message in response.json()["detail"]
        assert fake_provider.calls == []


class TestUsageRecords:
    def usage(self, client):
        return client.get("/api/v1/usage").json()

    def test_a_scan_is_recorded_with_tokens_cost_and_latency(self, client):
        scan_id = scan_with(client).json()["id"]
        report = self.usage(client)
        assert report["scans"] == 1 and report["input_tokens"] > 0 and report["output_tokens"] > 0
        assert report["total_tokens"] == report["input_tokens"] + report["output_tokens"]
        assert report["cost_usd"] > 0 and report["average_latency_ms"] >= 0
        record = database_module.database.db.usage_records
        stored = client.portal.call(record.find_one, {"scan_id": scan_id})
        assert stored["call_count"] == 2 and stored["tenant_id"] == "default" and stored["estimated"] is True

    def test_usage_adds_up_across_scans(self, client):
        for _ in range(3):
            scan_with(client)
        assert self.usage(client)["scans"] == 3

    def test_rejected_uploads_cost_nothing_and_are_not_counted(self, client):
        post_scan(client, content=b"garbage" * 30)
        post_scan(client, job_description="short")
        assert self.usage(client)["scans"] == 0

    def test_fallback_scans_are_counted_separately(self, client, fake_provider):
        fake_provider.replies = [RuntimeError("down")] * 8
        scan_with(client)
        report = self.usage(client)
        assert report["scans"] == 1 and report["fallback_scans"] == 1

    def test_failed_calls_are_still_recorded(self, client, fake_provider):
        fake_provider.replies = [RuntimeError("down")] * 8
        scan_id = scan_with(client).json()["id"]
        stored = client.portal.call(database_module.database.db.usage_records.find_one, {"scan_id": scan_id})
        assert stored["failed_calls"] == stored["call_count"] > 0

    def test_report_shows_no_limits_by_default(self, client):
        report = self.usage(client)
        assert report["limits"] == {"scans": None, "tokens": None}
        assert report["remaining"] == {"scans": None, "tokens": None}


class TestQuota:
    def test_scan_limit_blocks_with_429_before_using_the_ai(self, client, fake_provider, monkeypatch):
        monkeypatch.setenv("QUOTA_SCANS_PER_MONTH", "2")
        assert scan_with(client).status_code == 200
        assert scan_with(client).status_code == 200
        fake_provider.calls.clear()
        blocked = scan_with(client)
        assert blocked.status_code == 429 and "Monthly scan limit" in blocked.json()["detail"]
        assert fake_provider.calls == []

    def test_token_limit_blocks(self, client, monkeypatch):
        monkeypatch.setenv("QUOTA_TOKENS_PER_MONTH", "100")
        assert scan_with(client).status_code == 200  # the first scan is what takes it over
        blocked = scan_with(client)
        assert blocked.status_code == 429 and "usage limit" in blocked.json()["detail"]

    def test_remaining_allowance_is_reported(self, client, monkeypatch):
        monkeypatch.setenv("QUOTA_SCANS_PER_MONTH", "5")
        scan_with(client)
        report = client.get("/api/v1/usage").json()
        assert report["limits"]["scans"] == 5 and report["remaining"]["scans"] == 4

    def test_last_months_usage_does_not_count(self, client, monkeypatch):
        monkeypatch.setenv("QUOTA_SCANS_PER_MONTH", "1")
        old = utc_now() - timedelta(days=40)
        client.portal.call(database_module.database.db.usage_records.insert_one, {
            "scan_id": "old", "tenant_id": "default", "created_at": old,
            "input_tokens": 10, "output_tokens": 10, "cost_usd": 0.0, "latency_ms": 1.0, "used_fallback": False,
        })
        assert scan_with(client).status_code == 200

    def test_other_tenants_usage_does_not_count(self, client, monkeypatch):
        monkeypatch.setenv("QUOTA_SCANS_PER_MONTH", "1")
        client.portal.call(database_module.database.db.usage_records.insert_one, {
            "scan_id": "x", "tenant_id": "someone-else", "created_at": utc_now(),
            "input_tokens": 10, "output_tokens": 10, "cost_usd": 0.0, "latency_ms": 1.0, "used_fallback": False,
        })
        assert scan_with(client).status_code == 200

    def test_usage_outage_does_not_block_scans(self, client, monkeypatch):
        from database import DatabaseError
        monkeypatch.setenv("QUOTA_SCANS_PER_MONTH", "1")

        async def down(*args, **kwargs):
            raise DatabaseError("down")
        monkeypatch.setattr(database_module.database, "usage_totals", down)
        assert scan_with(client).status_code == 200

    def test_quota_off_by_default(self, client):
        for _ in range(3):
            assert scan_with(client).status_code == 200
