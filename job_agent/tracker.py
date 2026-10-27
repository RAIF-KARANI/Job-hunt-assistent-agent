"""
Phase 4: the job tracker - persistent memory in a SQLite database.

Why a database?
    Everything the agent learned so far disappears when the program exits.
    The tracker saves each job to data/jobs.db (one file, no server), so
    you can list, compare and update jobs across runs and days.

Notice: NO LLM in this file. Saving data must be exact and predictable, so
it's 100% plain code. The LLM produces the data; code stores it.

Two kinds of columns:
    - normal columns (title, fit_score, status...) for filtering and sorting:
      e.g.  SELECT * FROM jobs WHERE fit_score >= 70 ORDER BY fit_score DESC
    - *_json columns that keep the full Pydantic objects, so no detail is lost
      and we can rebuild the objects later (Phase 5 needs them for the note).
"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from job_agent.models import CompanyBrief, JobPosting, ResumeMatch
from job_agent.paths import DB_PATH

# The life of a job application. update_status() only accepts these.
STATUSES = (
    "researched",        # agent analyzed it (set automatically)
    "cover_note_ready",  # you approved a cover note (Phase 5)
    "applied",
    "interviewing",
    "offer",
    "rejected",
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    url           TEXT UNIQUE NOT NULL,      -- UNIQUE: one row per posting
    title         TEXT NOT NULL,
    company       TEXT NOT NULL,
    location      TEXT,
    seniority     TEXT,
    salary        TEXT,
    fit_score     INTEGER,
    best_resume   TEXT,
    status        TEXT NOT NULL DEFAULT 'researched',
    job_json      TEXT,                      -- full JobPosting
    fit_json      TEXT,                      -- full ResumeMatch (best)
    company_json  TEXT,                      -- full CompanyBrief (may be NULL)
    created_at    TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at    TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS cover_notes (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id       INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    text         TEXT NOT NULL,
    approved_at  TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


@contextmanager
def _db(path: Path | None = None):
    """Open a connection, commit if all went well, always close it."""
    # DB_PATH is read at call time (not as a default argument) so tests can
    # point it at a temporary database.
    conn = sqlite3.connect(path or DB_PATH)
    conn.row_factory = sqlite3.Row  # rows behave like dicts: row["title"]
    conn.execute("PRAGMA foreign_keys = ON")  # SQLite has them OFF by default
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    """Create the tables if they don't exist yet. Safe to call every run."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)  # fresh install: nothing exists yet
    with _db() as conn:
        conn.executescript(SCHEMA)


def save_job(
    url: str, job: JobPosting, best: ResumeMatch, company: CompanyBrief | None
) -> int:
    """Insert a job, or update it if this URL is already tracked. Returns its id.

    This is an "upsert" (update-or-insert). Running the agent twice on the
    same URL must not create a duplicate row - that property is called
    idempotency, and it matters for agents because they get re-run a lot.
    """
    init_db()
    values = {
        "url": url,
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "seniority": job.seniority,
        "salary": job.salary,
        "fit_score": best.fit_score,
        "best_resume": best.resume_name,
        "job_json": job.model_dump_json(),
        "fit_json": best.model_dump_json(),
        "company_json": company.model_dump_json() if company else None,
    }
    with _db() as conn:
        # The ? / :name placeholders let sqlite3 insert values safely.
        # NEVER build SQL with f-strings from outside data: that's how
        # SQL injection happens (a job title like "x'); DROP TABLE jobs;--").
        row = conn.execute(
            """
            INSERT INTO jobs (url, title, company, location, seniority, salary,
                              fit_score, best_resume, job_json, fit_json, company_json)
            VALUES (:url, :title, :company, :location, :seniority, :salary,
                    :fit_score, :best_resume, :job_json, :fit_json, :company_json)
            ON CONFLICT(url) DO UPDATE SET
                title = excluded.title,
                company = excluded.company,
                location = excluded.location,
                seniority = excluded.seniority,
                salary = excluded.salary,
                fit_score = excluded.fit_score,
                best_resume = excluded.best_resume,
                job_json = excluded.job_json,
                fit_json = excluded.fit_json,
                company_json = excluded.company_json,
                updated_at = CURRENT_TIMESTAMP
                -- status is NOT overwritten: re-analysing a job you already
                -- applied to must not reset it back to 'researched'.
            RETURNING id
            """,
            values,
        ).fetchone()
    return row["id"]


def find_job_id(url: str) -> int | None:
    """The id of the job with this URL, or None if it isn't tracked yet."""
    init_db()
    with _db() as conn:
        row = conn.execute("SELECT id FROM jobs WHERE url = ?", (url,)).fetchone()
    return row["id"] if row else None


def list_jobs() -> list[sqlite3.Row]:
    """All tracked jobs, best fit first."""
    init_db()
    with _db() as conn:
        return conn.execute(
            """SELECT id, title, company, fit_score, best_resume, status, updated_at
               FROM jobs ORDER BY fit_score DESC, updated_at DESC"""
        ).fetchall()


def get_job(job_id: int) -> dict | None:
    """One job with its JSON columns turned back into Pydantic objects."""
    init_db()
    with _db() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if row is None:
        return None
    return {
        **dict(row),
        "job": JobPosting.model_validate_json(row["job_json"]),
        "best_match": ResumeMatch.model_validate_json(row["fit_json"]),
        "company_brief": (
            CompanyBrief.model_validate_json(row["company_json"])
            if row["company_json"]
            else None
        ),
    }


def add_cover_note(job_id: int, text: str) -> int:
    """Store an approved cover note. Returns the note's id.

    This function does NOT check approval - it's a plain database helper.
    The approval guardrail lives in cover_note.save_cover_note(), which is
    the only place that should call this.
    """
    with _db() as conn:
        row = conn.execute(
            "INSERT INTO cover_notes (job_id, text) VALUES (?, ?) RETURNING id",
            (job_id, text),
        ).fetchone()
    return row["id"]


def update_status(job_id: int, status: str) -> None:
    """Move a job to a new stage, e.g. 'applied'. Rejects unknown statuses."""
    if status not in STATUSES:
        raise ValueError(f"Unknown status '{status}'. Use one of: {', '.join(STATUSES)}")
    with _db() as conn:
        cur = conn.execute(
            "UPDATE jobs SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (status, job_id),
        )
    if cur.rowcount == 0:
        raise ValueError(f"No job with id {job_id}")
