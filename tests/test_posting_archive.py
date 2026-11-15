"""16e: the job description is kept with the job. No network and no model:
fetch_page_text is replaced by a fake."""

import pytest

from desktop_web.bridge import Api
from job_agent import graph, posting_archive as pa, tracker
from job_agent.models import FitAnalysis, JobPosting, ResumeMatch

POSTING = """Backend Engineer at Acme Robotics - Bengaluru
About the role
You will design and build REST APIs in Python for our warehouse robots.
Requirements
- Python and Django
- PostgreSQL
- Docker and Kubernetes
Responsibilities
- Build and maintain backend services
- Write automated tests
""" + "Acme Robotics is an equal opportunity employer. " * 12

SIMILAR_JOBS = """Backend Engineer jobs in Bengaluru
Backend Engineer at Globex - Bengaluru - 2 days ago
Backend Engineer at Initech - Remote - 1 week ago
Sign in to see who you already know at these companies.
""" + "Create a job alert for Backend Engineer roles. " * 15


@pytest.fixture(autouse=True)
def temp_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(tracker, "DB_PATH", tmp_path / "jobs.db")
    monkeypatch.setattr(pa, "MARKER", tmp_path / "posting_backfill.txt")


def job():
    return JobPosting(title="Backend Engineer", company="Acme Robotics Pvt. Ltd.", location="Bengaluru",
                      employment_type="Full-time", seniority="Junior", salary="Not specified", summary="x",
                      required_skills=["Python and Django", "PostgreSQL", "Docker and Kubernetes"],
                      nice_to_have_skills=[], responsibilities=["Build and maintain backend services", "Write automated tests"])


def best():
    return ResumeMatch(resume_name="cv.pdf", fit_score=80,
                       analysis=FitAnalysis(matching_skills=[], missing_skills=[], reasoning="x", talking_points=[]))


def save(url="https://jobs.example/1", text=None):
    return tracker.save_job(url, job(), best(), None, posting_text=text)


def pages(monkeypatch, by_url):
    def fetch(url):
        if isinstance(by_url.get(url), Exception):
            raise by_url[url]
        return by_url[url]
    monkeypatch.setattr(pa, "fetch_page_text", fetch)


# ---- saving ------------------------------------------------------------------------

def test_the_text_is_saved_and_a_reanalysis_keeps_it():
    job_id = save(text=POSTING)
    assert tracker.get_job(job_id)["posting_text"] == POSTING
    save()                                                    # analyzed again, without a text
    assert tracker.get_job(job_id)["posting_text"] == POSTING
    save(text="the new text")                                 # analyzed again, with one: the newer wins
    assert tracker.get_job(job_id)["posting_text"] == "the new text"


def test_the_run_hands_the_text_to_the_tracker(monkeypatch, tmp_path):
    posting = tmp_path / "posting.txt"
    posting.write_text(POSTING, encoding="utf-8")
    monkeypatch.setattr(graph, "extract_job_posting", lambda text: job())
    state = graph.read_posting({"url": str(posting)})
    assert state["posting_text"] == POSTING
    result = graph.save_to_tracker({"url": str(posting), "job": job(), "best_match": best(), "company_brief": None, **state})
    assert tracker.get_job(result["job_id"])["posting_text"] == POSTING


def test_setting_the_text_later_keeps_the_dates():
    job_id = save()
    before = tracker.get_job(job_id)["updated_at"]
    with tracker._db() as conn:
        conn.execute("UPDATE jobs SET updated_at = '2020-01-01 00:00:00' WHERE id = ?", (job_id,))
    tracker.set_posting_text(job_id, POSTING)
    assert tracker.get_job(job_id)["updated_at"] == "2020-01-01 00:00:00" != before   # the follow-up clock isn't restarted
    with pytest.raises(ValueError):
        tracker.set_posting_text(999, "x")


# ---- is the page still the posting? -------------------------------------------------

def test_the_real_posting_is_recognised():
    assert pa.still_the_posting(POSTING, job())
    closed = "No longer accepting applications\n" + POSTING   # LinkedIn keeps the text under that line
    assert pa.still_the_posting(closed, job())


def test_a_page_of_similar_jobs_is_not_the_posting():
    assert not pa.still_the_posting(SIMILAR_JOBS, job())                       # the title is there, the employer isn't
    assert not pa.still_the_posting("Acme Robotics careers. Backend Engineer. " * 30, job())  # no word about the work
    assert not pa.still_the_posting("This job is no longer available.", job())
    assert not pa.still_the_posting(POSTING.replace("Backend Engineer", "Sales Manager"), job())


# ---- fetching for the jobs saved before 1.2.0 ---------------------------------------

