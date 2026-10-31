"""
The resume-improvement prompt (14g, D33): a prompt you paste into another AI
(ChatGPT, Claude...) together with your resume, to make the resume show this
job's requirements better.

NO LLM here: it's a template filled from the analysis already in the tracker,
so it costs nothing and takes no time. Your resume is NOT in it: you paste
yours yourself, so you choose what leaves your PC.

    keyword coverage = the job's required skills your resume visibly shows
                       (a proven match, checked by code and the judge)
    "already fits"   = coverage >= 95 % and no required skill missing:
                       then the screen says so, with a small "Generate anyway"

Coverage is deliberately NOT called an "ATS score": real applicant tracking
systems differ and none of them is simulated here. It's an honest count.

The rules in the prompt matter most: rephrase only real experience, never
invent any. Tests: tests/test_resume_prompt.py.
"""

from job_agent.fit import _words
from job_agent.models import JobPosting, ResumeMatch

FITS_AT = 0.95
SAME_SKILL = 0.8


def _same_skill(a: str, b: str) -> bool:
    """The shorter wording's words are (almost all) in the longer one:
    "SQL" ~ "SQL databases", but not "SQL databases" ~ "NoSQL databases".
    Stricter than fit._similar (half the words), which is fine for sorting
    gaps but would count a skill as shown when it isn't."""
    x, y = set(_words(a)), set(_words(b))
    return bool(x and y) and len(x & y) >= SAME_SKILL * min(len(x), len(y))


def _shown(requirement: str, match: ResumeMatch) -> str | None:
    """The resume quote proving this requirement, or None if it isn't shown."""
    for m in match.analysis.matching_skills:
        if _same_skill(requirement, m.requirement):
            return m.resume_evidence or ""
    return None


def coverage(job: JobPosting, match: ResumeMatch) -> dict:
    """Which of the job's skills the resume shows, in the job's own words."""
    required = [(r, _shown(r, match)) for r in job.required_skills]
    nice = [(r, _shown(r, match)) for r in job.nice_to_have_skills]
    shown = [{"skill": r, "quote": q} for r, q in required if q is not None]
    missing = [r for r, q in required if q is None]
    total = len(required)
    ratio = len(shown) / total if total else 1.0
    return {
        "required_total": total,
        "required_shown": len(shown),
        "ratio": round(ratio, 3),
        "shown": shown,
        "missing": missing,
        "nice_total": len(nice),
        "nice_shown": sum(1 for _, q in nice if q is not None),
        "nice_missing": [r for r, q in nice if q is None],
        # Real quotes the judge said don't prove the claim: the best material to rephrase.
        "unclear": [u.split(" - ", 1)[0] for u in match.unsupported_matches],
        "fits": ratio >= FITS_AT and not missing,
    }


def _bullets(items, empty="(none)") -> str:
    return "\n".join(f"- {item}" for item in items) if items else empty


def build_prompt(job: JobPosting, match: ResumeMatch, cov: dict | None = None) -> str:
    cov = cov or coverage(job, match)
    where = ", ".join(v for v in (job.location, job.seniority, job.employment_type)
                      if v and v != "Not specified")
    shown = [f'{s["skill"]}: "{s["quote"]}"' if s["quote"] else s["skill"] for s in cov["shown"]]
    return f"""I'm applying for the job below and want my resume to show what I really have for it more clearly. My resume is pasted at the end of this message.

THE JOB
{job.title} at {job.company}{f" ({where})" if where else ""}
{job.summary}

Responsibilities:
{_bullets(job.responsibilities)}

Required skills:
{_bullets(job.required_skills)}

Nice to have:
{_bullets(job.nice_to_have_skills)}

WHAT A CHECK OF MY RESUME FOUND
My resume clearly shows {cov["required_shown"]} of the {cov["required_total"]} required skills.

Shown (keep these, and make them easy to find):
{_bullets(shown)}

Required skills my resume doesn't show:
{_bullets(cov["missing"])}

Nice-to-haves it doesn't show:
{_bullets(cov["nice_missing"])}

Mentioned, but not clearly shown:
{_bullets(cov["unclear"])}

RULES (most important)
1. Use ONLY experience that is already in my resume. Never invent or inflate skills, tools, employers, job titles, dates, numbers, results or certificates.
2. You may rephrase, reorder and use the job's own wording for things I really did, so they are easy to find for a recruiter and for applicant tracking systems.
3. If my resume doesn't show a required skill, don't add it. Instead ask me one short question about it, in case I have related experience I left out.
4. Keep my resume's structure, length, language and country conventions, unless something stops it from being read correctly.

WHAT I WANT BACK
a) Concrete edits, each as: section, before -> after, and which requirement it shows.
b) Your questions about the skills my resume doesn't show.
c) The job's keywords my resume should contain word for word, only where they are true for me.

MY RESUME
[paste your resume here]
"""


def resume_prompt(job: JobPosting, match: ResumeMatch) -> dict:
    cov = coverage(job, match)
    return {"resume": match.resume_name, "coverage": cov, "prompt": build_prompt(job, match, cov)}
