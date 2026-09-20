"""
Lightweight history log, SQLite via the standard library only -- no extra
dependency needed. Lets the dashboard show "recent" generations.
"""
import json
import sqlite3
from datetime import datetime, timezone

from . import config


def _connect() -> sqlite3.Connection:
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kind TEXT NOT NULL,
            role TEXT,
            company TEXT,
            created_at TEXT NOT NULL,
            result_json TEXT NOT NULL
        )
        """
    )
    return conn


def save_entry(kind: str, role: str, company: str, result: dict) -> int:
    conn = _connect()
    try:
        cur = conn.execute(
            "INSERT INTO history (kind, role, company, created_at, result_json) "
            "VALUES (?, ?, ?, ?, ?)",
            (kind, role, company, datetime.now(timezone.utc).isoformat(), json.dumps(result)),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def list_recent(limit: int = 20) -> list[dict]:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT id, kind, role, company, created_at FROM history ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    finally:
        conn.close()
    return [
        {"id": r[0], "kind": r[1], "role": r[2], "company": r[3], "created_at": r[4]}
        for r in rows
    ]


def get_entry(entry_id: int) -> dict | None:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT id, kind, role, company, created_at, result_json FROM history WHERE id = ?",
            (entry_id,),
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return None
    return {
        "id": row[0],
        "kind": row[1],
        "role": row[2],
        "company": row[3],
        "created_at": row[4],
        "result": json.loads(row[5]),
    }
