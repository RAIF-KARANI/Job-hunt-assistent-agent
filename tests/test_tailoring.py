"""
Tests for resume tailoring (19d, E7). The model is replaced by a stand-in;
what's tested is the code check that every suggestion passes before you see
it: the "before" line is really yours, and the "after" adds no number,
skill or name your resume doesn't show.
"""

import pytest

from desktop_web.bridge import Api
from job_agent import paths, tailoring, tracker
from job_agent.models import FitAnalysis, JobPosting, ResumeMatch, SkillMatch
from job_agent.tailoring import BulletEdit

RESUME = """Raif Karani
AI Engineer
EXPERIENCE
Acme Labs, Software Engineer (2023-2025)
• Built a retrieval pipeline in Python with LangGraph for 3 internal teams
• Cut report generation time by 40% using async jobs
• Wrote unit tests with pytest and reviewed pull requests
SKILLS
Python, LangGraph, SQL, Docker
"""

JOB = JobPosting(title="LLM Engineer", company="Northwind", location="Remote", employment_type="Full-time",
                 seniority="Mid", salary="Not specified", summary="s",
                 required_skills=["Python", "RAG pipelines", "Kubernetes"], nice_to_have_skills=["AWS"],
                 responsibilities=["build agents"])


def edit(before, after, requirement="RAG pipelines"):
    return BulletEdit(before=before, after=after, requirement=requirement, why="shows it")


def reasons(e):
    return tailoring.problems(e, JOB, RESUME)


# ---- the check -------------------------------------------------------------


def test_a_faithful_rewrite_passes():
    e = edit("Built a retrieval pipeline in Python with LangGraph for 3 internal teams",
             "Built a Python retrieval pipeline with LangGraph, used by 3 internal teams")
    assert reasons(e) == []


def test_the_jobs_word_needs_the_fit_check_to_have_verified_it():
    e = edit("Built a retrieval pipeline in Python with LangGraph for 3 internal teams",
             "Built a Python RAG pipeline with LangGraph for 3 internal teams")
    assert reasons(e) == ["adds “RAG”, not in your resume"]  # "retrieval pipeline" may not be RAG: code can't tell
    assert tailoring.problems(e, JOB, RESUME, verified=["RAG pipelines"]) == []  # the fit check proved it


def test_a_before_line_that_is_not_in_the_resume_is_dropped():
    assert reasons(edit("Led a team of 12 engineers at Google", "Led 12 engineers")) == ["the “before” line isn't in your resume"]


def test_a_pdf_that_glued_words_together_still_counts_as_yours():
    glued = RESUME.replace("Wrote unit tests with pytest", "Wrote unittests withpytest")
    e = edit("Wrote unit tests with pytest and reviewed pull requests", "Wrote pytest unit tests and reviewed pull requests")
    assert tailoring.problems(e, JOB, glued) == []


def test_no_new_numbers():
    e = edit("Cut report generation time by 40% using async jobs", "Cut report generation time by 60% for 200 users using async jobs")
    assert reasons(e) == ["adds a number your line doesn't have (200, 60)", "leaves out your number 40"]


def test_a_number_from_elsewhere_in_the_resume_is_still_new_to_the_line():
    e = edit("Cut report generation time by 40% using async jobs", "Cut report generation time by 40% for 3 teams using async jobs")
    assert reasons(e) == ["adds a number your line doesn't have (3)"]


def test_no_job_skill_the_resume_does_not_show():
    e = edit("Wrote unit tests with pytest and reviewed pull requests",
             "Wrote unit tests with pytest, deployed on kubernetes, and reviewed pull requests")
    assert reasons(e) == ["adds “Kubernetes”, which your resume doesn't show"]


def test_no_new_tool_or_name():
    e = edit("Wrote unit tests with pytest and reviewed pull requests",
             "Wrote unit tests with pytest in GitHub Actions CI and reviewed pull requests")
    assert reasons(e) == ["adds “GitHub”, “Actions”, “CI”, not in your resume"]


def test_nothing_of_yours_is_left_out():
    e = edit("Built a retrieval pipeline in Python with LangGraph for 3 internal teams", "Built a retrieval pipeline for internal teams")
    assert reasons(e) == ["leaves out your number 3", "leaves out “Python”, “LangGraph”"]


