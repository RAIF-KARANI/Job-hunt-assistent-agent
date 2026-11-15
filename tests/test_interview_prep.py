"""16f: the interview prep sheet is built from the tracker by plain code.
The point of these tests: every line of the sheet is something that was
saved, and nothing that wasn't saved appears."""

import zipfile

import pytest

from desktop_web.bridge import Api
from job_agent import interview_prep as ip
from job_agent import tracker
from job_agent.models import CompanyBrief, FitAnalysis, JobPosting, ResumeMatch, SkillMatch

POSTING_TEXT = ("Backend Engineer at Acme Robotics\nSign in\nPassword\n"
                + "".join(f"You will build API number {n} in Python.\n" for n in range(20)))


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(tracker, "DB_PATH", tmp_path / "jobs.db")


def posting(**changes):
    values = dict(title="Backend Engineer", company="Acme Robotics", location="Bengaluru", employment_type="Full-time",
                  seniority="Junior", salary="Not specified", summary="Build the robot fleet's APIs.",
                  required_skills=["Python", "PostgreSQL", "Kubernetes"], nice_to_have_skills=["Go"],
                  responsibilities=["Build REST APIs", "Write tests"])
    return JobPosting(**{**values, **changes})


def match():
    analysis = FitAnalysis(
        matching_skills=[SkillMatch(requirement="Python", resume_evidence="Built a FastAPI service in Python")],
        partial_skills=[SkillMatch(requirement="PostgreSQL", resume_evidence="SQLite, SQLAlchemy")],
        missing_skills=["Kubernetes", "Go"], gap_reasons={"Kubernetes": "Docker only; no orchestration shown"},
        talking_points=["Cut DB latency from 1.2 s to 9 ms"], verdict="Apply: Python is proven.")
    return ResumeMatch(resume_name="cv.pdf", fit_score=72, analysis=analysis)


def brief():
    return CompanyBrief(what_they_do="Acme Robotics builds warehouse robots.", products=["PickBot"], size_and_stage="Unknown",
                        recent_news=["Opened a Pune office (2026-09-01)"], culture_and_values=["Remote-first"],
                        cover_note_hooks=["PickBot launch"], sources=["https://acme.example/about"])


def save(company=True, text=POSTING_TEXT, job=None):
    job_id = tracker.save_job("https://jobs.example/1", job or posting(), match(), brief() if company else None, posting_text=text)
    return job_id


def sheet(job_id, note=None):
    return ip.build_sheet(tracker.get_job(job_id), note)


def test_the_sheet_holds_what_was_saved():
    job_id = save()
    tracker.save_notes(job_id, {"notes": "Ask about on-call.", "interview_at": "2026-11-20T10:30", "contact": "Dana (recruiter)"})
    s = sheet(job_id, "Dear Acme team,\n\nI built APIs.")
    assert (s["title"], s["company"], s["resume"], s["fit_score"]) == ("Backend Engineer", "Acme Robotics", "cv.pdf", 72)
    assert s["proven"] == [{"requirement": "Python", "evidence": "Built a FastAPI service in Python"}]
    assert s["partial"] == [{"requirement": "PostgreSQL", "evidence": "SQLite, SQLAlchemy"}]
    assert s["gaps"] == [{"requirement": "Kubernetes", "reason": "Docker only; no orchestration shown"},
                         {"requirement": "Go", "reason": ""}]                      # a gap without a saved reason has none
    assert s["talking_points"] == ["Cut DB latency from 1.2 s to 9 ms"]
    assert s["research"]["products"] == ["PickBot"] and s["research"]["sources"] == ["https://acme.example/about"]
    assert s["research"]["size_and_stage"] == ""                                   # "Unknown" isn't shown as a fact
    assert s["cover_note"] == "Dear Acme team,\n\nI built APIs." and s["notes"] == "Ask about on-call."
    facts = {f["label"]: f["value"] for f in s["facts"]}
    assert facts == {"Location": "Bengaluru", "Type": "Full-time", "Level": "Junior",
                     "Interview": "2026-11-20 10:30", "Contact": "Dana (recruiter)"}   # no "Salary: Not specified"
    assert "Sign in" not in s["description"] and "You will build API number 7 in Python." in s["description"]


