"""E2E drill: WAL-safe backup/restore against a **live** gateway database.

Issue: #186 (data-integrity follow-up on PR #244)

Runs inside the ``backup-restore-drill`` compose service, alongside the
running ``iot-gateway`` container and sharing its data volume
(``e2e-gw-data`` → ``/app/data``).

Evidence level: **L2 simulation** (mock MQTT stack, no physical hardware).

What this drill proves
----------------------
A. Backup of the *live* gateway database (gateway container running) via the
   SQLite online backup API yields a valid, self-contained snapshot that
   contains the events the gateway has ingested.
B. Backup of a database with an **active WAL** and an in-flight (uncommitted)
   write is consistent: committed rows are captured, the uncommitted row is
   not.
C. A corrupt backup is rejected and the live database is left untouched.
D. Restore without the explicit offline attestation is refused — the tool
   never claims to stop a deployed gateway.
E. A failure after the atomic swap triggers rollback: the pre-restore live
   snapshot is restored and retained.
F. An interrupted restore leaves a journal that a deterministic recovery step
   resolves.
G. The restored database reopens and answers queries (restart/open
   validation).

The drill never mutates the live gateway database: every restore is executed
against a scratch copy. Only the backup in (A) touches the live file, and it
only reads it.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import sqlite3
import sys
import time
from pathlib import Path
from urllib.request import urlopen
from urllib.error import URLError

import pytest

sys.path.insert(0, "/app/iot-gateway/src")

from iot_gateway.migrations import backup_restore  # noqa: E402
from iot_gateway.migrations.backup_restore import (  # noqa: E402
    RestoreSafetyError,
    backup_database,
    recover_interrupted_restore,
    restore_database,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)-8s  %(message)s")
log = logging.getLogger("backup-restore-drill")

LIVE_DB = Path(os.environ.get("GATEWAY_DB_PATH", "/app/data/gateway.db"))
GW_HTTP_PORT = os.environ.get("GW_HTTP_PORT", "8001")
GW_BASE = f"http://iot-gateway:{GW_HTTP_PORT}"
SCRATCH = Path(os.environ.get("DRILL_SCRATCH_DIR", "/tmp/backup-restore-drill"))


# ── Helpers ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _clean_scratch():
    """Start every test from an empty scratch directory.

    The drill runs inside a container whose writable layer survives between
    runs. Artefacts left behind by an earlier run (for example a pre-existing
    ``source-e.bak``) would otherwise leak into the next run and fail a test
    for a reason unrelated to the behaviour under test.
    """
    shutil.rmtree(SCRATCH, ignore_errors=True)
    SCRATCH.mkdir(parents=True, exist_ok=True)
    yield


def wait_for_gateway_events(min_count: int = 1, timeout: int = 60) -> int:
    """Wait until the live gateway has ingested at least ``min_count`` events."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urlopen(f"{GW_BASE}/events?limit=100", timeout=5) as resp:
                if resp.status == 200:
                    payload = json.loads(resp.read())
                    events = payload.get("events", []) if isinstance(payload, dict) else payload
                    if isinstance(events, list) and len(events) >= min_count:
                        return len(events)
        except (URLError, OSError, json.JSONDecodeError):
            pass
        time.sleep(2)
    return 0


def _count_events(path: Path) -> int:
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        return conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    finally:
        conn.close()


def _snapshot_live_db(target: Path) -> Path:
    """Copy the live gateway database into ``target`` as a consistent snapshot.

    The live database runs in WAL mode, so a plain file copy of the main
    database file is **not** a copy of the database: committed rows may still
    live only in the ``-wal`` sidecar. Copying the main file alone therefore
    yields a database without the ``events`` table (or with stale contents)
    whenever the gateway has not checkpointed since it started.

    The SQLite online backup API reads the database *and* its WAL atomically
    and produces a single self-contained file, which is exactly what the
    scratch copies in this drill require.
    """
    if target.exists():
        target.unlink()
    for suffix in ("-wal", "-shm"):
        Path(f"{target}{suffix}").unlink(missing_ok=True)
    backup_database(LIVE_DB, target)
    return target


def _scratch(name: str) -> Path:
    SCRATCH.mkdir(parents=True, exist_ok=True)
    return SCRATCH / name


# ── A: backup of the live gateway database ───────────────────────────────────

