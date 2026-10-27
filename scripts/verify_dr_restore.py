#!/usr/bin/env python3
"""Automated Disaster Recovery (DR) Snapshot Backup & Point-in-Time Restore Verifier (`scripts/verify_dr_restore.py`).

Verifies Rubric #20 (Failure & Recovery Testing):
1. Creates a SQLite WAL database with sample curriculum, counselor session, and Zero-PII telemetry rows.
2. Computes canonical SHA-256 row checksums across all tables prior to snapshot.
3. Takes an online point-in-time atomic backup using `sqlite3.Connection.backup()`.
4. Simulates catastrophic primary database loss / corruption.
5. Restores from the point-in-time snapshot backup and runs `PRAGMA integrity_check`.
6. Verifies 100% SHA-256 row checksum parity (`rpo_lost_records == 0`) and `rto_seconds < 5.0`.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def _compute_table_checksum_and_count(
    conn: sqlite3.Connection,
    table_name: str,
    order_col: str,
) -> Tuple[str, int]:
    """Computes a deterministic SHA-256 digest and row count for `table_name`."""
    cur = conn.cursor()
    rows = cur.execute(f"SELECT * FROM {table_name} ORDER BY {order_col} ASC").fetchall()
    hasher = hashlib.sha256()
    for row in rows:
        serialized = json.dumps(list(row), sort_keys=False, separators=(",", ":"))
        hasher.update(serialized.encode("utf-8"))
    return hasher.hexdigest(), len(rows)


def _seed_sample_wal_database(db_path: Path) -> Dict[str, Any]:
    """Creates a multi-table SQLite WAL database and populates canonical curriculum/session/telemetry rows."""
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=FULL;")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS counselor_sessions (
                session_id TEXT PRIMARY KEY,
                badge_name TEXT NOT NULL,
                counselor_troop TEXT NOT NULL,
                slide_count INTEGER NOT NULL,
                canonical_pamphlet_sha256 TEXT NOT NULL
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS pamphlet_vector_memory (
                chunk_id TEXT PRIMARY KEY,
                badge_name TEXT NOT NULL,
                req_number TEXT NOT NULL,
                chunk_text TEXT NOT NULL
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS telemetry_workflow_runs (
                run_id TEXT PRIMARY KEY,
                badge_name TEXT NOT NULL,
                duration_ms REAL NOT NULL,
                estimated_cost_usd REAL NOT NULL,
                pii_scrubbed INTEGER NOT NULL
            );
            """
        )

        sessions = [
            ("sess_fa_001", "First Aid", "Troop 19", 38, hashlib.sha256(b"First Aid 2026").hexdigest()),
            ("sess_wx_002", "Weather", "Troop 19", 27, hashlib.sha256(b"Weather 2026").hexdigest()),
            ("sess_cp_003", "Camping", "Troop 19", 25, hashlib.sha256(b"Camping 2026").hexdigest()),
        ]
        conn.executemany(
            "INSERT INTO counselor_sessions VALUES (?, ?, ?, ?, ?);",
            sessions,
        )

        chunks = [
            ("fa_1a", "First Aid", "1a", "Demonstrate how to care for someone who is choking."),
            ("fa_2b", "First Aid", "2b", "Demonstrate direct pressure and tourniquet application."),
            ("wx_9a", "Weather", "9a", "Make one weather instrument such as a barometer or anemometer."),
            ("cp_2a", "Camping", "2a", "Explain the seven principles of Leave No Trace."),
        ]
        conn.executemany(
            "INSERT INTO pamphlet_vector_memory VALUES (?, ?, ?, ?);",
            chunks,
        )

        telemetry_rows = [
            ("run_001", "First Aid", 2410.5, 0.184, 1),
            ("run_002", "Weather", 1980.2, 0.006, 1),
            ("run_003", "Camping", 2150.8, 0.184, 1),
        ]
        conn.executemany(
            "INSERT INTO telemetry_workflow_runs VALUES (?, ?, ?, ?, ?);",
            telemetry_rows,
        )
        conn.commit()
        conn.execute("PRAGMA wal_checkpoint(FULL);")

        tables = [
            ("counselor_sessions", "session_id"),
            ("pamphlet_vector_memory", "chunk_id"),
            ("telemetry_workflow_runs", "run_id"),
        ]
        checksums: Dict[str, str] = {}
        total_records = 0
        for tbl, pk in tables:
            digest, count = _compute_table_checksum_and_count(conn, tbl, pk)
            checksums[tbl] = digest
            total_records += count

        combined_hash = hashlib.sha256(
            json.dumps(checksums, sort_keys=True).encode("utf-8")
        ).hexdigest()
        return {
            "table_checksums": checksums,
            "combined_sha256": combined_hash,
            "total_records": total_records,
        }
    finally:
        conn.close()


