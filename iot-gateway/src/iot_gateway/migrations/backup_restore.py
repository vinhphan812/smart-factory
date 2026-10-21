"""Safe SQLite backup, restore, and integrity-check CLI for the IoT gateway.

Usage:
    python -m iot_gateway.migrations.backup_restore --backup [--db PATH]
    python -m iot_gateway.migrations.backup_restore --restore --backup-path PATH \
        --confirm --offline [--db PATH]
    python -m iot_gateway.migrations.backup_restore --list [--db PATH]
    python -m iot_gateway.migrations.backup_restore --verify --backup-path PATH

Backup
------
Uses SQLite's *online backup API* (``sqlite3.Connection.backup``). The backup is
a transactionally consistent snapshot of the database even when the database is
in WAL mode and other connections are committing concurrently. A plain file
copy of a live database is never used.

Restore
-------
Restore is an **offline, operator-driven** procedure:

1. The operator must attest ``--offline``: every gateway process that touches
   the database has been stopped. This tool never stops a process. It only
   *verifies* that it can obtain an exclusive lock (and, in WAL mode, that a
   checkpoint can complete) at swap time, and it refuses to continue when it
   cannot.
2. The source backup is integrity-verified **before** anything is modified.
3. A pre-restore snapshot of the live database is taken with the online backup
   API and **retained** next to the database as
   ``<db>.pre-restore.<timestamp>.bak``.
4. The replacement is staged in the same directory as the target and moved into
   place with :func:`os.replace` (atomic within a filesystem).
5. The restored file is reopened and integrity-checked. If that validation
   fails, the retained pre-restore snapshot is moved back into place
   (rollback), and the rollback itself is validated.
6. A restore journal records every phase so that a restore interrupted by a
   crash or a kill can be detected and recovered explicitly with
   :func:`recover_interrupted_restore`.

Nothing in this module deletes the live database or the retained snapshot.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import shutil
import sqlite3
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

BACKUP_SUFFIX = ".bak"
JOURNAL_SUFFIX = ".restore-journal.json"


class RestoreSafetyError(RuntimeError):
    """The restore precondition could not be established or was violated."""


@dataclass
class RestoreOutcome:
    """Result of a successful restore."""

    db_path: Path
    restored_from: Path
    pre_restore: Path | None
    staged_path: Path | None = None
    journal_path: Path | None = None


@dataclass
class RecoveryOutcome:
    """Result of inspecting/recovering an interrupted restore."""

    db_path: Path
    action: str
    detail: str
    pre_restore: Path | None = None


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------


def _db_path(value: str | None) -> Path:
    """Resolve the live database path from a CLI argument or the default."""
    return Path(value).resolve() if value else Path("gateway.db").resolve()


def _backup_path_for(db_path: Path, label: str = "") -> Path:
    """Build a timestamped backup path next to the live database."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    tag = f".{label}" if label else ""
    return db_path.parent / f"{db_path.name}{tag}.{stamp}{BACKUP_SUFFIX}"


def _journal_path_for(db_path: Path) -> Path:
    """Restore journal path (hidden, next to the live database)."""
    return db_path.parent / f".{db_path.name}{JOURNAL_SUFFIX}"