def test_a_backup_of_live_gateway_database_is_valid_and_complete():
    """A. Backup the running gateway's database while it is live."""
    assert LIVE_DB.is_file(), f"live gateway database not found: {LIVE_DB}"

    ingested = wait_for_gateway_events(min_count=1, timeout=60)
    assert ingested >= 1, "gateway did not ingest any event — drill cannot proceed"
    log.info("gateway has %d ingested events", ingested)

    backup = backup_database(LIVE_DB)

    assert backup.is_file()
    assert backup.stat().st_size > 0
    # Self-contained: no sidecar required to read it back.
    assert not Path(f"{backup}-wal").exists()
    assert not Path(f"{backup}-shm").exists()

    backed_up = _count_events(backup)
    assert backed_up >= 1, "backup contains no events"
    # The gateway keeps ingesting while the backup runs, so the snapshot may
    # legitimately contain more events than the sampled API count. It must
    # never contain fewer than what the API already reported.
    assert backed_up >= ingested, (
        f"backup holds {backed_up} events but the gateway already reported "
        f"{ingested} — the snapshot is not a consistent superset"
    )
    log.info("live backup %s contains %d events", backup.name, backed_up)

    # The backup must be a valid SQLite database that opens cleanly.
    assert backup_restore.cmd_verify(str(backup)) == 0


# ── B: active WAL consistency ────────────────────────────────────────────────

def test_b_backup_with_active_wal_and_inflight_write_is_consistent():
    """B. The online backup API captures committed WAL frames only."""
    wal_db = _scratch("wal-live.db")
    for suffix in ("", "-wal", "-shm"):
        Path(f"{wal_db}{suffix}").unlink(missing_ok=True)

    writer = sqlite3.connect(wal_db, isolation_level=None)
    try:
        writer.execute("PRAGMA journal_mode=WAL")
        writer.execute("PRAGMA wal_autocheckpoint=0")
        writer.execute("CREATE TABLE records (value TEXT NOT NULL)")
        writer.execute("INSERT INTO records(value) VALUES ('committed-1')")
        writer.execute("INSERT INTO records(value) VALUES ('committed-2')")
        writer.execute("BEGIN")
        writer.execute("INSERT INTO records(value) VALUES ('uncommitted')")

        wal_file = Path(f"{wal_db}-wal")
        assert wal_file.exists() and wal_file.stat().st_size > 0, "WAL is not active"

        backup = backup_database(wal_db)
    finally:
        writer.close()

    conn = sqlite3.connect(f"file:{backup}?mode=ro", uri=True)
    try:
        values = [row[0] for row in conn.execute("SELECT value FROM records ORDER BY rowid")]
    finally:
        conn.close()

    assert values == ["committed-1", "committed-2"], f"unexpected snapshot: {values}"
    log.info("active-WAL backup captured %d committed rows", len(values))


# ── C: corrupt backup rejection ──────────────────────────────────────────────

def test_c_corrupt_backup_is_rejected_and_live_db_untouched():
    """C. A corrupt source is refused before anything is replaced."""
    live_copy = _scratch("live-copy.db")
    _snapshot_live_db(live_copy)
    before = _count_events(live_copy)

    corrupt = _scratch("corrupt.bak")
    corrupt.write_bytes(b"definitely not a sqlite database")

    with pytest.raises(RestoreSafetyError, match="integrity"):
        restore_database(live_copy, corrupt, offline=True)

    assert _count_events(live_copy) == before
    assert not list(SCRATCH.glob("*.restore-*.tmp"))
    log.info("corrupt backup rejected, live copy untouched")


# ── D: offline attestation ────────────────────────────────────────────────────

def test_d_restore_without_offline_attestation_is_refused():
    """D. The tool never implies it stopped the deployed gateway."""
    live_copy = _scratch("live-copy-d.db")
    _snapshot_live_db(live_copy)
    before = _count_events(live_copy)

    backup = backup_database(live_copy)

    with pytest.raises(RestoreSafetyError, match="--offline"):
        restore_database(live_copy, backup, offline=False)

    assert _count_events(live_copy) == before
    log.info("restore without --offline refused; live copy untouched")


# ── E: rollback on failure after the swap ─────────────────────────────────────

