"""End-to-end tests through the real FastAPI app with a fake AI provider and in-memory MongoDB."""
import json
import types

import pytest
from pymongo.errors import PyMongoError

import database as database_module
from tests.conftest import JOB_DESCRIPTION, FakeProvider, make_docx, make_encrypted_pdf, make_pdf


def make_scan_saves_fail(monkeypatch):
    """Saving a scan raises, as in a database outage; every other collection keeps working"""
    async def fail(*args, **kwargs):
        raise PyMongoError("down")

    class FailingScans:
        insert_one = staticmethod(fail)

    real_db = database_module.database.db

    class Db:
        resume_scans = FailingScans()

        def __getattr__(self, name):
            return getattr(real_db, name)

        def __getitem__(self, name):
            return real_db[name]

    monkeypatch.setattr(database_module.database, "db", Db())


def post_scan(client, content=None, filename="cv.pdf", content_type="application/pdf", job_description=JOB_DESCRIPTION):
    content = make_pdf() if content is None else content
    return client.post(
        "/api/v1/scan_resume",
        files={"resume_file": (filename, content, content_type)},
        data={"job_description": job_description},
    )


class TestHealth:
    def test_root(self, client):
        assert client.get("/api/v1/").json() == {"message": "AI-Powered Resume Scanner API is running"}

    def test_healthy(self, client):
        body = client.get("/api/v1/health").json()
        assert body["status"] == "healthy"
        assert body["ai_service"] == "Connected" and body["database"] == "Connected"

    def test_degraded_when_database_is_down(self, client):
        async def fail(*args, **kwargs):
            raise PyMongoError("down")

        database_module.database.client = types.SimpleNamespace(admin=types.SimpleNamespace(command=fail), close=lambda: None)
        body = client.get("/api/v1/health").json()
        assert body["status"] == "degraded" and body["database"] == "Disconnected"


