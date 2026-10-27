"""
Tests for the fit score computed in code (Phase 8a).

score = proven / (proven + required gaps + 0.3 x nice-to-have gaps)
"""

from job_agent.fit import compute_fit_score
from job_agent.models import FitAnalysis, JobPosting, ResumeMatch, SkillMatch


def _job(nice_to_have=()):
    return JobPosting(
        title="Backend Engineer", company="Acme", location="Remote",
        employment_type="Full-time", seniority="Mid", salary="Not specified",
        summary="s", required_skills=["Python", "APIs", "LangGraph"],
        nice_to_have_skills=list(nice_to_have), responsibilities=["code"],
    )


def _analysis(proven: int, gaps: list[str]):
    skills = [SkillMatch(requirement=f"skill {i}", resume_evidence="q") for i in range(proven)]
    return FitAnalysis(
        matching_skills=skills, missing_skills=gaps, talking_points=[], verdict="ok",
    )


def test_all_requirements_proven_scores_100():
    score, _ = compute_fit_score(_analysis(4, []), _job())
    assert score == 100


def test_nothing_proven_scores_0():
    score, _ = compute_fit_score(_analysis(0, ["Python", "APIs"]), _job())
    assert score == 0


def test_empty_analysis_does_not_crash():
    score, _ = compute_fit_score(_analysis(0, []), _job())
    assert score == 0


def test_required_gaps_count_fully():
    # 4 proven, 2 required gaps -> 4 / 6 = 67
    score, _ = compute_fit_score(_analysis(4, ["LangGraph", "communication"]), _job())
    assert score == 67


def test_nice_to_have_gaps_hurt_less():
    # Job #1's real situation: the Ruby/Vue gap is a nice-to-have, reworded.
    job = _job(nice_to_have=["Familiarity with Ruby on Rails and/or JavaScript and Vue"])
    gaps = ["LangGraph", "communication", "Familiarity with Ruby on Rails and Vue"]
    score, breakdown = compute_fit_score(_analysis(4, gaps), job)
    # 4 / (4 + 2 + 0.3 x 1) = 63
    assert score == 63
    assert "2 required gaps" in breakdown and "1 nice-to-have gaps" in breakdown


def test_same_facts_always_give_the_same_score():
    # The whole point: unlike the LLM's number, this is deterministic.
    analysis = _analysis(3, ["Rust"])
    assert compute_fit_score(analysis, _job()) == compute_fit_score(analysis, _job())


def test_old_rows_without_a_score_still_load():
    # A ResumeMatch saved before Phase 8a has the LLM's old fit_score inside
    # the analysis JSON and no computed score: it must still load.
    old_json = (
        '{"resume_name": "cv", "analysis": {"matching_skills": [], '
        '"missing_skills": [], "talking_points": [], "fit_score": 85, "verdict": "ok"}}'
    )
    match = ResumeMatch.model_validate_json(old_json)
    assert match.fit_score == 0  # filled in later by `python main.py rescore`
