"""
19b (E7): the interview date you type on a job (14h) becomes a calendar.

    upcoming()      interviews still ahead, soonest first (Dashboard, Tracker)
    due()           reminders to send now:
                      "evening" from 18:00 the day before
                      "hour"    in the last hour before (only with a time)
                    each is sent once per interview: `interview_reminded`
                    remembers "<interview_at>|evening,hour", so a changed
                    date starts afresh by itself
    ics()           the interview as an .ics file: Outlook, Google and Apple
                    calendars all open it

Times are your local time, stored as typed (14h). The .ics uses "floating"
time (no time zone), which every calendar reads as local: the same 10:30
you typed. A date without a time becomes an all-day event.

Rejected jobs get no reminders. NO LLM here. Tests: tests/test_interviews.py.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone

from job_agent import tracker

EVENING = time(18, 0)
KINDS = ("evening", "hour")
QUIET = ("rejected",)  # no reminders for these


def parse(value: str | None) -> tuple[datetime, bool] | None:
    """("2026-11-24T10:30" -> (datetime, True)); a date only -> midnight, False."""
    if not value:
        return None
    for fmt, timed in (("%Y-%m-%dT%H:%M", True), ("%Y-%m-%d", False)):
        try:
            return datetime.strptime(value, fmt), timed
        except ValueError:
            pass
    return None


def ahead(value: str | None, now: datetime) -> bool:
    """Still to come: a timed one until it starts, a date-only one all that day."""
    parsed = parse(value)
    if not parsed:
        return False
    at, timed = parsed
    return at > now if timed else at.date() >= now.date()


def upcoming(jobs: list[dict], now: datetime | None = None, days: int | None = None) -> list[dict]:
    """Interviews still ahead (within `days`, if given), soonest first."""
    now = now or datetime.now()
    out = []
    for job in jobs:
        value = job.get("interview_at")
        if job.get("status") in QUIET or not ahead(value, now):
            continue
        at, timed = parse(value)
        if days is not None and at.date() > now.date() + timedelta(days=days):
            continue
        out.append({"id": job["id"], "company": job["company"], "title": job["title"], "status": job["status"],
                    "interview_at": value, "timed": timed, "contact": job.get("contact"),
                    "days": (at.date() - now.date()).days, "interview_reminded": job.get("interview_reminded")})
    return sorted(out, key=lambda j: parse(j["interview_at"])[0])


def _sent(job: dict) -> set[str]:
    """The reminders already sent for THIS interview date."""
    raw = job.get("interview_reminded") or ""
    at, _, kinds = raw.partition("|")
    return set(kinds.split(",")) - {""} if at == job.get("interview_at") else set()


def due(jobs: list[dict], now: datetime | None = None) -> list[tuple[dict, str]]:
    """(job, "evening" | "hour") for every reminder that should go out now.
    One per job: the hour reminder wins when both are due (a late start)."""
    now = now or datetime.now()
    out = []
    for job in upcoming(jobs, now):
        at, timed = parse(job["interview_at"])
        sent = _sent(job)
        if timed and "hour" not in sent and at - now <= timedelta(hours=1):
            out.append((job, "hour"))
        elif "evening" not in sent and "hour" not in sent and now >= datetime.combine(at.date() - timedelta(days=1), EVENING):
            if timed or at.date() > now.date():  # a date-only one: not on the day itself any more
                out.append((job, "evening"))
    return out


def mark_sent(job_id: int, interview_at: str, kind: str) -> None:
    """Remember a reminder went out. "hour" also counts as "evening" (never send it after)."""
    if kind not in KINDS:
        raise ValueError(f"Unknown reminder '{kind}'")
    job = tracker.get_job(int(job_id))
    if not job:
        return
    kinds = _sent(job) | {kind} | ({"evening"} if kind == "hour" else set())
    tracker.init_db()
    with tracker._db() as conn:
        conn.execute("UPDATE jobs SET interview_reminded = ? WHERE id = ?",
                     (f"{interview_at}|{','.join(sorted(kinds))}", int(job_id)))


def label(value: str) -> str:
    """'Tue 24 Nov, 10:30' or 'Tue 24 Nov' - for notifications."""
    at, timed = parse(value)
    day = f"{at:%a} {at.day} {at:%b}"
    return f"{day}, {at:%H:%M}" if timed else day


def notice(job: dict, kind: str, now: datetime | None = None) -> tuple[str, str]:
    """(title, message) for the tray. The evening reminder may arrive on the
    day itself (JobLens wasn't running the evening before): then it says today."""
    now = now or datetime.now()
    at, timed = parse(job["interview_at"])
    who = f"{job['title']} at {job['company']}"
    if kind == "hour":
        return "Interview soon", f"{who} at {at:%H:%M}. Click to open the job and its prep sheet."
    day = "today" if at.date() == now.date() else "tomorrow"
    when = f"{day} at {at:%H:%M}" if timed else day
    return f"Interview {day}", f"{who}, {when}. Click to open the job and its prep sheet."


# ---------------------------------------------------------------------------
# .ics (RFC 5545)
# ---------------------------------------------------------------------------


def _text(value: str) -> str:
    """Escape for an .ics text value."""
    return (value.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
            .replace("\r\n", "\n").replace("\n", "\\n"))


def _fold(line: str) -> list[str]:
    """Lines longer than 75 bytes continue on the next line after a space."""
    out, current = [], ""
    for ch in line:
        limit = 75 if not out else 74  # a continuation starts with one space
        if len((current + ch).encode("utf-8")) > limit:
            out.append(current)
            current = ch
        else:
            current += ch
    out.append(current)
    return [out[0]] + [" " + part for part in out[1:]]


def ics(job: dict, now: datetime | None = None, minutes: int = 60) -> str:
    """One VEVENT for this job's interview, with a reminder an hour before."""
    parsed = parse(job.get("interview_at"))
    if not parsed:
        raise ValueError("This job has no interview date yet.")
    at, timed = parsed
    stamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%SZ")
    summary = f"Interview: {job['title']} at {job['company']}"
    if timed:
        start = [f"DTSTART:{at:%Y%m%dT%H%M%S}", f"DTEND:{at + timedelta(minutes=minutes):%Y%m%dT%H%M%S}"]
    else:
        start = [f"DTSTART;VALUE=DATE:{at:%Y%m%d}", f"DTEND;VALUE=DATE:{at.date() + timedelta(days=1):%Y%m%d}"]
    details = [f"Interview for {job['title']} at {job['company']}."]
    if job.get("contact"):
        details.append(f"Contact: {job['contact']}")
    if (job.get("url") or "").startswith(("http://", "https://")):
        details.append(f"Posting: {job['url']}")
    details.append("Prep sheet: open the job in JobLens → Interview prep.")
    lines = [
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//JobLens//Interview calendar//EN", "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH", "BEGIN:VEVENT",
        f"UID:joblens-job-{job['id']}-{at:%Y%m%dT%H%M}@joblens.local", f"DTSTAMP:{stamp}", *start,
        f"SUMMARY:{_text(summary)}",
        f"DESCRIPTION:{_text(chr(10).join(details))}",
    ]
    if job.get("location") and job["location"] != "Not specified":
        lines.append(f"LOCATION:{_text(job['location'])}")
    if timed:
        lines += ["BEGIN:VALARM", "ACTION:DISPLAY", "DESCRIPTION:Interview in an hour", "TRIGGER:-PT1H", "END:VALARM"]
    lines += ["END:VEVENT", "END:VCALENDAR"]
    return "\r\n".join(part for line in lines for part in _fold(line)) + "\r\n"


def file_name(job: dict) -> str:
    from job_agent.export import file_name as safe

    return safe("Interview", job["company"], job["title"], ext="ics")

