"""Deterministic regression tests for WAL-safe SQLite backup/restore.

Issue: #186 (data-integrity follow-up on PR #244)

Coverage map (reviewer requirements):

* ``test_backup_of_live_wal_database_is_consistent``  — online backup API with
  an active WAL and in-flight writes.
* ``test_backup_snapshot_is_self_contained``           — the backup needs no
  sidecar files to be reopened.
* ``test_backup_rejects_missing_database``             — failure, no artefact.
* ``test_restore_rejects_corrupt_backup``              — corrupt input is
  rejected and the live database is untouched.
* ``test_restore_requires_explicit_offline_attestation`` — the tool never
  claims to stop a deployed gateway.
* ``test_restore_rejects_database_in_use``             — quiescence gate.
* ``test_restore_retains_pre_restore_snapshot``        — rollback artefact.
* ``test_restore_rolls_back_when_post_swap_validation_fails`` — failure during
  restore preserves the live data.
* ``test_restore_interrupted_before_swap_leaves_live_db_untouched`` — simulated
  kill before the swap.
* ``test_restore_interrupted_after_swap_is_recoverable`` — simulated kill after
  the swap; the journal lets an operator recover deterministically.
* ``test_recover_interrupted_restore_rolls_back_corrupted_live_db``
* ``test_restored_database_reopens_and_serves_queries`` — restart/open
  validation.
* ``test_cli_restore_requires_offline_flag``            — CLI surface.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pytest

from iot_gateway.migrations import backup_restore
from iot_gateway.migrations.backup_restore import (
    RestoreSafetyError,
    backup_database,
    recover_interrupted_restore,
    restore_database,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_db(path: Path, values: list[str], *, wal: bool = False) -> None:
    """Create a DB with a ``records`` table holding ``values``."""
    conn = sqlite3.connect(path)
    try:
        if wal:
            conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("CREATE TABLE records (value TEXT NOT NULL)")
        conn.executemany("INSERT INTO records(value) VALUES (?)", [(v,) for v in values])
        conn.commit()
    finally:
        conn.close()


def _values(path: Path) -> list[str]:
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        return [row[0] for row in conn.execute("SELECT value FROM records ORDER BY rowid")]
    finally:
        conn.close()


def _count(path: Path) -> int:
    return len(_values(path))


# ---------------------------------------------------------------------------
# Backup
# ---------------------------------------------------------------------------


def test_backup_of_live_wal_database_is_consistent(tmp_path):
    """Online backup API captures committed WAL frames, not just the main file.

    A writer keeps the WAL open with autocheckpoint disabled and an extra
    uncommitted transaction in flight. The backup must contain every
    *committed* row and must not contain the uncommitted one.
    """
    db_path = tmp_path / "gateway.db"
    writer = sqlite3.connect(db_path, isolation_level=None)
    try:
        writer.execute("PRAGMA journal_mode=WAL")
        writer.execute("PRAGMA wal_autocheckpoint=0")
        writer.execute("CREATE TABLE records (value TEXT NOT NULL)")
        writer.execute("INSERT INTO records(value) VALUES ('committed-1')")
        writer.execute("INSERT INTO records(value) VALUES ('committed-2')")
        # Uncommitted transaction: must not appear in the snapshot.
        writer.execute("BEGIN")
        writer.execute("INSERT INTO records(value) VALUES ('uncommitted')")

        wal_path = Path(f"{db_path}-wal")
        assert wal_path.exists(), "WAL file must exist for this scenario"
        assert wal_path.stat().st_size > 0, "WAL must hold committed frames"

        backup = backup_database(db_path)
    finally:
        writer.close()

    assert backup.is_file()
    assert _values(backup) == ["committed-1", "committed-2"]


def test_backup_snapshot_is_self_contained(tmp_path):
    """The backup opens standalone: no -wal/-shm sidecar is required."""
    db_path = tmp_path / "gateway.db"
    _make_db(db_path, ["a", "b", "c"], wal=True)

    backup = backup_database(db_path)

    isolated = tmp_path / "isolated.db"
    isolated.write_bytes(backup.read_bytes())
    assert _values(isolated) == ["a", "b", "c"]
    assert not Path(f"{isolated}-wal").exists()
    assert not Path(f"{isolated}-shm").exists()


def test_backup_rejects_missing_database(tmp_path):
    """A missing database produces an error, not a bogus artefact."""
    with pytest.raises(FileNotFoundError):
        backup_database(tmp_path / "does-not-exist.db")
    assert not list(tmp_path.glob("*.bak"))


def test_backup_verification_rejects_corrupted_file(tmp_path):
    """``--verify`` semantics: a corrupted backup is reported as invalid."""
    db_path = tmp_path / "gateway.db"
    _make_db(db_path, ["x"])
    backup = backup_database(db_path)
    with backup.open("r+b") as handle:
        handle.seek(0)
        handle.write(b"CORRUPTED SQLITE!")
    assert backup_restore.cmd_verify(str(backup)) == 1


# ---------------------------------------------------------------------------
# Restore — preconditions
# ---------------------------------------------------------------------------


def test_restore_rejects_corrupt_backup_and_preserves_live_db(tmp_path):
    """A corrupt input is rejected before anything is modified."""
    db_path = tmp_path / "gateway.db"
    _make_db(db_path, ["live"])
    corrupt = tmp_path / "bad.bak"
    corrupt.write_bytes(b"not a sqlite database")

    with pytest.raises(RestoreSafetyError, match="integrity"):
        restore_database(db_path, corrupt, offline=True)

    assert _values(db_path) == ["live"]
    assert not list(tmp_path.glob("*.restore-*.tmp"))


def test_restore_requires_explicit_offline_attestation(tmp_path):
    """The tool never implies that it stopped the deployed gateway."""
    db_path = tmp_path / "gateway.db"
    _make_db(db_path, ["live"])
    backup = backup_database(db_path)

    with pytest.raises(RestoreSafetyError, match="--offline"):
        restore_database(db_path, backup, offline=False)

    assert _values(db_path) == ["live"]


def test_restore_rejects_database_in_use(tmp_path):
    """The quiescence gate refuses to restore while another process writes."""
    db_path = tmp_path / "gateway.db"
    _make_db(db_path, ["live"], wal=True)
    backup = backup_database(db_path)

    holder = sqlite3.connect(db_path, isolation_level=None, timeout=0.0)
    try:
        holder.execute("PRAGMA journal_mode=WAL")
        holder.execute("BEGIN EXCLUSIVE")
        holder.execute("INSERT INTO records(value) VALUES ('in-flight')")
        with pytest.raises(RestoreSafetyError, match="not quiescent"):
            restore_database(db_path, backup, offline=True)
        holder.execute("ROLLBACK")
    finally:
        holder.close()

    assert "live" in _values(db_path)
    assert not list(tmp_path.glob("*.restore-*.tmp"))


# ---------------------------------------------------------------------------
# Restore — happy path and rollback
# ---------------------------------------------------------------------------


def test_restore_retains_pre_restore_snapshot(tmp_path):
    """The live database is snapshotted before replacement and kept on disk."""
    db_path = tmp_path / "gateway.db"
    _make_db(db_path, ["old-live"])
    source = tmp_path / "source.bak"
    _make_db(source, ["new-1", "new-2"])

    outcome = restore_database(db_path, source, offline=True)

    assert outcome.pre_restore is not None
    assert outcome.pre_restore.is_file()
    assert _values(outcome.pre_restore) == ["old-live"]
    assert _values(db_path) == ["new-1", "new-2"]


def test_restore_rolls_back_when_post_swap_validation_fails(tmp_path, monkeypatch):
    """A failure after the swap restores the retained live snapshot."""
    db_path = tmp_path / "gateway.db"
    _make_db(db_path, ["live-before-restore"])
    source = tmp_path / "source.bak"
    _make_db(source, ["candidate"])

    def boom(_path):
        raise sqlite3.DatabaseError("restored database cannot be reopened")

    monkeypatch.setattr(backup_restore, "_reopen_check", boom)

    with pytest.raises(sqlite3.DatabaseError, match="reopen"):
        restore_database(db_path, source, offline=True)

    assert _values(db_path) == ["live-before-restore"]
    retained = list(tmp_path.glob("gateway.db.pre-restore.*.bak"))
    assert len(retained) == 1, "pre-restore snapshot must be retained"
    assert _values(retained[0]) == ["live-before-restore"]
    assert not list(tmp_path.glob("*.restore-*.tmp"))


def test_restore_interrupted_before_swap_leaves_live_db_untouched(tmp_path, monkeypatch):
    """A kill before the atomic swap leaves the live database unchanged."""
    db_path = tmp_path / "gateway.db"
    _make_db(db_path, ["live"])
    source = tmp_path / "source.bak"
    _make_db(source, ["candidate"])

    def interrupted(_src, _dst):
        raise KeyboardInterrupt("simulated SIGKILL before the swap")

    monkeypatch.setattr(backup_restore, "_atomic_replace", interrupted)

    with pytest.raises(KeyboardInterrupt):
        restore_database(db_path, source, offline=True)

    assert _values(db_path) == ["live"]
    assert not list(tmp_path.glob("*.restore-*.tmp"))


def test_restore_interrupted_after_swap_is_recoverable(tmp_path, monkeypatch):
    """A kill after the swap leaves a journal; recovery is deterministic."""
    db_path = tmp_path / "gateway.db"
    _make_db(db_path, ["live"])
    source = tmp_path / "source.bak"
    _make_db(source, ["candidate", "candidate-2"])

    def interrupted(_path):
        raise KeyboardInterrupt("simulated SIGKILL after the swap")

    monkeypatch.setattr(backup_restore, "_reopen_check", interrupted)

    with pytest.raises(KeyboardInterrupt):
        restore_database(db_path, source, offline=True)

    journal = db_path.parent / f".{db_path.name}.restore-journal.json"
    assert journal.is_file(), "an interrupted restore must leave a journal"

    outcome = recover_interrupted_restore(db_path)
    assert outcome is not None
    assert outcome.action == "completed"
    assert _values(db_path) == ["candidate", "candidate-2"]
    assert not journal.exists()


def test_recover_interrupted_restore_rolls_back_corrupted_live_db(tmp_path, monkeypatch):
    """If the swapped file is unusable, recovery restores the retained snapshot."""
    db_path = tmp_path / "gateway.db"
    _make_db(db_path, ["live"])
    source = tmp_path / "source.bak"
    _make_db(source, ["candidate"])

    def interrupted(_path):
        raise KeyboardInterrupt("simulated SIGKILL after the swap")

    monkeypatch.setattr(backup_restore, "_reopen_check", interrupted)

    with pytest.raises(KeyboardInterrupt):
        restore_database(db_path, source, offline=True)

    # Simulate a torn write on the swapped file.
    db_path.write_bytes(b"torn-file")

    outcome = recover_interrupted_restore(db_path)
    assert outcome is not None
    assert outcome.action == "rolled_back"
    assert _values(db_path) == ["live"]


def test_recover_interrupted_restore_returns_none_without_journal(tmp_path):
    db_path = tmp_path / "gateway.db"
    _make_db(db_path, ["live"])
    assert recover_interrupted_restore(db_path) is None


# ---------------------------------------------------------------------------
# Restart / open validation
# ---------------------------------------------------------------------------


def test_restored_database_reopens_and_serves_queries(tmp_path):
    """After a restore the database opens cleanly and returns the data."""
    db_path = tmp_path / "gateway.db"
    _make_db(db_path, ["old"])
    source = tmp_path / "source.bak"
    _make_db(source, ["fresh-a", "fresh-b"])

    restore_database(db_path, source, offline=True)

    # Reopen exactly like a restarted gateway would.
    conn = sqlite3.connect(f"file:{db_path}?mode=rw", uri=True)
    try:
        assert conn.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
        assert conn.execute("SELECT COUNT(*) FROM records").fetchone()[0] == 2
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_restored_database_is_usable_by_the_event_store(tmp_path):
    """The restored file is a valid gateway database (EventStore can open it)."""
    from iot_gateway.event_store import EventStore
    from iot_gateway.models import CanonicalEvent, EventType
    import time
    import uuid

    db_path = tmp_path / "gateway.db"
    store = EventStore(database_url=f"sqlite+aiosqlite:///{db_path}", max_events=100)
    await store.init()
    event = CanonicalEvent(
        event_id=str(uuid.uuid4()),
        device_id="dev-1",
        event_type=EventType.TELEMETRY,
        payload={"v": 1},
        mqtt_topic="sf/dev-1/t",
        mqtt_timestamp_ms=int(time.time() * 1000),
        ingested_at="2026-01-01T00:00:00+00:00",
        sequence=0,
    )
    await store.insert(event)
    await store.close()

    backup = backup_database(db_path)
    # Wipe the live database.
    for suffix in ("", "-wal", "-shm"):
        Path(f"{db_path}{suffix}").unlink(missing_ok=True)
    _make_db(db_path, ["placeholder"])

    restore_database(db_path, backup, offline=True)

    restored = EventStore(database_url=f"sqlite+aiosqlite:///{db_path}", max_events=100)
    await restored.init()
    events = await restored.query()
    await restored.close()
    assert len(events) == 1
    assert events[0]["device_id"] == "dev-1"


# ---------------------------------------------------------------------------
# CLI surface
# ---------------------------------------------------------------------------


def test_cli_restore_requires_offline_flag(tmp_path, capsys):
    """The CLI refuses a restore without the offline attestation."""
    db_path = tmp_path / "gateway.db"
    _make_db(db_path, ["live"])
    backup = backup_database(db_path)

    exit_code = backup_restore.cmd_restore(str(db_path), str(backup), confirm=True, offline=False)
    assert exit_code == 1
    assert "--offline" in capsys.readouterr().err
    assert _values(db_path) == ["live"]


def test_cli_backup_and_list_roundtrip(tmp_path, capsys):
    db_path = tmp_path / "gateway.db"
    _make_db(db_path, ["live"])
    assert backup_restore.cmd_backup(str(db_path)) == 0
    assert backup_restore.cmd_list(str(db_path)) == 0
    assert "gateway.db." in capsys.readouterr().out
