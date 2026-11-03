import logging

import pytest

from request_context import accept_or_generate, get_request_id
from tests.test_api import post_scan


class TestVersioning:
    def test_v1_is_the_supported_prefix(self, client):
        assert client.get("/api/v1/health").status_code == 200
        assert "Deprecation" not in client.get("/api/v1/health").headers

    def test_unversioned_paths_still_work_but_are_flagged(self, client):
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.headers["Deprecation"] == "true"
        assert response.headers["Link"] == '</api/v1>; rel="successor-version"'

    def test_unversioned_scan_still_works(self, client):
        from tests.conftest import JOB_DESCRIPTION, make_pdf
        response = client.post(
            "/api/scan_resume",
            files={"resume_file": ("cv.pdf", make_pdf(), "application/pdf")},
            data={"job_description": JOB_DESCRIPTION},
        )
        assert response.status_code == 200 and response.headers["Deprecation"] == "true"

    def test_docs_describe_only_v1(self, client):
        paths = client.get("/openapi.json").json()["paths"]
        assert paths and all(path.startswith("/api/v1/") for path in paths)

    def test_inline_scan_is_marked_deprecated_in_the_docs(self, client):
        operation = client.get("/openapi.json").json()["paths"]["/api/v1/scan_resume"]["post"]
        assert operation["deprecated"] is True


class TestRequestIds:
    def test_every_response_has_an_id(self, client):
        value = client.get("/api/v1/").headers["X-Request-ID"]
        assert len(value) == 32

    def test_each_request_gets_a_different_id(self, client):
        assert client.get("/api/v1/").headers["X-Request-ID"] != client.get("/api/v1/").headers["X-Request-ID"]

    def test_caller_supplied_id_is_kept(self, client):
        response = client.get("/api/v1/", headers={"X-Request-ID": "trace-abc.123"})
        assert response.headers["X-Request-ID"] == "trace-abc.123"

    @pytest.mark.parametrize("bad", ["has space", "semi;colon", "x" * 65, "line\tbreak", "<script>"])
    def test_unsafe_ids_are_replaced(self, client, bad):
        response = client.get("/api/v1/", headers={"X-Request-ID": bad})
        assert response.headers["X-Request-ID"] != bad and len(response.headers["X-Request-ID"]) == 32

    def test_error_responses_carry_the_id_too(self, client):
        response = post_scan(client, job_description="short")
        assert response.status_code == 400 and response.headers["X-Request-ID"]

    def test_validation_errors_carry_the_id_too(self, client):
        assert client.post("/api/v1/scan_resume").headers["X-Request-ID"]

    def test_log_lines_carry_the_request_id(self, client, caplog):
        with caplog.at_level(logging.INFO):
            response = post_scan(client)
        request_id = response.headers["X-Request-ID"]
        ours = [r for r in caplog.records if getattr(r, "request_id", None) == request_id]
        assert any("Resume scan completed" in r.getMessage() for r in ours)

    def test_id_does_not_leak_into_the_next_request(self, client, caplog):
        client.get("/api/v1/", headers={"X-Request-ID": "first"})
        assert get_request_id() == "-"

    def test_cors_lets_browsers_read_the_id(self, client):
        response = client.get("/api/v1/", headers={"Origin": "http://localhost:3000"})
        assert "x-request-id" in response.headers.get("access-control-expose-headers", "").lower()

    def test_accept_or_generate(self):
        assert accept_or_generate("ok-1") == "ok-1"
        assert accept_or_generate(None) != accept_or_generate(None)
        assert accept_or_generate("") != ""
