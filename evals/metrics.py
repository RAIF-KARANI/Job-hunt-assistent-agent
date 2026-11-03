"""
15a: how right was step 2? Pure code, no LLM, so it is unit-tested.

The fit step answers in free text: "matching_skills" with a requirement
written in the model's own words, "missing_skills" as plain strings, plus
the claims the quote check or the judge threw out. The eval set has a hand
label for each of the job's own requirements. This module maps every answer
item back to one of those requirements and compares.

Per requirement, the prediction is one of:
    proven    a final match (passed the quote check and the judge)
    missing   listed as a gap (by the model, or moved there by the judge)
    lost      a claimed match the quote check rejected, and not a gap:
              the score never sees it (finding F3)
    skipped   the answer never mentions it (the score never sees it either)

Hand labels are proven / partial / missing. "partial" is soft: the app
can't say "partial" yet (15b adds it), so partial requirements are left out
of accuracy and counted separately.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from job_agent.fit import NICE_TO_HAVE_WEIGHT, _words

LABELS = ("proven", "partial", "missing")
# An answer item belongs to a requirement if this share of the item's words
# are in it. Lower than the quote check's 0.8: the model rewords requirements.
MAP_THRESHOLD = 0.5


def overlap(item: str, requirement: str) -> float:
    """Share of the item's words that appear in the requirement."""
    words = set(_words(item))
    if not words:
        return 0.0
    return len(words & set(_words(requirement))) / len(words)


def best_requirement(item: str, requirements: list[str]) -> int | None:
    """Index of the requirement this answer item is about, or None (invented)."""
    scores = [overlap(item, r) for r in requirements]
    if not scores:
        return None
    best = max(range(len(scores)), key=lambda i: scores[i])
    return best if scores[best] >= MAP_THRESHOLD else None


@dataclass
class Prediction:
    status: list[str]                 # per requirement: proven / missing / lost / skipped
    invented_gaps: list[str] = field(default_factory=list)  # gaps matching no requirement
    judge_rejected: list[int] = field(default_factory=list)  # requirement indexes


def predict(fit: dict, requirements: list[str]) -> Prediction:
    """Map a ResumeMatch (as a dict) onto the job's requirements."""
    status = ["skipped"] * len(requirements)
    analysis = fit["analysis"]

    for m in fit.get("rejected_matches") or []:
        i = best_requirement(m["requirement"], requirements)
        if i is not None:
            status[i] = "lost"

    invented = []
    for gap in analysis.get("missing_skills") or []:
        i = best_requirement(gap, requirements)
        if i is None:
            invented.append(gap)
        elif status[i] != "proven":
            status[i] = "missing"

    for m in analysis.get("matching_skills") or []:
        i = best_requirement(m["requirement"], requirements)
        if i is not None:
            status[i] = "proven"  # a final match wins over anything else

    judged = []
    for text in fit.get("unsupported_matches") or []:
        # "<requirement> - <the judge's reason>"
        i = best_requirement(text.split(" - ")[0], requirements)
        if i is not None:
            judged.append(i)
    return Prediction(status=status, invented_gaps=invented, judge_rejected=judged)


def label_score(labels: list[str], kinds: list[str]) -> int:
    """The score today's formula would give if every answer matched the labels
    (partial = half proven, half gap). Shows the formula's own ceiling,
    separately from classification mistakes."""
    proven = gaps = 0.0
    for label, kind in zip(labels, kinds):
        weight = 1.0 if kind == "required" else NICE_TO_HAVE_WEIGHT
        have = {"proven": 1.0, "partial": 0.5, "missing": 0.0}[label]
        proven += have
        gaps += (1 - have) * weight
    total = proven + gaps
    return round(100 * proven / total) if total else 0


@dataclass
class RunResult:
    correct: int        # hard labels (proven/missing) the app got right
    hard: int           # number of hard labels
    false_gaps: list[int]      # labelled proven, predicted missing / lost / skipped
    false_matches: list[int]   # labelled missing, predicted proven
    not_seen: list[int]        # predicted lost or skipped (any label)
    partial_as: dict[str, int]  # what the app said for partial labels
    invented_gaps: int
    score: int

    @property
    def accuracy(self) -> float:
        return self.correct / self.hard if self.hard else 1.0


def compare(pred: Prediction, labels: list[str], score: int) -> RunResult:
    correct = hard = 0
    false_gaps, false_matches, not_seen = [], [], []
    partial_as: dict[str, int] = {}
    for i, (said, label) in enumerate(zip(pred.status, labels)):
        if said in ("lost", "skipped"):
            not_seen.append(i)
        if label == "partial":
            partial_as[said] = partial_as.get(said, 0) + 1
            continue
        hard += 1
        if said == label:
            correct += 1
        elif label == "proven":
            false_gaps.append(i)
        elif label == "missing" and said == "proven":
            false_matches.append(i)
    return RunResult(correct, hard, false_gaps, false_matches, not_seen, partial_as,
                     len(pred.invented_gaps), score)


def stability(statuses: list[list[str]]) -> float:
    """Share of requirements given the same answer in every run."""
    if not statuses:
        return 1.0
    same = sum(1 for column in zip(*statuses) if len(set(column)) == 1)
    return same / len(statuses[0]) if statuses[0] else 1.0
