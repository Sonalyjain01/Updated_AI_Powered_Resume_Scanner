import types
from datetime import timedelta

import pytest
from pymongo.errors import PyMongoError

import database as database_module
import migrations
from database import DatabaseError
from models import ExtractedData, ResumeAnalysisResponse, utc_now


def make_scan(name="cv.pdf", **overrides):
    return ResumeAnalysisResponse(
        filename=name,
        extracted_data=ExtractedData(skills=["python"]),
        match_score=75,
        job_description="a job description",
        analysis_summary="fine",
        **overrides,
    )


class TestCrud:
    async def test_save_and_get(self, test_db):
        scan = make_scan()
        await test_db.save_scan_result(scan)
        loaded = await test_db.get_scan_by_id(scan.id, "default")
        assert loaded.id == scan.id and loaded.filename == "cv.pdf"
        assert loaded.created_at.tzinfo is not None  # timestamps stay timezone-aware

    async def test_missing_scan_is_none_not_an_error(self, test_db):
        assert await test_db.get_scan_by_id("nope", "default") is None

    async def test_history_is_newest_first_and_paginated(self, test_db):
        base = utc_now()
        for i in range(5):
            await test_db.save_scan_result(make_scan(f"cv{i}.pdf", created_at=base + timedelta(minutes=i)))
        history = await test_db.get_scan_history("default", limit=2, skip=1)
        assert [s.filename for s in history] == ["cv3.pdf", "cv2.pdf"]
        assert await test_db.get_total_scans_count("default") == 5

    async def test_delete(self, test_db):
        scan = make_scan()
        await test_db.save_scan_result(scan)
        assert await test_db.delete_scan(scan.id, "default") is True
        assert await test_db.delete_scan(scan.id, "default") is False

    async def test_unreadable_record_is_skipped_not_fatal(self, test_db):
        await test_db.save_scan_result(make_scan("good.pdf"))
        await test_db.db.resume_scans.insert_one({"id": "corrupt"})
        history = await test_db.get_scan_history("default")
        assert [s.filename for s in history] == ["good.pdf"]


class TestOutage:
    @pytest.fixture
    def broken(self, test_db):
        """Every collection call fails like a lost connection"""
        async def fail(*args, **kwargs):
            raise PyMongoError("connection lost")

        class Collection:
            insert_one = find_one = delete_one = count_documents = staticmethod(fail)

            def find(self, *args, **kwargs):
                raise PyMongoError("connection lost")

        test_db.db = types.SimpleNamespace(resume_scans=Collection())
        test_db.client = types.SimpleNamespace(admin=types.SimpleNamespace(command=fail), close=lambda: None)
        return test_db

    async def test_each_operation_raises_instead_of_returning_empty(self, broken):
        with pytest.raises(DatabaseError):
            await broken.get_scan_history("default")
        with pytest.raises(DatabaseError):
            await broken.get_total_scans_count("default")
        with pytest.raises(DatabaseError):
            await broken.get_scan_by_id("x", "default")
        with pytest.raises(DatabaseError):
            await broken.delete_scan("x", "default")
        with pytest.raises(DatabaseError):
            await broken.save_scan_result(make_scan())

    async def test_ping_reports_false_without_raising(self, broken):
        assert await broken.ping() is False

    async def test_not_connected_raises(self):
        with pytest.raises(DatabaseError, match="not connected"):
            await database_module.Database().get_total_scans_count("default")


class TestMigrations:
    async def test_indexes_are_created(self, test_db):
        indexes = await test_db.db.resume_scans.index_information()
        assert indexes["uniq_scan_id"]["unique"] is True
        assert "scan_created_at_desc" in indexes

    async def test_unique_index_blocks_duplicate_ids(self, test_db):
        scan = make_scan()
        await test_db.save_scan_result(scan)
        with pytest.raises(DatabaseError):
            await test_db.save_scan_result(scan)

    async def test_versions_are_recorded_and_rerun_is_a_no_op(self, test_db):
        recorded = [d["version"] async for d in test_db.db.schema_migrations.find()]
        assert recorded == sorted(recorded) and len(recorded) == len(migrations.MIGRATIONS)
        assert await migrations.run_migrations(test_db.db) == 0

    async def test_backfill_updates_old_scans_only(self, test_db):
        await test_db.db.resume_scans.insert_many([
            {"id": "old"},
            {"id": "new", "is_fallback": True, "fallback_notice": "n", "saved": False},
        ])
        await test_db.db.schema_migrations.delete_one({"version": 2})
        await migrations.run_migrations(test_db.db)
        old = await test_db.db.resume_scans.find_one({"id": "old"})
        new = await test_db.db.resume_scans.find_one({"id": "new"})
        assert (old["is_fallback"], old["fallback_notice"], old["saved"]) == (False, None, True)
        assert (new["is_fallback"], new["fallback_notice"], new["saved"]) == (True, "n", False)
