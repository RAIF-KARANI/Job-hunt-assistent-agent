"""
Tests for the resume-improvement prompt (14g): an honest keyword coverage,
the "already fits" rule, a prompt that forbids inventing experience, no AI
call, and no resume text in it.
"""

import pytest

from desktop_web.bridge import Api
from job_agent import llm, tracker
from job_agent.models import FitAnalysis, JobPosting, ResumeMatch, SkillMatch
from job_agent.resume_prompt import coverage, resume_prompt

JOB = JobPosting(
    title="AI Engineer", company="Northwind", location="Dubai, hybrid", employment_type="Full-time",
    seniority="Junior", salary="Not specified", summary="Build LLM features for logistics.",
    required_skills=["Python", "LangGraph agents", "SQL databases", "Docker"],
    nice_to_have_skills=["Kubernetes"],
    responsibilities=["Ship agent features", "Evaluate models"],
)


def match(proven, unsupported=()):
    analysis = FitAnalysis(
        matching_skills=[SkillMatch(requirement=r, resume_evidence=q) for r, q in proven],
        missing_skills=[], talking_points=[], verdict="ok")
    return ResumeMatch(resume_name="AI_Engineer.pdf", analysis=analysis, fit_score=70,
                       unsupported_matches=list(unsupported))


PARTIAL = match([("Python", "Built FastAPI services in Python"), ("LangGraph", "multi-agent LangGraph workflows")],
                unsupported=["Docker - the quote mentions containers but not Docker"])


def test_coverage_counts_the_jobs_own_required_skills():
    cov = coverage(JOB, PARTIAL)
    assert (cov["required_shown"], cov["required_total"], cov["ratio"]) == (2, 4, 0.5)
    assert cov["missing"] == ["SQL databases", "Docker"]           # in the job's own words
    assert cov["shown"][0] == {"skill": "Python", "quote": "Built FastAPI services in Python"}
    assert (cov["nice_shown"], cov["nice_missing"]) == (0, ["Kubernetes"])
    assert cov["unclear"] == ["Docker"] and cov["fits"] is False


def test_every_required_skill_shown_means_it_already_fits():
    full = match([("Python", "Python"), ("LangGraph agents", "LangGraph agents"),
                  ("SQL", "SQL databases (PostgreSQL)"), ("Docker", "Docker images")])
    cov = coverage(JOB, full)
    assert cov["ratio"] == 1.0 and cov["fits"] is True
    assert cov["nice_missing"] == ["Kubernetes"]       # a nice-to-have doesn't block "fits"


def test_one_missing_required_skill_never_fits_even_on_a_long_list():
    job = JOB.model_copy(update={"required_skills": [f"skill{i} tool" for i in range(30)]})
    proven = match([(f"skill{i} tool", "q") for i in range(29)])
    cov = coverage(job, proven)
    assert cov["ratio"] > 0.95 and cov["fits"] is False


def test_a_similar_looking_skill_isnt_counted_as_shown():
    nosql = match([("NoSQL databases", "MongoDB"), ("Docker Compose", "docker compose files")])
    cov = coverage(JOB, nosql)
    assert "SQL databases" in cov["missing"]           # NoSQL isn't SQL
    assert "Docker" not in cov["missing"]              # but Docker Compose shows Docker


def test_the_prompt_has_the_rules_the_job_and_the_findings_but_no_resume():
    result = resume_prompt(JOB, PARTIAL)
    text = result["prompt"]
    assert "Never invent or inflate" in text and "Use ONLY experience that is already in my resume" in text
    assert "AI Engineer at Northwind (Dubai, hybrid, Junior, Full-time)" in text
    assert "shows 2 of the 4 required skills" in text
    assert '- Python: "Built FastAPI services in Python"' in text
    assert "- SQL databases\n- Docker" in text
    assert "[paste your resume here]" in text           # you paste it; JobLens never does
    assert "ATS score" not in text


def test_the_bridge_builds_it_from_the_tracker_without_any_ai(tmp_path, monkeypatch):
    monkeypatch.setattr(tracker, "DB_PATH", tmp_path / "jobs.db")
    monkeypatch.setattr(llm, "get_llm", lambda *a, **k: pytest.fail("no AI call for the prompt"))
    job_id = tracker.save_job("https://jobs.example/1", JOB, PARTIAL, None)
    data = Api(send=lambda e: None, graph=object()).resume_prompt(job_id)
    assert data["resume"] == "AI_Engineer.pdf" and data["coverage"]["required_shown"] == 2
    assert data["prompt"].startswith("I'm applying for the job below")
    with pytest.raises(ValueError):
        Api(send=lambda e: None, graph=object()).resume_prompt(999)