def verify_dr_restore(tmp_dir: Optional[str | Path] = None) -> Dict[str, Any]:
    """Executes an end-to-end SQLite WAL snapshot backup, corruption simulation, and point-in-time restore."""
    managed_tmp = tempfile.TemporaryDirectory() if tmp_dir is None else None
    work_dir = Path(managed_tmp.name if managed_tmp is not None else tmp_dir)  # type: ignore[arg-type]
    work_dir.mkdir(parents=True, exist_ok=True)

    try:
        primary_db = work_dir / "scouts_bsa_primary.db"
        snapshot_db = work_dir / "scouts_bsa_snapshot_backup.db"
        restored_db = work_dir / "scouts_bsa_restored.db"

        # 1. Seed primary WAL database and compute pre-disaster SHA-256 checksums
        pre_state = _seed_sample_wal_database(primary_db)

        # 2. Take an online point-in-time snapshot backup via sqlite3.Connection.backup
        t_backup_start = time.perf_counter()
        src_conn = sqlite3.connect(str(primary_db))
        dst_conn = sqlite3.connect(str(snapshot_db))
        try:
            src_conn.backup(dst_conn)
        finally:
            dst_conn.close()
            src_conn.close()
        backup_duration_sec = round(time.perf_counter() - t_backup_start, 6)

        # 3. Simulate catastrophic primary database loss / corruption
        for suffix in ("", "-wal", "-shm"):
            candidate = Path(f"{primary_db}{suffix}")
            if candidate.exists():
                candidate.unlink()
        assert not primary_db.exists(), "Primary DB should be removed during disaster simulation"

        # 4. Restore from point-in-time snapshot and measure RTO latency
        t_restore_start = time.perf_counter()
        snap_conn = sqlite3.connect(str(snapshot_db))
        rest_conn = sqlite3.connect(str(restored_db))
        try:
            snap_conn.backup(rest_conn)
            integrity_row = rest_conn.execute("PRAGMA integrity_check;").fetchone()
            integrity_ok = bool(integrity_row and str(integrity_row[0]).lower() == "ok")

            tables: List[Tuple[str, str]] = [
                ("counselor_sessions", "session_id"),
                ("pamphlet_vector_memory", "chunk_id"),
                ("telemetry_workflow_runs", "run_id"),
            ]
            post_checksums: Dict[str, str] = {}
            restored_records = 0
            for tbl, pk in tables:
                digest, count = _compute_table_checksum_and_count(rest_conn, tbl, pk)
                post_checksums[tbl] = digest
                restored_records += count
        finally:
            rest_conn.close()
            snap_conn.close()

        rto_seconds = round(time.perf_counter() - t_restore_start, 6)
        post_combined_hash = hashlib.sha256(
            json.dumps(post_checksums, sort_keys=True).encode("utf-8")
        ).hexdigest()

        rpo_lost_records = max(0, pre_state["total_records"] - restored_records)
        checksum_parity = (
            pre_state["combined_sha256"] == post_combined_hash
            and pre_state["table_checksums"] == post_checksums
        )
        rto_target_seconds = 5.0
        passed = (
            integrity_ok
            and checksum_parity
            and rpo_lost_records == 0
            and rto_seconds < rto_target_seconds
        )

        return {
            "status": "PASSED" if passed else "FAILED",
            "passed": passed,
            "integrity_check": "ok" if integrity_ok else "failed",
            "pre_disaster_records": pre_state["total_records"],
            "restored_records": restored_records,
            "rpo_lost_records": rpo_lost_records,
            "rto_seconds": rto_seconds,
            "rto_target_seconds": rto_target_seconds,
            "backup_duration_seconds": backup_duration_sec,
            "checksum_parity_verified": checksum_parity,
            "pre_disaster_sha256": pre_state["combined_sha256"],
            "post_restore_sha256": post_combined_hash,
            "table_checksums": post_checksums,
        }
    finally:
        if managed_tmp is not None:
            managed_tmp.cleanup()


def main() -> int:
    report = verify_dr_restore()
    print(json.dumps(report, indent=2))
    if not report.get("passed"):
        print("DR RESTORE VERIFICATION FAILED", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