def test_e_failure_after_swap_rolls_back_to_retained_snapshot(monkeypatch):
    """E. A post-swap failure restores the retained pre-restore snapshot."""
    live_copy = _scratch("live-copy-e.db")
    _snapshot_live_db(live_copy)
    before = _count_events(live_copy)

    source = _scratch("source-e.bak")
    conn = sqlite3.connect(source)
    try:
        conn.execute("CREATE TABLE events (event_id TEXT PRIMARY KEY)")
        conn.execute("CREATE TABLE gateway_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        conn.commit()
    finally:
        conn.close()

    def boom(_path):
        raise sqlite3.DatabaseError("restored database cannot be reopened")

    monkeypatch.setattr(backup_restore, "_reopen_check", boom)

    with pytest.raises(sqlite3.DatabaseError, match="reopen"):
        restore_database(live_copy, source, offline=True)

    assert _count_events(live_copy) == before, "live data was not rolled back"
    retained = list(SCRATCH.glob("live-copy-e.db.pre-restore.*.bak"))
    assert len(retained) == 1, "pre-restore snapshot must be retained"
    assert _count_events(retained[0]) == before
    log.info("rollback restored %d events; snapshot retained", before)


# ── F: interrupted restore recovery ───────────────────────────────────────────

def test_f_interrupted_restore_is_deterministically_recoverable(monkeypatch):
    """F. A killed restore leaves a journal; recovery resolves it."""
    live_copy = _scratch("live-copy-f.db")
    _snapshot_live_db(live_copy)
    before = _count_events(live_copy)

    source = _scratch("source-f.bak")
    shutil.copyfile(live_copy, source)

    def interrupted(_path):
        raise KeyboardInterrupt("simulated SIGKILL after the swap")

    monkeypatch.setattr(backup_restore, "_reopen_check", interrupted)

    with pytest.raises(KeyboardInterrupt):
        restore_database(live_copy, source, offline=True)

    journal = live_copy.parent / f".{live_copy.name}.restore-journal.json"
    assert journal.is_file(), "interrupted restore must leave a journal"

    outcome = recover_interrupted_restore(live_copy)
    assert outcome is not None
    assert outcome.action in {"completed", "aborted", "rolled_back"}
    assert _count_events(live_copy) == before
    log.info("interrupted restore recovered with action=%s", outcome.action)


# ── H: WAL-safe snapshot of the live database ─────────────────────────────────

def test_h_snapshot_of_live_database_is_wal_safe():
    """H. The live-database copy used by this drill is WAL-safe.

    Regression guard: the live gateway database runs in WAL mode, so a plain
    file copy of the main database file is not a copy of the database. When
    the gateway has not checkpointed (which is the normal case for a freshly
    started gateway), the copy has no ``events`` table at all and the drill
    fails with "no such table: events".

    This test proves the snapshot helper reads the database *and* its WAL.
    """
    hot = _scratch("hot-wal.db")
    for suffix in ("", "-wal", "-shm"):
        Path(f"{hot}{suffix}").unlink(missing_ok=True)

    writer = sqlite3.connect(hot, isolation_level=None)
    try:
        writer.execute("PRAGMA journal_mode=WAL")
        writer.execute("PRAGMA wal_autocheckpoint=0")
        writer.execute("CREATE TABLE events (event_id TEXT PRIMARY KEY)")
        writer.execute("INSERT INTO events(event_id) VALUES ('e1')")
        writer.execute("INSERT INTO events(event_id) VALUES ('e2')")
        # The WAL stays hot: no checkpoint, connection still open, exactly like
        # a gateway that is running and ingesting events.
        assert Path(f"{hot}-wal").exists(), "WAL is not active"

        snapshot = _scratch("hot-wal-snapshot.db")
        backup_database(hot, snapshot)
        assert _count_events(snapshot) == 2, "snapshot lost committed WAL rows"
    finally:
        writer.close()

    log.info("WAL-safe snapshot preserved committed rows from a hot WAL")


# ── G: restart / open validation of the restored database ─────────────────────

def test_g_restored_database_reopens_and_answers_queries():
    """G. The restored file opens cleanly and serves queries (restart check)."""
    live_copy = _scratch("live-copy-g.db")
    _snapshot_live_db(live_copy)
    before = _count_events(live_copy)

    backup = backup_database(live_copy)
    restore_database(live_copy, backup, offline=True)

    conn = sqlite3.connect(f"file:{live_copy}?mode=rw", uri=True)
    try:
        assert conn.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
        assert conn.execute("SELECT COUNT(*) FROM events").fetchone()[0] == before
    finally:
        conn.close()

    # Also open it through the gateway's own EventStore (same code path a
    # restarted gateway uses).
    import asyncio

    from iot_gateway.event_store import EventStore

    async def _open_with_event_store() -> int:
        store = EventStore(database_url=f"sqlite+aiosqlite:///{live_copy}", max_events=10000)
        await store.init()
        try:
            # query() defaults to limit=100, so request the full count.
            events = await store.query(limit=max(before, 1))
            return len(events)
        finally:
            await store.close()

    reopened = asyncio.run(_open_with_event_store())
    assert reopened == before, (
        f"EventStore reopened the restored database and saw {reopened} events, "
        f"expected {before}"
    )
    log.info("restored database reopened via EventStore with %d events", reopened)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