def _find_backups(db_path: Path) -> list[Path]:
    """List backups that share the database stem, newest first."""
    return sorted(
        db_path.parent.glob(f"{db_path.name}.*{BACKUP_SUFFIX}"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )


def _sidecars(db_path: Path) -> tuple[Path, Path]:
    return Path(f"{db_path}-wal"), Path(f"{db_path}-shm")


def _remove_sidecars(db_path: Path) -> None:
    """Remove the -wal/-shm sidecars of a database.

    Only ever called after the WAL has been checkpointed (or after the database
    has been replaced by an atomic rename), so no committed data is lost.
    """
    for sidecar in _sidecars(db_path):
        with contextlib.suppress(OSError):
            sidecar.unlink()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


# ---------------------------------------------------------------------------
# Core SQLite operations
# ---------------------------------------------------------------------------


def _connect_source(path: Path) -> sqlite3.Connection:
    """Open a database for reading, allowing WAL recovery when possible.

    Read-write is preferred because a read-only connection cannot recover a
    hot WAL left behind by a crash. Read-only is used as a fallback.
    """
    try:
        return sqlite3.connect(f"file:{path}?mode=rw", uri=True)
    except sqlite3.Error:
        return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def _sqlite_backup(source: Path, destination: Path) -> None:
    """Write a consistent snapshot of ``source`` into ``destination``.

    Uses SQLite's online backup API, which is safe against a live database in
    WAL mode with concurrent writers.

    The destination is normalised to rollback-journal (DELETE) mode so the
    resulting artefact is a **single self-contained file**: no ``-wal``/``-shm``
    sidecar is needed to read it back. A backup produced from a WAL database
    would otherwise inherit the WAL header flag and require a sidecar.
    """
    src: sqlite3.Connection | None = None
    dst: sqlite3.Connection | None = None
    try:
        src = _connect_source(source)
        dst = sqlite3.connect(destination)
        src.backup(dst)
        dst.commit()
        # Normalise away any WAL mode inherited from the source header.
        dst.execute("PRAGMA journal_mode=DELETE")
        dst.commit()
    finally:
        if dst is not None:
            with contextlib.suppress(sqlite3.Error):
                dst.close()
        if src is not None:
            with contextlib.suppress(sqlite3.Error):
                src.close()


def _verify_database(path: Path) -> bool:
    """Return True when ``path`` is a readable, structurally sound SQLite DB."""
    if not path.is_file():
        return False
    conn: sqlite3.Connection | None = None
    try:
        conn = sqlite3.connect(f"file:{path}?mode=rw", uri=True)
        result = conn.execute("PRAGMA integrity_check").fetchall()
        return result == [("ok",)]
    except (sqlite3.Error, OSError):
        return False
    finally:
        if conn is not None:
            with contextlib.suppress(sqlite3.Error):
                conn.close()


def _integrity_check(path: Path) -> bool:
    """Backward-compatible alias of :func:`_verify_database`."""
    return _verify_database(path)


def _assert_quiescent(db_path: Path) -> None:
    """Verify the live database is not being written to by another process.

    This does **not** stop any process. It only proves that, at this instant,
    no other connection holds a write lock (and, in WAL mode, that a
    checkpoint can complete). Failure raises :class:`RestoreSafetyError`.
    """
    conn: sqlite3.Connection | None = None
    try:
        conn = sqlite3.connect(db_path, timeout=0.0, isolation_level=None)
        conn.execute("PRAGMA busy_timeout = 0")
        checkpoint = conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
        if checkpoint is not None and checkpoint[0] != 0:
            raise RestoreSafetyError(
                "database is not quiescent: WAL checkpoint could not complete "
                "(another process is reading or writing it)"
            )
        conn.execute("BEGIN EXCLUSIVE")
        conn.execute("ROLLBACK")
    except RestoreSafetyError:
        raise
    except sqlite3.Error as exc:
        raise RestoreSafetyError(
            f"database is not quiescent: {exc}; stop every gateway process "
            "that uses it and retry"
        ) from exc
    finally:
        if conn is not None:
            with contextlib.suppress(sqlite3.Error):
                conn.close()


def _atomic_replace(source: Path, target: Path) -> None:
    """Atomically move ``source`` onto ``target`` (same filesystem)."""
    os.replace(source, target)


def _reopen_check(db_path: Path) -> None:
    """Open the restored database and read from it to prove it is usable."""
    conn: sqlite3.Connection | None = None
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=rw", uri=True)
        conn.execute("SELECT count(*) FROM sqlite_master").fetchone()
    except sqlite3.Error as exc:
        raise sqlite3.DatabaseError(f"restored database cannot be reopened: {exc}") from exc
    finally:
        if conn is not None:
            with contextlib.suppress(sqlite3.Error):
                conn.close()


# ---------------------------------------------------------------------------
# Backup
# ---------------------------------------------------------------------------


def backup_database(db_path: Path, backup_path: Path | None = None) -> Path:
    """Create an integrity-verified online backup of ``db_path``.

    Safe to run against a live database: the online backup API produces a
    consistent snapshot even with an active WAL and in-flight writes.
    """
    db_path = Path(db_path)
    if not db_path.is_file():
        raise FileNotFoundError(f"database not found: {db_path}")
    target = Path(backup_path) if backup_path else _backup_path_for(db_path)
    target.parent.mkdir(parents=True, exist_ok=True)

    staging = target.parent / f".{target.name}.{uuid.uuid4().hex}.partial"
    try:
        _sqlite_backup(db_path, staging)
        if not _verify_database(staging):
            raise sqlite3.DatabaseError("backup snapshot failed integrity verification")
        _atomic_replace(staging, target)
    except BaseException:
        with contextlib.suppress(OSError):
            staging.unlink()
        raise
    return target


# ---------------------------------------------------------------------------
# Restore
# ---------------------------------------------------------------------------


def _write_journal(journal: Path, payload: dict) -> None:
    journal.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _rollback(db_path: Path, pre_restore: Path) -> None:
    """Put the retained pre-restore snapshot back in place and validate it."""
    staging = db_path.parent / f".{db_path.name}.rollback-{uuid.uuid4().hex}.tmp"
    try:
        shutil.copyfile(pre_restore, staging)
        _atomic_replace(staging, db_path)
    except OSError as exc:
        with contextlib.suppress(OSError):
            staging.unlink()
        raise RestoreSafetyError(
            f"restore failed and rollback failed ({exc}); the pre-restore "
            f"snapshot is retained at {pre_restore}"
        ) from exc
    _remove_sidecars(db_path)
    if not _verify_database(db_path):
        raise RestoreSafetyError(
            "restore failed and the rollback snapshot did not validate; the "
            f"pre-restore snapshot is retained at {pre_restore}"
        )


def restore_database(db_path: Path, backup_path: Path, *, offline: bool = False) -> RestoreOutcome:
    """Atomically restore a verified backup over the live database.

    ``offline`` is the operator's attestation that every gateway process
    using the database has been stopped. This function never stops a process.

    On failure after the swap, the retained pre-restore snapshot is restored
    automatically (rollback). A restore interrupted by a kill leaves a journal
    behind; use :func:`recover_interrupted_restore` to inspect and recover it.
    """
    db_path = Path(db_path).resolve()
    backup_path = Path(backup_path).resolve()

    if not offline:
        raise RestoreSafetyError(
            "--offline is required: stop every gateway process that uses "
            f"{db_path} before restoring, then re-run with --offline"
        )
    if not backup_path.is_file():
        raise FileNotFoundError(f"backup not found: {backup_path}")
    live_exists = db_path.is_file()
    if live_exists and db_path.samefile(backup_path):
        raise RestoreSafetyError("the backup path must not be the live database")

    # 1. Verify the source backup before touching anything.
    if not _verify_database(backup_path):
        raise RestoreSafetyError(
            f"backup failed integrity verification: {backup_path}; refusing to restore"
        )

    # 2. Retain a pre-restore snapshot of the live database (online backup API).
    pre_restore: Path | None = None
    if live_exists:
        pre_restore = _backup_path_for(db_path, label="pre-restore")
        _sqlite_backup(db_path, pre_restore)
        if not _verify_database(pre_restore):
            raise RestoreSafetyError(
                f"pre-restore snapshot failed verification: {pre_restore}; aborting"
            )

    # 3. Stage the replacement next to the target (same filesystem => atomic).
    staged = db_path.parent / f".{db_path.name}.restore-{uuid.uuid4().hex}.tmp"
    try:
        _sqlite_backup(backup_path, staged)
        if not _verify_database(staged):
            raise sqlite3.DatabaseError("staged restore file failed verification")
        staged_sha = _sha256(staged)

        journal = _journal_path_for(db_path)
        journal_payload = {
            "db_path": str(db_path),
            "backup_path": str(backup_path),
            "pre_restore": str(pre_restore) if pre_restore else None,
            "staged_sha256": staged_sha,
            "started_at": datetime.now(timezone.utc).isoformat(),
        }
        _write_journal(journal, {**journal_payload, "phase": "preparing"})

        completed = False
        swapped = False
        try:
            # 4. Quiescence gate + WAL checkpoint before replacing anything.
            if live_exists:
                _assert_quiescent(db_path)
                _remove_sidecars(db_path)

            # 5. Atomic swap.
            try:
                _atomic_replace(staged, db_path)
            except PermissionError as exc:
                # On Windows the OS refuses to replace a file that another
                # process still has open. That is a useful extra guard: the
                # live database was not touched.
                raise RestoreSafetyError(
                    f"could not replace the live database ({exc}); another "
                    "process still has it open — stop every gateway process "
                    "using it and retry"
                ) from exc
            swapped = True
            _write_journal(journal, {**journal_payload, "phase": "swapped"})

            # 6. Remove any sidecar resurrected by the previous database.
            _remove_sidecars(db_path)

            # 7. Post-swap validation (integrity + reopen).
            if not _verify_database(db_path):
                raise sqlite3.DatabaseError(
                    "restored database failed integrity validation after the swap"
                )
            _reopen_check(db_path)
            completed = True
        except Exception:
            # The swap did not happen -> the live database is untouched, so the
            # journal is stale and can be dropped.
            if not swapped:
                with contextlib.suppress(OSError):
                    journal.unlink()
            elif pre_restore is not None:
                # The swap happened but the result is not usable -> roll back.
                _rollback(db_path, pre_restore)
                with contextlib.suppress(OSError):
                    journal.unlink()
            raise
        finally:
            if completed:
                with contextlib.suppress(OSError):
                    journal.unlink()
            with contextlib.suppress(OSError):
                staged.unlink()

        return RestoreOutcome(
            db_path=db_path,
            restored_from=backup_path,
            pre_restore=pre_restore,
            staged_path=None,
            journal_path=None,
        )
    except BaseException:
        with contextlib.suppress(OSError):
            staged.unlink()
        raise


# ---------------------------------------------------------------------------
# Interrupted-restore recovery
# ---------------------------------------------------------------------------


def recover_interrupted_restore(db_path: Path) -> RecoveryOutcome | None:
    """Inspect (and repair) a restore that was interrupted by a kill/crash.

    Returns ``None`` when no journal is present. The live database is only
    modified when it cannot be opened as a valid SQLite database.
    """
    db_path = Path(db_path).resolve()
    journal = _journal_path_for(db_path)
    if not journal.is_file():
        return None
    try:
        payload = json.loads(journal.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return RecoveryOutcome(
            db_path=db_path,
            action="manual",
            detail=f"restore journal {journal} is unreadable; inspect it manually",
        )

    pre_restore_raw = payload.get("pre_restore")
    pre_restore = Path(pre_restore_raw) if pre_restore_raw else None
    staged_sha = payload.get("staged_sha256")

    swap_completed = False
    if db_path.is_file() and staged_sha:
        try:
            swap_completed = _sha256(db_path) == staged_sha
        except OSError:
            swap_completed = False

    if swap_completed and _verify_database(db_path):
        with contextlib.suppress(OSError):
            journal.unlink()
        return RecoveryOutcome(
            db_path=db_path,
            action="completed",
            detail="the interrupted restore had already swapped in the new "
            "database and it validates; the journal was cleaned up",
            pre_restore=pre_restore,
        )

    if not swap_completed and db_path.is_file() and _verify_database(db_path):
        with contextlib.suppress(OSError):
            journal.unlink()
        return RecoveryOutcome(
            db_path=db_path,
            action="aborted",
            detail="the interrupted restore never swapped the database; the "
            "live database is unchanged and was validated",
            pre_restore=pre_restore,
        )

    if pre_restore is not None and pre_restore.is_file():
        _rollback(db_path, pre_restore)
        with contextlib.suppress(OSError):
            journal.unlink()
        return RecoveryOutcome(
            db_path=db_path,
            action="rolled_back",
            detail="the live database was unusable; it was restored from the "
            "retained pre-restore snapshot",
            pre_restore=pre_restore,
        )

    return RecoveryOutcome(
        db_path=db_path,
        action="manual",
        detail="the live database is unusable and no pre-restore snapshot is "
        "available; manual recovery is required",
        pre_restore=pre_restore,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def cmd_backup(db_arg: str | None) -> int:
    try:
        created = backup_database(_db_path(db_arg))
    except (sqlite3.Error, OSError) as exc:
        print(f"ERROR: backup failed: {exc}", file=sys.stderr)
        return 1
    print(f"Backup created and verified: {created}")
    return 0


def cmd_restore(db_arg: str | None, backup_path: str, confirm: bool, offline: bool) -> int:
    if not confirm:
        print(
            "ERROR: --confirm is required to restore.\n"
            "This replaces the live database with the selected backup.",
            file=sys.stderr,
        )
        return 1
    try:
        outcome = restore_database(
            _db_path(db_arg), Path(backup_path).resolve(), offline=offline
        )
    except (sqlite3.Error, OSError, RestoreSafetyError) as exc:
        print(f"ERROR: restore rejected or failed: {exc}", file=sys.stderr)
        return 1
    print("Restore completed; the restored database passed integrity and reopen validation.")
    print(f"Restored: {outcome.db_path} <- {outcome.restored_from}")
    if outcome.pre_restore is not None:
        print(f"Retained pre-restore live backup: {outcome.pre_restore}")
    return 0


def cmd_list(db_arg: str | None) -> int:
    db_path = _db_path(db_arg)
    backups = _find_backups(db_path)
    if not backups:
        print(f"No backups found for {db_path.name} in {db_path.parent}.")
        return 0
    print(f"Backups for {db_path.name} in {db_path.parent}:")
    for backup in backups:
        size_kb = backup.stat().st_size // 1024
        mtime = datetime.fromtimestamp(
            backup.stat().st_mtime, tz=timezone.utc
        ).strftime("%Y-%m-%d %H:%M:%S UTC")
        print(f"  {backup.name}  {size_kb} KB  {mtime}")
    return 0


def cmd_verify(backup_path: str) -> int:
    path = Path(backup_path).resolve()
    if path.is_file() and _verify_database(path):
        print(f"PASSED — database is valid: {path}")
        return 0
    print(f"FAILED — database is corrupted, unreadable or missing: {path}", file=sys.stderr)
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="iot-gateway SQLite backup / restore / verify (WAL-safe)."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--backup", action="store_true", help="Create a timestamped backup.")
    group.add_argument("--restore", action="store_true", help="Restore from a backup.")
    group.add_argument("--list", action="store_true", help="List available backups.")
    group.add_argument("--verify", action="store_true", help="Integrity-check a backup.")
    parser.add_argument("--db", default=None, help="Path to the live database (default: gateway.db).")
    parser.add_argument(
        "--backup-path",
        help="Path to the backup file (required with --restore and --verify).",
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Required flag for --restore to prevent accidental data loss.",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Attest that every gateway process using the database is stopped. "
        "Required with --restore. This tool never stops a process itself.",
    )
    args = parser.parse_args()

    if (args.restore or args.verify) and not args.backup_path:
        parser.error("--backup-path is required with --restore and --verify")

    if args.backup:
        return cmd_backup(args.db)
    if args.restore:
        return cmd_restore(args.db, args.backup_path, args.confirm, args.offline)
    if args.list:
        return cmd_list(args.db)
    return cmd_verify(args.backup_path)


if __name__ == "__main__":
    raise SystemExit(main())