def test_about_does_not_become_exact():
    resume = RESUME + "• Posts review comments about 40 seconds after a push\n"
    e = edit("Posts review comments about 40 seconds after a push", "Posts review comments within 40 seconds of a push")
    assert tailoring.problems(e, JOB, resume) == ["makes “about 40” sound exact"]


def test_hyphenated_and_plural_forms_of_your_words_are_yours():
    resume = RESUME + "• Applied MVC practices to UI work\n"
    e = edit("Applied MVC practices to UI work", "Applied MVC-based practices to UIs")
    assert tailoring.problems(e, JOB, resume) == []


def test_a_skill_the_resume_shows_elsewhere_may_be_named():
    # Docker is in the SKILLS line: naming it is not an invention (you can still judge the placement).
    e = edit("Cut report generation time by 40% using async jobs", "Cut report generation time by 40% using async jobs in Docker")
    assert reasons(e) == []


def test_no_change_is_dropped():
    line = "Cut report generation time by 40% using async jobs"
    assert reasons(edit(line, line + ".")) == ["no change"]


def test_check_keeps_the_good_drops_the_bad_and_says_why():
    edits = [
        edit("Built a retrieval pipeline in Python with LangGraph for 3 internal teams", "Built a Python retrieval pipeline with LangGraph for 3 internal teams"),
        edit("Built a retrieval pipeline in Python with LangGraph for 3 internal teams", "Built a retrieval pipeline with LangGraph in Python for 3 teams"),
        edit("Cut report generation time by 40% using async jobs", "Cut report time by 90%"),
    ]
    kept, dropped = tailoring.check(edits, JOB, RESUME)
    assert len(kept) == 1
    assert [d["reasons"][0] for d in dropped] == ["the same line twice", "adds a number your line doesn't have (90)"]


# ---- the whole step, the log, the bridge ------------------------------------


@pytest.fixture
def saved_job(tmp_path, monkeypatch):
    monkeypatch.setattr(tracker, "DB_PATH", tmp_path / "jobs.db")
    analysis = FitAnalysis(matching_skills=[SkillMatch(requirement="Python", resume_evidence="Python, LangGraph, SQL, Docker"),
                                            SkillMatch(requirement="RAG pipelines", resume_evidence="Built a retrieval pipeline")],
                           missing_skills=["Kubernetes"], talking_points=[], verdict="ok")
    return tracker.save_job("https://jobs.example/1", JOB, ResumeMatch(resume_name="Raif_CV", analysis=analysis, fit_score=70), None)


def fake_model(*_):
    return [edit("Built a retrieval pipeline in Python with LangGraph for 3 internal teams",
                 "Built a Python RAG pipeline with LangGraph for 3 internal teams"),
            edit("Cut report generation time by 40% using async jobs", "Cut report generation time by 40% on AWS")]


def test_tailor_checks_and_logs_for_evals(saved_job, monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "test-model")
    result = tailoring.tailor(saved_job, RESUME, suggest_fn=fake_model)
    assert result["resume"] == "Raif_CV" and len(result["edits"]) == 1
    assert result["dropped"][0]["reasons"] == ["adds “AWS”, which your resume doesn't show"]
    s = tailoring.stats()
    assert (s["runs"], s["suggested"], s["kept"], s["dropped"], s["drop_rate"]) == (1, 2, 1, 1, 0.5)
    assert s["reasons"] == {"added a skill or name": 1}
    assert tailoring.stats("another-model")["runs"] == 0


def test_the_bridge_reads_the_resume_and_refuses_during_a_run(saved_job, tmp_path, monkeypatch):
    api = Api(send=lambda e: None, graph=object())
    monkeypatch.setattr(paths, "DATA_DIR", tmp_path)
    with pytest.raises(ValueError, match="isn't in JobLens any more"):
        api.tailor_resume(saved_job)

    api._runner._thread = type("T", (), {"is_alive": lambda self: True})()
    with pytest.raises(RuntimeError, match="agent is working"):
        api.tailor_resume(saved_job)
