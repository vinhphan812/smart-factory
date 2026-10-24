"""Helper script for Scenario 05 (sqlite_lock): opens the gateway database
with an exclusive write lock to verify that concurrent locks do not corrupt
or wedge the gateway.
"""

from __future__ import annotations

import os
import sqlite3
import time

DB_PATH = os.environ.get("GATEWAY_DB_PATH", "/app/data/gateway.db")

def main() -> int:
    print(f"[lock-holder] Opening {DB_PATH} with exclusive write lock...")
    conn = sqlite3.connect(DB_PATH, timeout=5)
    try:
        conn.execute("BEGIN EXCLUSIVE")
        print("[lock-holder] Acquired EXCLUSIVE lock. Holding for 45s...")
        time.sleep(45)
        conn.commit()
        print("[lock-holder] Released lock successfully.")
    except Exception as exc:
        print(f"[lock-holder] Error holding lock: {exc}")
        try:
            conn.rollback()
        except Exception:
            pass
        return 1
    finally:
        conn.close()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