def test_one_job_saved_gone_unreadable(monkeypatch):
    live, gone, blocked = save("https://a.example"), save("https://b.example"), save("https://c.example")
    pasted, kept = save("C:/postings/job.txt"), save("https://d.example", text="already here")
    pages(monkeypatch, {"https://a.example": POSTING, "https://b.example": SIMILAR_JOBS,
                        "https://c.example": ValueError("almost no text")})
    assert pa.fetch_for_job(live) == "saved" and tracker.get_job(live)["posting_text"] == POSTING
    assert pa.fetch_for_job(gone) == "gone" and tracker.get_job(gone)["posting_text"] is None
    assert pa.fetch_for_job(blocked) == "unreadable"
    assert pa.fetch_for_job(pasted) == "not a link"
    assert pa.fetch_for_job(kept) == "already saved"            # never fetched: nothing in `pages` for it
    with pytest.raises(ValueError):
        pa.fetch_for_job(999)


def test_the_one_time_fetch_runs_once(monkeypatch):
    live, gone = save("https://a.example"), save("https://b.example")
    save("https://d.example", text="already here")
    asked = []
    monkeypatch.setattr(pa, "fetch_page_text", lambda url: (asked.append(url), POSTING if "a." in url else SIMILAR_JOBS)[1])
    assert pa.backfill(pause=0) == {"saved": 1, "gone": 1}
    assert sorted(asked) == ["https://a.example", "https://b.example"]         # the job with a text isn't fetched
    assert tracker.jobs_without_posting_text() == [gone]
    assert pa.backfill(pause=0) is None and len(asked) == 2                     # never again
    assert pa.MARKER.read_text(encoding="utf-8") == "done gone: 1, saved: 1"


def test_a_crash_midway_does_not_make_it_run_at_every_start(monkeypatch):
    save("https://a.example")
    monkeypatch.setattr(pa, "fetch_for_job", lambda job_id: (_ for _ in ()).throw(KeyboardInterrupt()))
    with pytest.raises(KeyboardInterrupt):
        pa.backfill(pause=0)
    assert pa.backfill(pause=0) is None                                         # marked before the first page


# ---- the bridge ------------------------------------------------------------------------

def test_the_page_gets_the_text_and_can_ask_for_one_more_try(monkeypatch):
    api = Api(send=lambda e: None, graph=object())
    old = save("https://a.example")
    assert api.get_job(old)["posting_text"] is None
    pages(monkeypatch, {"https://a.example": POSTING})
    assert api.fetch_posting_text(old) == {"result": "saved", "posting_text": POSTING, "posting_readable": pa.readable(POSTING)}
    assert api.get_job(old)["posting_text"] == POSTING


# ---- reading it ------------------------------------------------------------------------

LINKEDIN = """Backend Engineer at Acme Robotics | LinkedIn Jobs
Skip to main content
Backend Engineer
Acme Robotics
Bengaluru
Apply
Join or sign in to find your next job
Join to apply for the
Backend Engineer
role at
Acme Robotics
Email or phone
Password
Show
Forgot password?
Sign in
By clicking Continue to join or sign in, you agree to LinkedIn's
User Agreement
,
Privacy Policy
, and
Cookie Policy
.
2 weeks ago
Description
""" + "\n".join(f"You will build service number {n} in Python for our warehouse robots." for n in range(12)) + """
Seniority level
Entry level
Referrals increase your chances of interviewing at Acme Robotics by 2x
Similar jobs
Backend Engineer
Globex
Sign in
"""


def test_readable_drops_the_sign_in_form_and_other_jobs():
    text = pa.readable(LINKEDIN)
    lines = text.splitlines()
    assert lines[:4] == ["Backend Engineer at Acme Robotics | LinkedIn Jobs", "Backend Engineer", "Acme Robotics", "Bengaluru"]
    assert "Password" not in lines and "Sign in" not in lines and "Apply" not in lines
    assert "Globex" not in text and "Referrals" not in text          # other companies' jobs: cut
    assert text.count("You will build service number") == 12 and "Entry level" in text   # the job: all there


def test_readable_never_leaves_too_little():
    short = "Sign in\nPassword\nA short posting.\n" * 3
    assert pa.readable(short) == short                                # too little left: the whole page
    assert pa.readable(None) is None and pa.readable("") == ""


def test_the_details_get_the_readable_text():
    api = Api(send=lambda e: None, graph=object())
    job_id = save(text=LINKEDIN)
    data = api.get_job(job_id)
    assert data["posting_text"] == LINKEDIN and data["posting_readable"] == pa.readable(LINKEDIN)