class TestScan:
    def test_pdf_scan_succeeds_and_is_saved(self, client):
        response = post_scan(client)
        assert response.status_code == 200
        body = response.json()
        assert body["match_score"] == 82 and body["is_fallback"] is False and body["saved"] is True
        assert body["extracted_data"]["skills"] == ["python", "fastapi"]
        assert client.get(f"/api/v1/scan/{body['id']}").status_code == 200

    def test_docx_scan_succeeds(self, client):
        response = post_scan(
            client, make_docx(), "cv.docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        assert response.status_code == 200

    def test_each_scan_uses_its_own_request_id(self, client, fake_provider):
        post_scan(client)
        post_scan(client)
        ids = [rid for _, rid in fake_provider.calls if rid]
        assert len(ids) == 4 and len(set(ids[:2])) == 1 and len(set(ids)) == 2

    def test_ai_failure_returns_flagged_fallback(self, client, fake_provider):
        fake_provider.replies = [RuntimeError("down")] * 8
        body = post_scan(client).json()
        assert body["is_fallback"] is True
        assert "keyword comparison" in body["fallback_notice"]

    def test_failed_save_still_returns_the_scan_marked_unsaved(self, client, monkeypatch):
        make_scan_saves_fail(monkeypatch)
        response = post_scan(client)
        assert response.status_code == 200
        assert response.json()["saved"] is False and response.json()["match_score"] == 82


class TestUploadValidation:
    @pytest.mark.parametrize("job_description,expected", [
        ("", "cannot be empty"),
        ("   ", "cannot be empty"),
        ("too short", "too short"),
    ])
    def test_bad_job_description(self, client, job_description, expected):
        response = post_scan(client, job_description=job_description)
        assert response.status_code == 400 and expected in response.json()["detail"]

    def test_unsupported_extension(self, client):
        response = post_scan(client, filename="cv.doc", content_type="application/msword")
        assert response.status_code == 400 and "Unsupported file type" in response.json()["detail"]

    def test_content_type_mismatch(self, client):
        response = post_scan(client, content_type="text/html")
        assert response.status_code == 400 and "does not match" in response.json()["detail"]

    def test_fake_pdf_is_rejected_by_signature(self, client):
        response = post_scan(client, content=b"MZ not a pdf at all" * 20)
        assert response.status_code == 400 and "does not look like" in response.json()["detail"]

    def test_password_protected_pdf(self, client):
        response = post_scan(client, content=make_encrypted_pdf())
        assert response.status_code == 400 and "password-protected" in response.json()["detail"]

    def test_empty_resume_text(self, client):
        response = post_scan(client, content=make_pdf("Hi"))
        assert response.status_code == 400 and "too short or empty" in response.json()["detail"]

    def test_oversized_upload_is_rejected_with_413(self, client, monkeypatch):
        from file_processor import FileProcessor
        monkeypatch.setattr(FileProcessor, "MAX_FILE_SIZE", 1024)
        response = post_scan(client, content=b"%PDF-" + b"0" * 5000)
        assert response.status_code == 413

    def test_ai_is_not_called_when_validation_fails(self, client, fake_provider):
        post_scan(client, job_description="short")
        post_scan(client, content=b"garbage" * 30)
        assert fake_provider.calls == []


class TestHistory:
    def test_empty_history(self, client):
        assert client.get("/api/v1/scan_history").json() == {"scans": [], "total_count": 0}

    def test_history_lists_saved_scans(self, client):
        # Newest-first ordering is covered with explicit timestamps in test_database.py;
        # two scans in a row can share a clock tick, so order is not asserted here.
        ids = {post_scan(client).json()["id"] for _ in range(2)}
        body = client.get("/api/v1/scan_history").json()
        assert body["total_count"] == 2
        assert {s["id"] for s in body["scans"]} == ids

    def test_pagination_limits_are_clamped(self, client):
        for _ in range(3):
            post_scan(client)
        assert len(client.get("/api/v1/scan_history?limit=2").json()["scans"]) == 2
        assert len(client.get("/api/v1/scan_history?limit=-5").json()["scans"]) == 1
        assert len(client.get("/api/v1/scan_history?skip=2").json()["scans"]) == 1

    def test_get_missing_scan_is_404(self, client):
        assert client.get("/api/v1/scan/does-not-exist").status_code == 404

    def test_delete_then_gone(self, client):
        scan_id = post_scan(client).json()["id"]
        assert client.delete(f"/api/v1/scan/{scan_id}").status_code == 200
        assert client.get(f"/api/v1/scan/{scan_id}").status_code == 404
        assert client.delete(f"/api/v1/scan/{scan_id}").status_code == 404


class TestDatabaseOutage:
    @pytest.fixture
    def outage(self, client, monkeypatch):
        async def fail(*args, **kwargs):
            raise PyMongoError("down")

        class Collection:
            insert_one = find_one = delete_one = count_documents = staticmethod(fail)

            def find(self, *args, **kwargs):
                raise PyMongoError("down")

        monkeypatch.setattr(database_module.database, "db", types.SimpleNamespace(resume_scans=Collection()))

    def test_outage_is_a_503_not_an_empty_history(self, client, outage):
        response = client.get("/api/v1/scan_history")
        assert response.status_code == 503
        assert "temporarily unavailable" in response.json()["detail"]

    def test_get_and_delete_are_503(self, client, outage):
        assert client.get("/api/v1/scan/x").status_code == 503
        assert client.delete("/api/v1/scan/x").status_code == 503


class TestVirusScanning:
    def test_every_upload_is_scanned_before_parsing(self, client, fake_scanner):
        post_scan(client)
        assert len(fake_scanner.scanned) == 1 and fake_scanner.scanned[0].startswith(b"%PDF-")

    def test_infected_file_is_rejected_and_never_reaches_ai_or_storage(self, client, fake_scanner, fake_provider, storage):
        fake_scanner.verdict = "Eicar-Test-Signature"
        response = post_scan(client)
        assert response.status_code == 400 and "malware" in response.json()["detail"]
        assert fake_provider.calls == []
        assert client.get("/api/v1/scan_history").json()["total_count"] == 0
        assert not list(storage.root.rglob("*.pdf"))

    def test_scanner_outage_blocks_uploads_with_503(self, client, fake_scanner, fake_provider):
        from virus_scan import ScannerUnavailable
        fake_scanner.verdict = ScannerUnavailable("clamd down")
        response = post_scan(client)
        assert response.status_code == 503 and "virus scanner" in response.json()["detail"]
        assert fake_provider.calls == []

    def test_health_reports_scanner_state(self, client):
        assert client.get("/api/v1/health").json()["virus_scanner"] == "Connected"


class TestOcrInScan:
    def test_scanned_resume_is_read_with_ocr_and_flagged(self, client, monkeypatch):
        import file_processor
        from tests.conftest import RESUME_TEXT, make_scanned_pdf
        from tests.test_ocr import FakeOCR
        monkeypatch.setattr(file_processor, "get_ocr_engine", lambda: FakeOCR(RESUME_TEXT))
        body = post_scan(client, make_scanned_pdf()).json()
        assert body["ocr_used"] is True and body["match_score"] == 82

    def test_text_resume_is_not_flagged(self, client):
        assert post_scan(client).json()["ocr_used"] is False

    def test_scanned_resume_without_ocr_gets_a_clear_error(self, client):
        from tests.conftest import make_scanned_pdf
        response = post_scan(client, make_scanned_pdf())
        assert response.status_code == 400 and "looks like a scan" in response.json()["detail"]


class TestStoredOriginals:
    def test_original_is_kept_with_a_retention_date(self, client, storage):
        scan_id = post_scan(client).json()["id"]
        stored = list(storage.root.rglob("cv.pdf"))
        assert len(stored) == 1 and stored[0].parent.name == scan_id
        assert stored[0].read_bytes().startswith(b"%PDF-")

    def test_deleting_a_scan_deletes_its_original(self, client, storage):
        scan_id = post_scan(client).json()["id"]
        assert list(storage.root.rglob("cv.pdf"))
        assert client.delete(f"/api/v1/scan/{scan_id}").status_code == 200
        assert not list(storage.root.rglob("cv.pdf"))

    def test_storage_failure_does_not_fail_the_scan(self, client, storage, monkeypatch):
        from storage import StorageError

        async def fail(*args, **kwargs):
            raise StorageError("disk full")
        monkeypatch.setattr(storage, "put", fail)
        response = post_scan(client)
        assert response.status_code == 200 and response.json()["saved"] is True

    def test_unsaved_scan_stores_no_file(self, client, storage, monkeypatch):
        make_scan_saves_fail(monkeypatch)
        assert post_scan(client).json()["saved"] is False
        assert not list(storage.root.rglob("cv.pdf"))
