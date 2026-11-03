"""15a: the fit eval's own logic (mapping answers to requirements, metrics).
No LLM: answers are written by hand in the shape ResumeMatch.model_dump() has."""

import json

import pytest

from evals import fit as evalfit
from evals.metrics import best_requirement, compare, label_score, predict, stability

REQS = [
    "Python programming",
    "SQL and relational databases such as PostgreSQL",
    "Knowledge of Embedded C/C++ and microcontroller programming",
    "Apache Spark",
]


def answer(matches=(), gaps=(), rejected=(), unsupported=(), score=50):
    return {
        "analysis": {"matching_skills": [{"requirement": r, "resume_evidence": "x"} for r in matches],
                     "missing_skills": list(gaps)},
        "rejected_matches": [{"requirement": r, "resume_evidence": "x"} for r in rejected],
        "unsupported_matches": list(unsupported),
        "fit_score": score,
    }


def test_reworded_items_map_to_their_requirement():
    assert best_requirement("Python", REQS) == 0
    assert best_requirement("Knowledge of SQL databases", REQS) == 1
    assert best_requirement("Experience with Apache Spark", REQS) == 3


def test_an_invented_gap_maps_to_nothing():
    # From job 17: a gap that is in neither of the job's lists.
    assert best_requirement("Firmware development in Embedded C", ["Familiarity with Git and Linux"]) is None


def test_prediction_statuses():
    pred = predict(answer(matches=["Python"], gaps=["Apache Spark", "Kubernetes operators"],
                          rejected=["Embedded C/C++ microcontroller programming"]), REQS)
    assert pred.status == ["proven", "skipped", "lost", "missing"]
    assert pred.invented_gaps == ["Kubernetes operators"]


def test_a_final_match_beats_a_gap_and_the_judge_is_recorded():
    pred = predict(answer(matches=["Python programming"], gaps=["Python programming"],
                          unsupported=["SQL and PostgreSQL - quote is about something else"]), REQS)
    assert pred.status[0] == "proven"
    assert pred.judge_rejected == [1]


def test_compare_counts_false_gaps_matches_and_partials():
    pred = predict(answer(matches=["Python", "Apache Spark"], gaps=["SQL and PostgreSQL databases"]), REQS)
    res = compare(pred, ["proven", "proven", "partial", "missing"], score=40)
    assert res.false_gaps == [1]          # SQL proven, called a gap
    assert res.false_matches == [3]       # Spark missing, called proven
    assert res.not_seen == [2]            # skipped
    assert res.partial_as == {"skipped": 1}
    assert (res.correct, res.hard) == (1, 3)


def test_label_score_shows_the_formulas_ceiling():
    # All 8 required proven, all 8 nice-to-haves missing: today's formula
    # can't go above 77, the number job 16 got (finding F7).
    assert label_score(["proven"] * 8 + ["missing"] * 8, ["required"] * 8 + ["nice"] * 8) == 77
    assert label_score(["proven", "partial"], ["required", "required"]) == 75


def test_partial_answers_are_read_and_count_as_half_a_mistake():
    fit = answer(matches=["Python"], gaps=["Apache Spark"])
    fit["analysis"]["partial_skills"] = [{"requirement": "SQL and PostgreSQL", "resume_evidence": "x"}]
    pred = predict(fit, REQS)
    assert pred.status[:2] == ["proven", "partial"]
    res = compare(pred, ["proven", "proven", "partial", "missing"], score=50)
    assert res.proven_as_partial == [1] and res.false_gaps == []


def test_stability():
    assert stability([["proven", "missing"], ["proven", "missing"]]) == 1.0
    assert stability([["proven", "missing"], ["proven", "proven"]]) == 0.5


def test_the_sample_case_loads_and_matches_its_job():
    case = evalfit.load_case(evalfit.SAMPLE_CASES / "project_only")
    assert len(case["labels"]) == len(case["reqs"]) == 11
    assert "PostgreSQL" in case["resume"]


def test_a_case_with_blank_labels_is_refused(tmp_path):
    (tmp_path / "job.json").write_text(json.dumps(
        {"required_skills": ["Python"], "nice_to_have_skills": []}), encoding="utf-8")
    (tmp_path / "case.json").write_text(json.dumps({"resume": "r.txt", "labels": [
        {"kind": "required", "requirement": "Python", "label": "?"}]}), encoding="utf-8")
    (tmp_path / "r.txt").write_text("Python", encoding="utf-8")
    with pytest.raises(ValueError, match="unlabelled"):
        evalfit.load_case(tmp_path)


def test_a_run_is_scored_from_the_raw_answer(monkeypatch):
    case = evalfit.load_case(evalfit.SAMPLE_CASES / "project_only")
    fake = answer(matches=["Python programming", "Building REST APIs"], gaps=["Apache Spark"], score=60)
    monkeypatch.setattr(evalfit, "run_once", lambda c: {"fit": fake, "seconds": 1.0,
                                                         "tokens": {"input": 10, "output": 5}})
    report = evalfit.run_cases([case], runs=2)
    c = report["cases"]["project_only"]
    assert c["scores"] == [60, 60] and c["stability"] == 1.0
    assert len(c["not_seen"]) == 8           # 8 requirements were never mentioned,
    assert len(c["false_gaps"]) == 7         # 7 of them labelled proven: lost to the score
    assert report["total"]["runs"] == 2
