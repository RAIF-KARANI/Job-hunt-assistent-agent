"""15c: fairer checks. Glued PDF text, a second look at bad quotes and at
gaps whose terms are in the resume, a three-way judge, the years rule.
Fake LLMs only: these check the wiring, not a model's answers."""

import re

from langchain_core.messages import HumanMessage

from job_agent import fit
from job_agent.models import (
    FitAnalysis,
    JobPosting,
    RequirementCheck,
    RequirementReview,
    ResumeMatch,
    SkillMatch,
)

# How the friend's PDF really reads: the heading is glued to the list.
RESUME = """TECHNICAL SKILLS
LanguagesEmbedded C/C++, C, Python, Verilog
DSP, ML and VisionFFT, spectral analysis, PyTorch, scikit-learn, OpenCV, ArUco
Robotics, Hardware and ToolsInverse kinematics, soldering, Linux, Git"""


def job(required, nice=()):
    return JobPosting(title="Engineer", company="Acme", location="Remote", employment_type="Full-time",
                      seniority="Entry", salary="Not specified", summary="Build things.",
                      required_skills=list(required), nice_to_have_skills=list(nice), responsibilities=[])


def listed_ids(human: str) -> list[int]:
    part = human.split("=== REQUIREMENTS TO CHECK ===")[1]
    return [int(m) for m in re.findall(r"^(\d+)\.", part, re.M)]


class Script:
    """Answers per call from a list of {id: (status, quote)}; records prompts."""

    def __init__(self, *rounds):
        self.rounds, self.prompts = list(rounds), []

    def __call__(self, schema):
        assert schema is RequirementReview
        return self

    def invoke(self, messages):
        human = next(m.content for m in messages if isinstance(m, HumanMessage))
        self.prompts.append(human)
        answers = self.rounds.pop(0)
        return RequirementReview(checks=[
            RequirementCheck(id=i, status=answers[i][0], resume_evidence=answers[i][1], reason="r")
            for i in listed_ids(human)])


def test_a_quote_across_a_glued_heading_is_real():
    assert fit.is_evidence_in_resume("Languages: Embedded C/C++, C, Python", RESUME)
    assert not fit.is_evidence_in_resume("Languages: Rust, Go, Python", RESUME)


def test_a_short_letters_match_is_not_enough():
    # "C, Go" -> "cgo": too short to trust a letters-only match.
    assert not fit.is_evidence_in_resume("C, Go", "Arduino C/C++ firmware; Go-kart club")


def test_gap_hint_finds_the_lines_with_the_key_terms():
    hint = fit.gap_hint("Knowledge of OpenCV and computer vision", RESUME)
    assert "OpenCV" in hint and "Inverse kinematics" not in hint
    assert fit.gap_hint("Experience with Apache Spark", RESUME) == ""
    # Generic words alone never trigger a second look.
    assert fit.gap_hint("Strong experience and knowledge", "Strong experience in sales") == ""


def test_a_bad_quote_and_a_suspicious_gap_get_one_second_look(monkeypatch):
    j = job(["Python", "OpenCV", "Apache Spark"])
    script = Script(
        {0: ("proven", "Python developer for 5 years"),   # not in the resume
         1: ("missing", ""),                               # but OpenCV is in the resume
         2: ("missing", "")},                              # really missing: no second look
        {0: ("proven", "Embedded C/C++, C, Python"), 1: ("proven", "OpenCV, ArUco")},
    )
    monkeypatch.setattr(fit, "structured_llm", script)
    match = fit.assess_resume(j, RESUME)
    assert len(script.prompts) == 2
    second = script.prompts[1]
    assert listed_ids(second) == [0, 1]
    assert "is not in the resume" in second and "OpenCV" in second.split("Note:")[2]
    assert [m.requirement for m in match.analysis.matching_skills] == ["Python", "OpenCV"]
    assert match.analysis.missing_skills == ["Apache Spark"]
    assert [m.requirement for m in match.rejected_matches] == ["Python"]  # still counted as caught


def test_a_quote_still_wrong_after_the_second_look_is_a_gap_not_lost(monkeypatch):
    j = job(["Rust"])
    monkeypatch.setattr(fit, "structured_llm", Script(
        {0: ("proven", "Rust expert since 2019")}, {0: ("proven", "Rust expert since 2019")}))
    match = fit.assess_resume(j, RESUME)
    assert match.analysis.missing_skills == ["Rust"]
    assert match.analysis.gap_reasons["Rust"] == "its quote isn't in the resume"


def test_one_common_term_is_not_enough_for_a_long_requirement():
    # 15c measurement: "power" (EEG band-power) sent battery design for a
    # second look, and the model then called it partial.
    resume = "extracted theta, alpha, and beta band-power features"
    assert fit.gap_hint("Knowledge of battery-powered design: sleep modes, power profiling", resume) == ""
    assert fit.gap_hint("Power profiling and sleep modes on battery devices", "power profiling of sleep modes") != ""


def test_the_judge_is_told_a_skills_list_is_proof():
    assert "skills list counts" in fit.JUDGE_PROMPT


def test_years_need_years_in_the_quote():
    def proven(req, quote):
        return ResumeMatch(resume_name="cv", analysis=FitAnalysis(
            matching_skills=[SkillMatch(requirement=req, resume_evidence=quote)], missing_skills=[],
            talking_points=[]))
    capped = fit.cap_years(proven("3+ years of embedded firmware", "developed Arduino C/C++ firmware"))
    assert capped.analysis.matching_skills == [] and len(capped.analysis.partial_skills) == 1
    assert "years" in capped.analysis.gap_reasons["3+ years of embedded firmware"]
    kept = fit.cap_years(proven("3+ years of embedded firmware", "Firmware engineer, 2021 - 2025"))
    assert len(kept.analysis.matching_skills) == 1
    assert fit.cap_years(proven("Python", "Python")).analysis.partial_skills == []