def test_what_is_missing_is_left_out_not_made_up():
    job_id = save(company=False, text=None)
    s = sheet(job_id)
    assert s["research"] is None and s["cover_note"] is None and s["notes"] is None and s["description"] is None
    text = ip.as_text(s)
    for heading in ("THE COMPANY", "THE COVER NOTE", "YOUR NOTES", "THE JOB DESCRIPTION"):
        assert heading not in text                                                 # no empty sections
    assert "WHAT YOUR RESUME PROVES (cv.pdf, fit 72)" in text                      # the file name stays readable


def test_every_line_of_the_text_comes_from_the_tracker():
    job_id = save()
    tracker.save_notes(job_id, {"notes": "Ask about on-call."})
    note = "Dear Acme team, I built APIs."
    job = tracker.get_job(job_id)
    saved = "\n".join([job["job"].model_dump_json(), job["best_match"].model_dump_json(),
                       job["company_brief"].model_dump_json(), note, job["notes"], job["posting_text"]])
    ours = {"Interview prep:", "Location:", "Type:", "Level:", "Your resume says:", "Closest in your resume:",
            "Why it counts as a gap:", "Size and stage:", "Product:", "News:", "Culture:", "Source:", "(nice to have)"}
    for line in ip.as_text(sheet(job_id, note)).splitlines():
        if not line.strip() or line.isupper() or line.startswith("WHAT YOUR RESUME PROVES ("):
            continue                                                               # blank lines and our headings
        rest = line.strip().lstrip("- ").strip('"')
        for label in ours:
            rest = rest.replace(label, "")
        rest = rest.replace(" at Acme Robotics", "").strip().strip('"')
        assert rest == "" or rest in saved, f"not from the tracker: {line!r}"


def test_the_text_has_the_sections_in_reading_order():
    text = ip.as_text(sheet(save(), "Dear Acme team"))
    order = ["Interview prep: Backend Engineer at Acme Robotics", "THE ROLE", "WHAT YOU WOULD DO", "WHAT THEY ASK FOR",
             "WHAT YOUR RESUME PROVES", "SHOWN ONLY IN PART", "NOT IN YOUR RESUME", "WORTH BRINGING UP", "THE COMPANY",
             "THE COVER NOTE YOU APPROVED", "THE JOB DESCRIPTION, AS SAVED"]
    places = [text.index(part) for part in order]
    assert places == sorted(places)
    assert '- Python\n  Your resume says: "Built a FastAPI service in Python"' in text
    assert "- Go (nice to have)" in text


def test_the_page_gets_the_sheet_and_can_save_it(tmp_path, monkeypatch):
    api = Api(send=lambda e: None, graph=object())
    job_id = save()
    tracker.add_cover_note(job_id, "Dear Acme team")
    data = api.interview_prep(job_id)
    assert data["cover_note"] == "Dear Acme team" and data["text"].startswith("Interview prep: Backend Engineer at Acme Robotics")
    with pytest.raises(ValueError):
        api.interview_prep(999)
    with pytest.raises(ValueError):
        api.export_interview_prep(job_id, "exe")

    asked = {}
    for fmt in ("txt", "docx", "pdf"):
        target = tmp_path / f"prep.{fmt}"
        monkeypatch.setattr(api, "_save_path", lambda name, kind, target=target: (asked.setdefault(target.suffix, name), target)[1])
        assert api.export_interview_prep(job_id, fmt) == {"path": str(target)}
        assert target.stat().st_size > 500
    assert asked[".pdf"] == "Interview prep - Acme Robotics - Backend Engineer.pdf"
    assert "Kubernetes" in (tmp_path / "prep.txt").read_text(encoding="utf-8")
    with zipfile.ZipFile(tmp_path / "prep.docx") as z:
        assert "Built a FastAPI service in Python" in z.read("word/document.xml").decode("utf-8")
    assert (tmp_path / "prep.pdf").read_bytes().startswith(b"%PDF")
    monkeypatch.setattr(api, "_save_path", lambda name, kind: None)               # you cancelled the dialog
    assert api.export_interview_prep(job_id, "pdf") is None
