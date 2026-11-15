"""
"Did you apply?" (16i, D43): a job shouldn't sit in "Cover note ready" for
long, because postings close.

    asked when:  status is cover_note_ready
                 AND 24 hours have passed since the cover note was approved
                     (or since you answered "Not yet")
                 AND you didn't press Ignore for this cover note
                 AND the question hasn't been open for 24 hours already

Three answers:
    Yes, I applied  -> the job moves to Applied (tracker.update_status)
    Not yet         -> asked again 24 hours from now
    Ignore          -> never asked again for this cover note
No answer within 24 hours of the question counts as Ignore: a reminder must
not stay pending. The 24 hours start when JobLens first showed the question
(`apply_asked_at`), not when it became due: a PC that was off all weekend
shouldn't cost you the question.

A NEW cover note for the same job starts over: every stored time is
compared with the approval, and older ones don't count.

NO LLM here: plain dates. The rule is a pure function (state), tested
without a database (tests/test_applyreminder.py).
"""

from datetime import datetime, timedelta, timezone

from job_agent import tracker

STATUS = "cover_note_ready"
ASK_AFTER = timedelta(hours=24)       # after the approval, or after "Not yet"
ANSWER_WITHIN = timedelta(hours=24)   # then the question is dropped
BEST_FIT = 75                         # the dashboard's "Ready to apply" list (= the galaxy's top band)
_FORMAT = "%Y-%m-%d %H:%M:%S"         # SQLite's CURRENT_TIMESTAMP, in UTC


def _parse(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, _FORMAT).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _get(job, key: str):
    return job[key] if key in job.keys() else None


def approved_at(job) -> datetime | None:
    """When the newest cover note was approved; a job moved to "Cover note
    ready" by hand has no note, so its last status change counts."""
    return _parse(_get(job, "note_approved_at")) or _parse(_get(job, "updated_at"))


def state(job, now: datetime | None = None) -> str:
    """One of:
        "off"      not a cover-note-ready job
        "waiting"  the 24 hours aren't over yet
        "due"      ask now
        "ignored"  you pressed Ignore
        "expired"  the question was open for 24 hours without an answer
    `job`: a tracker row (or dict) with status, updated_at, note_approved_at,
    apply_asked_at, apply_snoozed_until, apply_ignored_at."""
    approved = approved_at(job)
    if job["status"] != STATUS or approved is None:
        return "off"
    now = now or _now()
    ignored = _parse(_get(job, "apply_ignored_at"))
    if ignored and ignored >= approved:
        return "ignored"
    start = approved + ASK_AFTER
    snoozed = _parse(_get(job, "apply_snoozed_until"))
    if snoozed and snoozed > start:
        start = snoozed
    if now < start:
        return "waiting"
    asked = _parse(_get(job, "apply_asked_at"))
    if asked_this_round(job) and now - asked >= ANSWER_WITHIN:  # shown a day ago, no answer
        return "expired"
    return "due"


def is_due(job, now: datetime | None = None) -> bool:
    return state(job, now) == "due"


def in_ready_list(job, now: datetime | None = None) -> bool:
    """The dashboard's "Ready to apply": best fits with a cover note, not
    applied. A job you pressed Ignore on is left out; one whose question
    simply ran out stays (you never said no)."""
    return state(job, now) not in ("off", "ignored") and (job["fit_score"] or 0) >= BEST_FIT


def _set(job_id: int, column: str, value: str) -> None:
    tracker.init_db()
    with tracker._db() as conn:
        cur = conn.execute(f"UPDATE jobs SET {column} = ? WHERE id = ?", (value, job_id))  # column: ours only
    if cur.rowcount == 0:
        raise ValueError(f"No job with id {job_id}")


def due_jobs(now: datetime | None = None, mark: bool = False) -> list:
    """The jobs to ask about now. mark=True: JobLens is showing the question,
    so the 24 hours to answer start for the ones not asked yet in this round."""
    now = now or _now()
    due = [job for job in tracker.list_jobs() if is_due(job, now)]
    if mark:
        for job in due:
            if not asked_this_round(job):
                _set(job["id"], "apply_asked_at", now.strftime(_FORMAT))
    return due


def asked_this_round(job) -> bool:
    """Was the question already shown since the approval / the last "Not yet"?"""
    approved, asked = approved_at(job), _parse(_get(job, "apply_asked_at"))
    if approved is None or asked is None:
        return False
    start = max(filter(None, (approved + ASK_AFTER, _parse(_get(job, "apply_snoozed_until")))))
    return asked >= start


def new_jobs(now: datetime | None = None) -> list:
    """Due and not shown yet: what a notification should announce (once)."""
    return [job for job in due_jobs(now) if not asked_this_round(job)]


def not_yet(job_id: int, now: datetime | None = None) -> None:
    """"Not yet": ask again in 24 hours."""
    _set(job_id, "apply_snoozed_until", ((now or _now()) + ASK_AFTER).strftime(_FORMAT))


def ignore(job_id: int, now: datetime | None = None) -> None:
    """Never ask again about this cover note."""
    _set(job_id, "apply_ignored_at", (now or _now()).strftime(_FORMAT))
