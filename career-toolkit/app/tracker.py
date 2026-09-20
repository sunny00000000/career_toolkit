"""
Application tracker: save a job you're interested in and move it through
Applied -> Interviewing -> Offer / Rejected as things progress. Uses the
same SQLite file as history.py (a second table), so there's still only one
database file for the whole app.
"""
import sqlite3
from datetime import datetime, timezone

from . import config

VALID_STATUSES = ("applied", "interviewing", "offer", "rejected")

_COLUMNS = (
    "id", "title", "company", "location", "url", "salary_min", "salary_max",
    "work_mode", "status", "notes", "created_at", "updated_at",
)


def _connect() -> sqlite3.Connection:
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tracked_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            company TEXT,
            location TEXT,
            url TEXT,
            salary_min INTEGER,
            salary_max INTEGER,
            work_mode TEXT,
            status TEXT NOT NULL DEFAULT 'applied',
            notes TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    return conn


def add_job(job: dict) -> int:
    now = datetime.now(timezone.utc).isoformat()
    conn = _connect()
    try:
        cur = conn.execute(
            """INSERT INTO tracked_jobs
               (title, company, location, url, salary_min, salary_max, work_mode,
                status, notes, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'applied', '', ?, ?)""",
            (
                job.get("title", ""), job.get("company", ""), job.get("location", ""),
                job.get("url", ""), job.get("salary_min"), job.get("salary_max"),
                job.get("work_mode", ""), now, now,
            ),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def list_jobs() -> list[dict]:
    conn = _connect()
    try:
        rows = conn.execute(
            f"SELECT {', '.join(_COLUMNS)} FROM tracked_jobs ORDER BY updated_at DESC"
        ).fetchall()
    finally:
        conn.close()
    return [dict(zip(_COLUMNS, row)) for row in rows]


def update_status(job_id: int, status: str) -> bool:
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid status: {status}")
    conn = _connect()
    try:
        cur = conn.execute(
            "UPDATE tracked_jobs SET status = ?, updated_at = ? WHERE id = ?",
            (status, datetime.now(timezone.utc).isoformat(), job_id),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def update_notes(job_id: int, notes: str) -> bool:
    conn = _connect()
    try:
        cur = conn.execute(
            "UPDATE tracked_jobs SET notes = ?, updated_at = ? WHERE id = ?",
            (notes, datetime.now(timezone.utc).isoformat(), job_id),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def delete_job(job_id: int) -> bool:
    conn = _connect()
    try:
        cur = conn.execute("DELETE FROM tracked_jobs WHERE id = ?", (job_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()
