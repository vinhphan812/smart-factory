"""Gateway DB backup, restore and integrity-check CLI.

Usage:
    python -m iot_gateway.migrations.backup_restore --backup [--db PATH]
    python -m iot_gateway.migrations.backup_restore --restore --backup-path PATH --confirm
    python -m iot_gateway.migrations.backup_restore --list
    python -m iot_gateway.migrations.backup_restore --verify --backup-path PATH
"""

from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

BACKUP_SUFFIX = ".bak"


def _db_path(db_arg: str | None) -> Path:
    """Resolve DB path from CLI arg or default."""
    if db_arg:
        return Path(db_arg).resolve()
    return Path("gateway.db").resolve()


def _backup_path_for(db_path: Path) -> Path:
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    return db_path.parent / f"{db_path.name}.{ts}{BACKUP_SUFFIX}"


def _find_backups(db_path: Path) -> list[Path]:
    """List all .bak files that share the DB stem (same name prefix)."""
    stem = db_path.name
    suffix = BACKUP_SUFFIX
    return sorted(
        (p for p in db_path.parent.glob(f"{stem}.*{suffix}")),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )


def _integrity_check(db_path: Path) -> bool:
    """Run SQLite PRAGMA integrity_check on the file.

    Returns True if the database passes all integrity checks, False otherwise.
    """
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except sqlite3.Error:
        return False
    try:
        cur = conn.execute("PRAGMA integrity_check")
        result = cur.fetchone()
        return result is not None and result[0] == "ok"
    finally:
        conn.close()


def cmd_backup(db_arg: str | None) -> int:
    db_path = _db_path(db_arg)
    if not db_path.exists():
        print(f"ERROR: database not found: {db_path}", file=sys.stderr)
        return 1

    bk_path = _backup_path_for(db_path)
    shutil.copy2(db_path, bk_path)
    print(f"Backup created: {bk_path}")
    return 0


def cmd_restore(backup_path_str: str, confirm: bool) -> int:
    backup_path = Path(backup_path_str).resolve()
    if not backup_path.exists():
        print(f"ERROR: backup not found: {backup_path}", file=sys.stderr)
        return 1

    if not confirm:
        print(
            "ERROR: --confirm flag is required to restore.\n"
            "This will overwrite the current database.\n"
            "Run with --confirm to proceed.",
            file=sys.stderr,
        )
        return 1

    if not _integrity_check(backup_path):
        print(f"WARNING: backup failed integrity check: {backup_path}", file=sys.stderr)
        print("Restoring anyway (use --verify first to check).", file=sys.stderr)

    # Restore: the backup path IS the database path (backup is next to the db)
    # So we copy the .bak file over the live .db
    db_path = _db_path(None)
    shutil.copy2(backup_path, db_path)
    print(f"Restored: {db_path} <- {backup_path}")
    return 0


def cmd_list(db_arg: str | None) -> int:
    db_path = _db_path(db_arg)
    backups = _find_backups(db_path)
    if not backups:
        print("No backups found.")
        return 0
    print(f"Backups for {db_path.name} in {db_path.parent}:")
    for bk in backups:
        size_kb = bk.stat().st_size // 1024
        mtime = datetime.fromtimestamp(bk.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        print(f"  {bk.name}  {size_kb} KB  {mtime}")
    return 0


def cmd_verify(backup_path_str: str) -> int:
    backup_path = Path(backup_path_str).resolve()
    if not backup_path.exists():
        print(f"ERROR: backup not found: {backup_path}", file=sys.stderr)
        return 1

    print(f"Integrity check: {backup_path}")
    ok = _integrity_check(backup_path)
    if ok:
        print("PASSED — database is valid.")
    else:
        print("FAILED — database is corrupted.", file=sys.stderr)
    return 0 if ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="iot-gateway SQLite backup / restore / verify."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--backup", action="store_true", help="Create a timestamped backup.")
    group.add_argument("--restore", action="store_true", help="Restore from a backup.")
    group.add_argument("--list", action="store_true", help="List available backups.")
    group.add_argument("--verify", action="store_true", help="Integrity-check a backup.")

    parser.add_argument("--db", default=None, help="Path to the live database (default: gateway.db).")
    parser.add_argument(
        "--backup-path",
        help="Path to the backup file (required for --restore and --verify).",
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Required flag for --restore to prevent accidental data loss.",
    )
    args = parser.parse_args()

    if args.restore and not args.backup_path:
        parser.error("--backup-path is required with --restore")
    if args.verify and not args.backup_path:
        parser.error("--backup-path is required with --verify")

    if args.backup:
        return cmd_backup(args.db)
    elif args.restore:
        return cmd_restore(args.backup_path, args.confirm)
    elif args.list:
        return cmd_list(args.db)
    elif args.verify:
        return cmd_verify(args.backup_path)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
