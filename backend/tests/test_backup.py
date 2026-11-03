from datetime import datetime, timedelta, timezone

import pytest
from cryptography.fernet import Fernet

import backup
import database as database_module
from tests.helpers import PASSWORD, collection, db_call, insert_scan, scan, signup

KEY = Fernet.generate_key().decode()


def make_backup(client, tmp_path, key=None):
    return client.portal.call(lambda: backup.create_backup(database_module.database.db, tmp_path, key if key is not None else ""))


def restore(client, path, key=None, **kwargs):
    return client.portal.call(lambda: backup.restore_backup(database_module.database.db, path, key if key is not None else "", **kwargs))


def count(client, name, query=None):
    return db_call(client, collection(name).count_documents, query or {})


def populate(client):
    headers, body = signup(client)
    scan_id = scan(client, headers).json()["id"]
    return headers, body, scan_id


class TestCreateAndRead:
    def test_round_trip_keeps_every_document(self, client, tmp_path):
        headers, body, scan_id = populate(client)
        path = make_backup(client, tmp_path)
        data = backup.read_backup(path, "")
        assert [u["email"] for u in data["users"]] == ["owner@example.com"]
        assert data["resume_scans"][0]["id"] == scan_id and len(data["plans"]) == 3
        assert data["organizations"][0]["id"] == body["organization"]["id"]
        assert isinstance(data["resume_scans"][0]["created_at"], datetime)

    def test_transient_collections_are_left_out(self, client, tmp_path):
        populate(client)
        data = backup.read_backup(make_backup(client, tmp_path), "")
        assert set(data) == set(backup.BACKED_UP)
        assert "scan_jobs" not in data and "idempotency_keys" not in data

    def test_encrypted_backup_cannot_be_read_without_the_key(self, client, tmp_path):
        populate(client)
        path = make_backup(client, tmp_path, KEY)
        assert path.name.endswith(".jsonl.gz.enc")
        assert b"owner@example.com" not in path.read_bytes()
        assert backup.read_backup(path, KEY)["users"]
        with pytest.raises(backup.BackupError, match="encrypted"):
            backup.read_backup(path, "")
        with pytest.raises(backup.BackupError, match="Wrong encryption key"):
            backup.read_backup(path, Fernet.generate_key().decode())

    def test_unencrypted_backup_is_readable_and_warns(self, client, tmp_path, caplog):
        populate(client)
        with caplog.at_level("WARNING"):
            path = make_backup(client, tmp_path)
        assert path.name.endswith(".jsonl.gz") and "UNENCRYPTED" in caplog.text

    def test_corrupted_file_is_detected(self, client, tmp_path):
        populate(client)
        path = make_backup(client, tmp_path)
        path.write_bytes(path.read_bytes()[:-30])
        with pytest.raises(backup.BackupError, match="corrupted"):
            backup.read_backup(path, "")

    def test_incomplete_backup_is_detected(self, client, tmp_path):
        import gzip
        populate(client)
        path = make_backup(client, tmp_path)
        lines = gzip.decompress(path.read_bytes()).decode().splitlines()
        path.write_bytes(gzip.compress("\n".join(lines[:-2]).encode()))  # drop the last documents
        with pytest.raises(backup.BackupError, match="incomplete"):
            backup.read_backup(path, "")

    def test_a_non_backup_file_is_refused(self, tmp_path):
        import gzip
        path = tmp_path / "backup-20260101T000000Z.jsonl.gz"
        path.write_bytes(gzip.compress(b'{"hello": "world"}\n'))
        with pytest.raises(backup.BackupError, match="not a backup"):
            backup.read_backup(path, "")

    def test_no_half_written_file_is_left_behind(self, client, tmp_path):
        populate(client)
        make_backup(client, tmp_path)
        assert not list(tmp_path.glob("*.part"))


class TestPruning:
    def test_removes_only_backups_older_than_the_retention_period(self, tmp_path):
        now = datetime(2026, 10, 20, tzinfo=timezone.utc)
        names = ["backup-20260901T000000Z.jsonl.gz", "backup-20261001T000000Z.jsonl.gz.enc", "backup-20261019T000000Z.jsonl.gz"]
        for name in names:
            (tmp_path / name).write_bytes(b"x")
        (tmp_path / "notes.txt").write_text("keep me")
        assert backup.prune_backups(tmp_path, keep_days=14, now=now) == 2
        assert sorted(p.name for p in tmp_path.iterdir()) == ["backup-20261019T000000Z.jsonl.gz", "notes.txt"]

    def test_listing_ignores_unrelated_files(self, tmp_path):
        (tmp_path / "backup-20260101T000000Z.jsonl.gz").write_bytes(b"x")
        (tmp_path / "other.gz").write_bytes(b"x")
        assert [p.name for p in backup.list_backups(tmp_path)] == ["backup-20260101T000000Z.jsonl.gz"]


