"""
15f: which achievements a cover note uses, and where each one belongs.

Pure code, no LLM. Two problems in the 35 cover notes of the installed app
(finding F9):
  - 23 of 35 mentioned CodeLens, whatever the job, because the writer got
    the whole resume and picked the most impressive project every time.
  - Projects moved to the wrong place: "As a Software Engineering Intern, I
    built CodeLens", "At Tap Academy, I built a code review tool". CodeLens
    is a personal project; Tap Academy was Java training.

So code now:
  1. splits the resume into ENTRIES (each project, each job) with the lines
     that belong to it (`resume_entries`),
  2. picks the 2-3 entries whose lines best match THIS job's verified
     requirements, with their best lines (`pick_achievements`), passed to the
     writer as "<project or job>: <facts>",
  3. checks the draft: a sentence that names a project together with an
     employer, role or school must match the resume (`placement_notices`).

The parser is heuristic (resumes have no standard layout); it was tuned on
6 real resumes. When it finds no entries, the cover note works as before
(whole resume + talking points).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Section headings: a short line, mostly capitals, containing one of these.
_SECTIONS = {
    "project": ("PROJECT",),
    "experience": ("EXPERIENCE", "EMPLOYMENT", "INTERNSHIP", "WORK HISTORY"),
    "education": ("EDUCATION",),
    "other": ("SKILL", "SUMMARY", "PROFILE", "CERTIFICATION", "ACHIEVEMENT", "AWARD",
              "PUBLICATION", "LANGUAGE", "INTEREST", "ACTIVITIES", "LEADERSHIP", "OBJECTIVE",
              "VOLUNTEER", "COURSEWORK", "REFERENCES"),
}
_MONTH = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?"
_YEAR = r"(?:19|20)\d\d"
# "Jan 2026 - Jul 2026", "2022 - 2026", "Jun – Jul 2026", "Feb 2025 – Present"
DATE_RANGE = re.compile(
    rf"(?:{_MONTH}\s*)?(?:{_YEAR})?\s*[-–—]\s*(?:{_MONTH}\s*)?(?:{_YEAR}|present|current|now)\b", re.I)
_BULLET = re.compile(r"^[\s•●▪◦■*�·]+")
_VERB_FIRST = {"built", "led", "won", "ran", "wrote", "made", "co-built", "set", "taught", "drove", "grew",
               "cut", "took", "rebuilt", "helped", "owned", "shipped", "hardened", "designing", "building",
               "developing", "leading", "surveying"}
_LINK_TAIL = re.compile(r"\s*(?:(?:live|code|demo|github|link)\s*\|?\s*)+$", re.I)
_ENDS = (".", "!", "?")


@dataclass
class Entry:
    kind: str                    # "project" | "experience" | "education"
    title: str                   # "CodeLens - AI Code Reviewer ..." / "Tap Academy"
    role: str = ""               # experience: the role line ("Software Engineering Intern")
    facts: list[str] = field(default_factory=list)  # sentences that belong to it

    @property
    def name(self) -> str:
        """The short name used in prose: "CodeLens", "Tap Academy"."""
        base = re.split(r"\s+[-–—|]\s+|,\s", self.title)[0]
        return base.strip() or self.title

    @property
    def aliases(self) -> list[str]:
        """Names a sentence may use for this job: the employer, the role, each
        part of "Role – Employer, Place"."""
        parts = [self.name, self.role] + re.split(r"\s+[-–—|]\s+|,\s*", self.title)
        return [p.strip() for p in dict.fromkeys(parts) if p and len(p.strip()) >= 3]

    @property
    def label(self) -> str:
        if self.kind == "experience":
            return f"Work: {self.title}" + (f", as {self.role}" if self.role else "")
        if self.kind == "education":
            return f"Studies: {self.title}"
        return f"Project \"{self.name}\" (a personal / academic project, not done at any employer)"


def _heading(line: str) -> str | None:
    letters = [c for c in line if c.isalpha()]
    if not letters or len(line) > 45 or sum(c.isupper() for c in letters) / len(letters) < 0.8:
        return None
    upper = line.upper()
    for kind, words in _SECTIONS.items():
        if any(w in upper for w in words):
            return kind
    return None


# Words ending in -ed that start titles, not achievements ("Embedded / IoT
# Intern", "Vision-Guided Robotic Arm").
_NOT_VERBS = {"embedded", "automated", "distributed", "advanced", "integrated", "connected", "unified",
              "guided", "based", "red", "speed", "seed", "need", "feed"}


def _starts_with_verb(line: str) -> bool:
    first = line.split()[0].lower().strip(",.:;") if line.split() else ""
    if first in _NOT_VERBS or "-" in first and not first.startswith("co-"):
        return False
    return first.endswith("ed") or first in _VERB_FIRST


def _is_tech_list(line: str) -> bool:
    """"Python, FastAPI, Celery, Redis, ..." - a list of names, not a sentence."""
    commas = line.count(",")
    return (commas >= 3 and not line.rstrip().endswith(".") and not _starts_with_verb(line)
            and len(line.split()) / (commas + 1) <= 4)


def _looks_like_title(text: str) -> bool:
    """A project title: short, starts with a capital or a digit ("5-DOF Arm"),
    or "name - description" ("my-rag - Personal RAG Assistant")."""
    text = _LINK_TAIL.sub("", text)  # "... GitHub App Live | Code"
    named = text[:1].isupper() or text[:1].isdigit() or bool(re.match(r"^\S+\s+[-–—]\s+", text))
    return (named and len(text.split()) <= 14 and not _is_tech_list(text)
            and not _starts_with_verb(text) and not text.rstrip().endswith("."))


def resume_entries(resume_text: str) -> list[Entry]:
    """Projects, jobs and studies with the sentences that belong to each, in order."""
    entries: list[Entry] = []
    section: str | None = None
    current: Entry | None = None
    sentence = ""

    def flush() -> None:
        nonlocal sentence
        if current is not None and sentence.strip():
            current.facts.append(re.sub(r"\s+([.,;:])", r"\1", sentence.strip()))
        sentence = ""

    for raw in resume_text.splitlines():
        line = raw.strip()
        if not line:
            continue
        kind = _heading(line)
        if kind:
            flush()
            section, current = kind, None
            continue
        if section not in ("project", "experience", "education"):
            continue
        bullet = bool(_BULLET.match(line))
        text = _BULLET.sub("", line).strip()
        if not text:
            continue
        # A wrapped line: the sentence so far hasn't ended, and this line
        # doesn't start a new bullet or a new achievement ("Built ...").
        # A lowercase start always continues ("raised F1 from ...").
        wrapped = bool(sentence) and not sentence.rstrip().endswith(_ENDS) and not bullet \
            and (text[:1].islower() or not _starts_with_verb(text))
        if section in ("experience", "education"):
            header = not bullet and not wrapped and bool(DATE_RANGE.search(text))
        else:
            finished = current is None or (not sentence) or sentence.rstrip().endswith(_ENDS)
            header = not bullet and not wrapped and finished and _looks_like_title(text) \
                and (current is None or bool(current.facts) or bool(sentence))
        if header:
            flush()
            title = DATE_RANGE.sub("", text).strip(" ,|–—-")
            current = Entry(kind=section, title=_LINK_TAIL.sub("", title).strip())
            entries.append(current)
            continue
        if current is None:
            continue
        if not current.facts and not sentence and _is_tech_list(text):
            continue  # the project's tech line
        if section == "experience" and not current.role and not current.facts and not sentence \
                and len(text.split()) <= 8 and not text.endswith(".") and not re.search(r"[·|,]", text):
            current.role = text
            continue
        if wrapped:
            sentence += " " + text
        else:
            flush()
            sentence = text
    flush()
    return [e for e in entries if e.facts or e.kind == "experience"]


# ---------------------------------------------------------------------------
# Picking what the note talks about
# ---------------------------------------------------------------------------

_FILLER = {"a", "an", "and", "as", "for", "in", "of", "on", "or", "the", "to", "with", "by", "at", "from",
           "experience", "knowledge", "familiarity", "understanding", "strong", "basic", "good", "solid",
           "skills", "ability", "working", "using", "development", "developing", "design", "systems", "tools",
           "proficiency", "hands", "related", "field", "years", "year", "plus", "etc", "such", "like"}


def _terms(text: str) -> set[str]:
    return {w.strip(".") for w in re.findall(r"[a-z0-9+#.]+", text.lower())} - _FILLER - {""}


@dataclass
class Achievement:
    entry: Entry
    facts: list[str]
    score: int


def pick_achievements(entries: list[Entry], requirements: list[str], evidence: list[str] = (),
                      most: int = 3, facts_each: int = 2) -> list[Achievement]:
    """The entries whose lines best match this job's verified requirements.
    Each fact scores its overlap with the requirement terms; a quote the fit
    step verified counts extra (it proves a requirement)."""
    wanted = set().union(*(_terms(r) for r in requirements)) if requirements else set()
    proof = [e.lower()[:60] for e in evidence if len(e) > 12]
    picked = []
    for entry in entries:
        if entry.kind == "education":
            continue
        scored = []
        for fact in entry.facts:
            hits = len(_terms(fact) & wanted) + 3 * sum(1 for p in proof if p in fact.lower())
            scored.append((hits, fact))
        scored.sort(key=lambda s: -s[0])
        best = [(h, f) for h, f in scored[:facts_each] if h > 0]
        if best:
            picked.append(Achievement(entry, [f for _, f in best], sum(h for h, _ in best)))
    picked.sort(key=lambda a: -a.score)
    return picked[:most]


def achievements_text(picked: list[Achievement]) -> str:
    return "\n".join(f"- {a.entry.label}: " + " ".join(a.facts) for a in picked)


# ---------------------------------------------------------------------------
# Checking the draft
# ---------------------------------------------------------------------------

_SCHOOL_WORDS = ("university", "college", "my studies", "my degree", "coursework")
# A project put in an unnamed job: "At my last role, I developed <project>"
# (15f eval, Intel note).
_WORK_WORDS = ("my last role", "my current role", "my previous role", "my role as", "my last job",
               "my current job", "my previous job", "my internship", "during my intern", "as an intern",
               "at work", "my employer", "my team at", "professionally")


def placement_notices(note: str, entries: list[Entry]) -> list[str]:
    """Sentences that put a project at an employer, in a role, or at a school
    the resume doesn't connect it to. Returns readable notices."""
    projects = [e for e in entries if e.kind == "project" and len(e.name) >= 3]
    jobs = [e for e in entries if e.kind == "experience"]
    notices = []
    for sentence in re.split(r"(?<=[.!?])\s+", note):
        low = sentence.lower()
        named = [p for p in projects if p.name.lower() in low]
        if not named:
            continue
        for job in jobs:
            if any(a.lower() in low for a in job.aliases):
                inside = " ".join([job.title] + job.facts).lower()
                for p in named:
                    if p.name.lower() not in inside:
                        notices.append(f"“{p.name}” is a project in your resume, not work at {job.name}"
                                       + (f" or as {job.role}" if job.role else "") + ": check this sentence.")
        if any(w in low for w in _SCHOOL_WORDS):
            for p in named:
                notices.append(f"“{p.name}” isn't listed as university work in your resume: check this sentence.")
        if any(w in low for w in _WORK_WORDS):
            for p in named:
                if not any(p.name.lower() in " ".join([j.title] + j.facts).lower() for j in jobs):
                    notices.append(f"“{p.name}” is a project in your resume, not part of a job: check this sentence.")
    return list(dict.fromkeys(notices))
