"""
16e: keep the job description.

Companies take a posting down once applications close, and with it the text
you need to prepare for the interview. Since 1.2.0 every run saves the
posting's full text with the job (tracker.save_job). This file is for the
jobs saved BEFORE that: fetch the page again and keep its text, but only if
the page still is that posting.

NO LLM here. The check (still_the_posting) is a pure function, tested without
the network (tests/test_posting_archive.py).
"""

import re
import time

from job_agent import tracker
from job_agent.models import JobPosting
from job_agent.paths import DATA_DIR
from job_agent.posting import fetch_page_text
from job_agent.research import core_name

_WORD = re.compile(r"[a-z0-9][a-z0-9+#.]*", re.I)
_SMALL = {"and", "the", "for", "with", "our", "you", "are", "ltd", "inc", "pvt", "llc", "of", "in", "to", "at", "a", "an"}


def _words(text: str) -> set[str]:
    return {w.lower().strip(".") for w in _WORD.findall(text)} - _SMALL


def _share(items: list[set[str]], page: set[str]) -> float:
    """The share of `items` found on the page (1.0 when there are none). An
    item counts when most of its words are there: one shared word ("software",
    "team") proves nothing, every job page has it."""
    items = [i for i in items if i]
    return sum(len(i & page) / len(i) >= 0.6 for i in items) / len(items) if items else 1.0


def still_the_posting(text: str, job: JobPosting) -> bool:
    """Is this page text still the saved job's posting?

    A removed posting usually answers with a search page, a "this job is no
    longer available" page or the company's careers home: none of them has
    the description. So the page must (1) name the job: most of the title's
    words, (2) name the employer, and (3) talk about the work: at least half
    of what the agent once read from it (required skills, responsibilities).

    "No longer accepting applications" does NOT disqualify a page: LinkedIn
    keeps the description under that line, and that is the text we want.
    """
    page = _words(text)
    title = _words(job.title)
    if not title or len(title & page) / len(title) < 0.6:
        return False
    company = _words(core_name(job.company))
    if company and not company <= page:  # a list of similar jobs at other companies
        return False
    content = [_words(item) for item in [*job.required_skills, *job.responsibilities]]
    return _share(content, page) >= 0.5 and len(text) >= 600


def fetch_for_job(job_id: int) -> str:
    """Fetch and save one job's posting text. Returns "saved", "gone" (the
    page isn't the posting any more), "unreadable" (blocked, login, offline),
    "not a link" or "already saved"."""
    job = tracker.get_job(job_id)
    if job is None:
        raise ValueError(f"No job with id {job_id}")
    if job.get("posting_text"):
        return "already saved"
    if not str(job["url"]).lower().startswith(("http://", "https://")):
        return "not a link"
    try:
        text = fetch_page_text(job["url"])
    except Exception:  # 404, timeout, login wall, almost no text...
        return "unreadable"
    if not still_the_posting(text, job["job"]):
        return "gone"
    tracker.set_posting_text(job_id, text)
    return "saved"


MARKER = DATA_DIR / "posting_backfill.txt"


def backfill(pause: float = 2.0, force: bool = False, log=print) -> dict | None:
    """ONE try, ever, to fetch the description of every job saved without one
    (the jobs from before 1.2.0). One page at a time with a pause, like a
    person opening the links. Returns the counts, or None if it already ran.
    A job that can't be fetched keeps "not saved"; its details offer one more
    try by hand."""
    if MARKER.exists() and not force:
        return None
    MARKER.parent.mkdir(parents=True, exist_ok=True)
    MARKER.write_text("started", encoding="utf-8")  # first: a crash must not make it run at every start
    counts: dict[str, int] = {}
    for job_id in tracker.jobs_without_posting_text():
        try:
            result = fetch_for_job(job_id)
        except Exception as e:  # one bad row must not end the rest
            result = "unreadable"
            log(f"! job description of job #{job_id}: {e}")
        counts[result] = counts.get(result, 0) + 1
        if result != "not a link":
            time.sleep(pause)
    MARKER.write_text("done " + ", ".join(f"{k}: {v}" for k, v in sorted(counts.items())), encoding="utf-8")
    return counts


# ---------------------------------------------------------------------------
# Reading it: the page text is saved whole (it is the only copy), but a job
# page is mostly not the job. A LinkedIn posting is ~490 lines, of which ~30
# are the description: the rest is the sign-in form (four times) and other
# companies' jobs. readable() is what the job's details show. It only ever
# hides lines; nothing is changed in the tracker.
# ---------------------------------------------------------------------------

_NOISE = {
    "skip to main content", "apply", "save", "report this job", "show", "show more", "show less", "or", ",", ".",
    ", and", "email or phone", "password", "forgot password?", "sign in", "sign in with email", "new to linkedin?",
    "join now", "user agreement", "privacy policy", "cookie policy", "join or sign in to find your next job",
    "join to apply for the", "role at", "use ai to assess how you fit", "am i a good fit for this job?",
    "tailor my resume", "sign in to access ai-powered advices", "apply now", "back to jobs", "share", "share this job",
}
_NOISE_STARTS = ("by clicking continue to join or sign in", "get ai-powered advice on this job",
                 "see who ", "sign in to ")
# From one of these lines on, the page is about other jobs.
_END = ("similar jobs", "people also viewed", "similar searches", "explore collaborative articles",
        "more jobs like this", "you may also like", "recommended jobs")
_END_STARTS = ("referrals increase your chances of interviewing",)


def readable(text: str | None) -> str | None:
    """The saved page text without what is never the job: sign-in forms,
    buttons, and the list of other jobs at the end."""
    if not text:
        return text
    kept: list[str] = []
    for line in text.splitlines():
        low = line.strip().lower()
        if not low or low in _NOISE or low.startswith(_NOISE_STARTS):
            continue
        if len(kept) >= 15 and (low in _END or low.startswith(_END_STARTS)):
            break
        if len(kept) < 25 and line in kept[-6:]:
            continue  # the page's header says title / company / place several times
        kept.append(line)
    result = "\n".join(kept)
    return result if len(result) >= 300 else text  # too little left: better the whole page than a wrong cut
