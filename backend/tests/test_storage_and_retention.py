import hashlib
from datetime import timedelta

import pytest

import storage as storage_module
from database import database as app_database
from models import utc_now
from services import retention
from storage import LocalFileStorage, S3FileStorage, StorageError, make_key


class TestKeys:
    def test_key_is_namespaced_by_scan(self):
        assert make_key("abc", "cv.pdf") == "resumes/abc/cv.pdf"

    @pytest.mark.parametrize("name", ["../../etc/passwd", "..\\..\\windows\\system32", "a b/c d.pdf", "", None])
    def test_hostile_filenames_cannot_escape(self, name):
        key = make_key("abc", name)
        assert key.startswith("resumes/abc/") and ".." not in key and "\\" not in key
        assert key.count("/") == 2


class TestLocalStorage:
    async def test_put_exists_delete(self, tmp_path):
        store = LocalFileStorage(tmp_path)
        await store.put("resumes/1/cv.pdf", b"data", "application/pdf")
        assert await store.exists("resumes/1/cv.pdf")
        assert (tmp_path / "resumes" / "1" / "cv.pdf").read_bytes() == b"data"
        await store.delete("resumes/1/cv.pdf")
        assert not await store.exists("resumes/1/cv.pdf")
        assert not (tmp_path / "resumes" / "1").exists()  # empty folder removed

    async def test_deleting_a_missing_file_is_fine(self, tmp_path):
        await LocalFileStorage(tmp_path).delete("resumes/none/cv.pdf")

    async def test_path_traversal_is_refused(self, tmp_path):
        with pytest.raises(StorageError, match="outside"):
            await LocalFileStorage(tmp_path / "root").put("../escape.txt", b"x", "text/plain")


class TestS3Storage:
    @pytest.fixture
    def s3(self, monkeypatch):
        from moto import mock_aws
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
        with mock_aws():
            yield S3FileStorage(bucket="resumes-test", region="us-east-1")

    async def test_bucket_is_created_when_missing(self, s3):
        await s3.ensure_ready()
        await s3.ensure_ready()  # second call finds it

    async def test_put_exists_delete(self, s3):
        await s3.ensure_ready()
        await s3.put("resumes/1/cv.pdf", b"data", "application/pdf")
        assert await s3.exists("resumes/1/cv.pdf")
        body = s3._client.get_object(Bucket="resumes-test", Key="resumes/1/cv.pdf")
        assert body["Body"].read() == b"data" and body["ContentType"] == "application/pdf"
        await s3.delete("resumes/1/cv.pdf")
        assert not await s3.exists("resumes/1/cv.pdf")

    async def test_failures_become_storage_errors(self, s3):
        # no bucket was created
        with pytest.raises(StorageError):
            await s3.put("resumes/1/cv.pdf", b"x", "application/pdf")


class TestFactory:
    def test_none(self, monkeypatch):
        monkeypatch.setenv("STORAGE_BACKEND", "none")
        assert storage_module.get_storage() is None

    def test_local_uses_configured_folder(self, monkeypatch, tmp_path):
        monkeypatch.setenv("STORAGE_BACKEND", "local")
        monkeypatch.setenv("STORAGE_LOCAL_DIR", str(tmp_path))
        assert storage_module.get_storage().root == tmp_path.resolve()

    def test_unknown_is_rejected(self, monkeypatch):
        monkeypatch.setenv("STORAGE_BACKEND", "ftp")
        with pytest.raises(ValueError, match="Unknown STORAGE_BACKEND"):
            storage_module.get_storage()


@pytest.fixture
async def wired(test_db, storage, monkeypatch):
    """Retention code uses the shared `database` object; point it at the in-memory one"""
    monkeypatch.setattr(retention, "database", test_db)
    await storage.ensure_ready()
    return test_db


