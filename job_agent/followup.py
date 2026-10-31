"""
Follow-up reminders (14e, D31): an application that has sat in Applied or
Interviewing for a week deserves a short "any news?" email.

    due when:  status is applied or interviewing
               AND FOLLOW_UP_DAYS have passed since the last change
                   (the status change, or your "I followed up")
               AND it isn't snoozed

Marking "I followed up" starts the clock again; a status change does too
(update_status() sets updated_at). Snooze hides it for a few days.

NO LLM here: plain dates. The rule is a pure function (is_due), so it is
tested without a database (tests/test_followup.py).
"""

import os
from datetime import datetime, timedelta, timezone

from job_agent import tracker

FOLLOW_UP_STATUSES = ("applied", "interviewing")
DAY_CHOICES = ("off", "3", "5", "7", "14")
SNOOZE_DAYS = 3
_FORMAT = "%Y-%m-%d %H:%M:%S"  # SQLite's CURRENT_TIMESTAMP, in UTC


def _parse(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, _FORMAT).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def days_setting() -> int | None:
    """FOLLOW_UP_DAYS as a number, or None when reminders are off."""
    value = os.getenv("FOLLOW_UP_DAYS", "7").strip().lower()
    return int(value) if value.isdigit() and int(value) > 0 else None


def is_due(job, days: int | None, now: datetime | None = None) -> bool:
    """`job`: a tracker row (or dict) with status, updated_at, followed_up_at, snoozed_until."""
    if days is None or job["status"] not in FOLLOW_UP_STATUSES:
        return False
    now = now or _now()
    snoozed = _parse(job["snoozed_until"])
    if snoozed and snoozed > now:
        return False
    since = max(filter(None, (_parse(job["updated_at"]), _parse(job["followed_up_at"]))), default=None)
    return since is not None and now - since >= timedelta(days=days)


def due_jobs(now: datetime | None = None) -> list:
    days = days_setting()
    return [job for job in tracker.list_jobs() if is_due(job, days, now)]


def _set(job_id: int, column: str, value: str) -> None:
    tracker.init_db()
    with tracker._db() as conn:
        cur = conn.execute(f"UPDATE jobs SET {column} = ? WHERE id = ?", (value, job_id))  # column: ours only
    if cur.rowcount == 0:
        raise ValueError(f"No job with id {job_id}")


def mark_followed_up(job_id: int, now: datetime | None = None) -> None:
    """You sent the follow-up: the next reminder comes FOLLOW_UP_DAYS from now."""
    _set(job_id, "followed_up_at", (now or _now()).strftime(_FORMAT))


def snooze(job_id: int, days: int = SNOOZE_DAYS, now: datetime | None = None) -> None:
    _set(job_id, "snoozed_until", ((now or _now()) + timedelta(days=days)).strftime(_FORMAT))