class TestRestore:
    def test_restores_into_an_empty_database(self, client, tmp_path):
        headers, body, scan_id = populate(client)
        path = make_backup(client, tmp_path, KEY)
        for name in backup.BACKED_UP:
            db_call(client, collection(name).delete_many, {})
        result = restore(client, path, KEY)
        assert result["users"] == 1 and result["resume_scans"] == 1
        assert client.get(f"/api/v1/scan/{scan_id}", headers=headers).status_code == 200
        assert client.post("/api/v1/auth/login", json={"email": "owner@example.com", "password": PASSWORD}).status_code == 200

    def test_refuses_to_overwrite_existing_data_unless_told_to(self, client, tmp_path):
        populate(client)
        path = make_backup(client, tmp_path)
        with pytest.raises(backup.BackupError, match="already has data"):
            restore(client, path)
        assert restore(client, path, replace=True)["users"] == 1

    def test_a_scan_deleted_after_the_backup_does_not_come_back(self, client, tmp_path):
        headers, _, scan_id = populate(client)
        path = make_backup(client, tmp_path)
        client.delete(f"/api/v1/scan/{scan_id}", headers=headers)
        restore(client, path, replace=True)
        assert client.get(f"/api/v1/scan/{scan_id}", headers=headers).status_code == 404
        assert count(client, "resume_scans") == 0

    def test_organisation_data_erased_after_the_backup_stays_erased(self, client, tmp_path):
        headers, body, _ = populate(client)
        path = make_backup(client, tmp_path)
        client.post("/api/v1/orgs/current/erase-data", headers=headers, json={"organization_name": "Acme Hiring"})
        restore(client, path, replace=True)
        assert count(client, "resume_scans") == 0 and count(client, "usage_records") == 0
        assert count(client, "users") == 1  # accounts are not erased by this

    def test_scans_made_after_an_erasure_are_new_data_not_erased(self, client, tmp_path):
        headers, _, _ = populate(client)
        client.post("/api/v1/orgs/current/erase-data", headers=headers, json={"organization_name": "Acme Hiring"})
        later = scan(client, headers).json()["id"]
        path = make_backup(client, tmp_path)  # taken after both
        restore(client, path, replace=True)
        assert client.get(f"/api/v1/scan/{later}", headers=headers).status_code == 200

    def test_a_deleted_account_and_its_organisation_do_not_come_back(self, client, tmp_path):
        headers, body, scan_id = populate(client)
        path = make_backup(client, tmp_path)
        client.post("/api/v1/auth/delete-account", headers=headers, json={"password": PASSWORD})
        restore(client, path, replace=True)
        for name in ("users", "organizations", "memberships", "resume_scans", "usage_records"):
            assert count(client, name) == 0, name
        assert client.post("/api/v1/auth/login", json={"email": "owner@example.com", "password": PASSWORD}).status_code == 401

    def test_erasures_from_before_the_backup_are_also_reapplied(self, client, tmp_path):
        headers, _, scan_id = populate(client)
        client.delete(f"/api/v1/scan/{scan_id}", headers=headers)
        other = scan(client, headers).json()["id"]
        path = make_backup(client, tmp_path)
        restore(client, path, replace=True)
        assert count(client, "resume_scans") == 1 and count(client, "resume_scans", {"id": other}) == 1

    def test_tombstones_supplied_by_the_caller_are_applied(self, client, tmp_path):
        headers, _, scan_id = populate(client)
        path = make_backup(client, tmp_path)
        extra = [{"kind": "scan", "id": scan_id, "org_id": "x", "erased_at": datetime.now(timezone.utc)}]
        restore(client, path, replace=True, extra_tombstones=extra)
        assert count(client, "resume_scans") == 0

    def test_a_restore_does_not_duplicate_tombstones(self, client, tmp_path):
        headers, _, scan_id = populate(client)
        client.delete(f"/api/v1/scan/{scan_id}", headers=headers)
        path = make_backup(client, tmp_path)
        restore(client, path, replace=True)
        restore(client, path, replace=True)
        assert count(client, "erasure_tombstones") == 1

    def test_a_wrong_key_changes_nothing(self, client, tmp_path):
        populate(client)
        path = make_backup(client, tmp_path, KEY)
        with pytest.raises(backup.BackupError):
            restore(client, path, Fernet.generate_key().decode(), replace=True)
        assert count(client, "users") == 1  # the live data was not touched


class TestScheduling:
    def test_backups_run_on_a_schedule_when_enabled(self, client, tmp_path, monkeypatch):
        import asyncio
        populate(client)
        monkeypatch.setenv("BACKUP_DIR", str(tmp_path))
        monkeypatch.setenv("BACKUP_ENCRYPTION_KEY", KEY)

        async def run():
            task = asyncio.create_task(backup.backup_loop(lambda: database_module.database.db, 1))
            await asyncio.sleep(0.2)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        client.portal.call(run)
        assert len(backup.list_backups(tmp_path)) == 1