class TestArchive:
    async def test_stores_file_and_record(self, wired, storage):
        assert await retention.archive_original(storage, "s1", "cv.pdf", b"content", "application/pdf") is True
        record = await wired.get_file_record("s1")
        assert await storage.exists(record["key"])
        assert record["size"] == 7 and record["sha256"] == hashlib.sha256(b"content").hexdigest()
        assert record["expires_at"] - record["created_at"] == timedelta(days=retention.retention_days())

    async def test_retention_days_comes_from_config(self, wired, storage, monkeypatch):
        monkeypatch.setenv("FILE_RETENTION_DAYS", "7")
        await retention.archive_original(storage, "s1", "cv.pdf", b"x", "application/pdf")
        record = await wired.get_file_record("s1")
        assert record["expires_at"] - record["created_at"] == timedelta(days=7)

    async def test_no_storage_means_nothing_kept(self, wired):
        assert await retention.archive_original(None, "s1", "cv.pdf", b"x", "application/pdf") is False
        assert await wired.get_file_record("s1") is None

    async def test_storage_failure_is_reported_not_raised(self, wired, storage, monkeypatch):
        async def fail(*args, **kwargs):
            raise StorageError("disk full")
        monkeypatch.setattr(storage, "put", fail)
        assert await retention.archive_original(storage, "s1", "cv.pdf", b"x", "application/pdf") is False
        assert await wired.get_file_record("s1") is None

    async def test_file_is_taken_back_if_its_record_cannot_be_saved(self, wired, storage, monkeypatch):
        from database import DatabaseError

        async def fail(record):
            raise DatabaseError("down")
        monkeypatch.setattr(wired, "save_file_record", fail)
        assert await retention.archive_original(storage, "s1", "cv.pdf", b"x", "application/pdf") is False
        assert not await storage.exists(make_key("s1", "cv.pdf"))  # no unreachable file left behind


class TestDeleteAndSweep:
    async def test_delete_original_removes_file_and_record(self, wired, storage):
        await retention.archive_original(storage, "s1", "cv.pdf", b"x", "application/pdf")
        key = (await wired.get_file_record("s1"))["key"]
        await retention.delete_original(storage, "s1")
        assert not await storage.exists(key) and await wired.get_file_record("s1") is None

    async def test_failed_delete_leaves_record_due_for_next_sweep(self, wired, storage, monkeypatch):
        await retention.archive_original(storage, "s1", "cv.pdf", b"x", "application/pdf")

        async def fail(key):
            raise StorageError("unreachable")
        real_delete = storage.delete
        monkeypatch.setattr(storage, "delete", fail)
        await retention.delete_original(storage, "s1")

        record = await wired.get_file_record("s1")
        assert record is not None and record["expires_at"] <= utc_now()
        monkeypatch.setattr(storage, "delete", real_delete)  # storage is back
        assert await retention.purge_expired(storage) == 1
        assert await wired.get_file_record("s1") is None

    async def test_sweep_removes_only_expired_files(self, wired, storage):
        for scan_id in ("old", "fresh"):
            await retention.archive_original(storage, scan_id, "cv.pdf", b"x", "application/pdf")
        await wired.db.scan_files.update_one({"scan_id": "old"}, {"$set": {"expires_at": utc_now() - timedelta(days=1)}})

        assert await retention.purge_expired(storage) == 1
        assert not await storage.exists(make_key("old", "cv.pdf"))
        assert await storage.exists(make_key("fresh", "cv.pdf"))
        assert await wired.get_file_record("old") is None and await wired.get_file_record("fresh") is not None

    async def test_sweep_keeps_going_when_one_file_fails(self, wired, storage, monkeypatch):
        for scan_id in ("a", "b"):
            await retention.archive_original(storage, scan_id, "cv.pdf", b"x", "application/pdf")
            await wired.db.scan_files.update_one({"scan_id": scan_id}, {"$set": {"expires_at": utc_now() - timedelta(hours=1)}})
        real_delete = storage.delete

        async def flaky(key):
            if "/a/" in key:
                raise StorageError("boom")
            await real_delete(key)
        monkeypatch.setattr(storage, "delete", flaky)
        assert await retention.purge_expired(storage) == 1
        assert await wired.get_file_record("a") is not None  # kept for the next sweep
        assert await wired.get_file_record("b") is None

    async def test_sweep_with_no_storage_does_nothing(self, wired):
        assert await retention.purge_expired(None) == 0
