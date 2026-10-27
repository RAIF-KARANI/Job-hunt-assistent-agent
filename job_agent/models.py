"""
Data models: the "shapes" of data that flow through the agent.

Why Pydantic models?
    LLMs produce free text, but code needs predictable data. A Pydantic model
    is a strict form: when we call `llm.with_structured_output(JobPosting)`,
    LangChain sends this schema to the model and parses the reply into a real
    Python object. If a field is missing or the wrong type, Pydantic raises an
    error instead of letting bad data flow into the tracker.

    The `description=` on each Field is not just documentation: it is sent to
    the LLM as part of the schema, so it acts as an instruction for that field.
"""

from pydantic import BaseModel, Field


class JobPosting(BaseModel):
    """Structured information extracted from a job posting page."""

    title: str = Field(description="Exact job title, e.g. 'Senior Backend Engineer'")
    company: str = Field(description="Name of the hiring company")
    location: str = Field(
        description="City/country, and whether it's remote, hybrid or on-site. "
        "Use 'Not specified' if missing."
    )
    employment_type: str = Field(
        description="Full-time, part-time, contract, internship, or 'Not specified'"
    )
    seniority: str = Field(
        description="Junior, mid, senior, lead, etc. Infer from title/years "
        "of experience if not stated; 'Not specified' if unclear."
    )
    salary: str = Field(description="Salary or pay range as written, or 'Not specified'")
    summary: str = Field(description="2-3 sentence summary of what the role is about")
    required_skills: list[str] = Field(
        description="Must-have skills, tools and qualifications, as short items"
    )
    nice_to_have_skills: list[str] = Field(
        description="Preferred / bonus skills. Empty list if none are mentioned."
    )
    responsibilities: list[str] = Field(
        description="Main day-to-day responsibilities, as short items"
    )


class SkillMatch(BaseModel):
    """One job requirement + proof from the resume that the candidate has it."""

    requirement: str = Field(description="The job requirement, in a few words")
    resume_evidence: str = Field(
        description="A short phrase (3-12 words) copied EXACTLY from the resume "
        "that proves this requirement. Must be a real quote, not a summary."
    )


class FitAnalysis(BaseModel):
    """How well ONE resume matches ONE job. Produced by the LLM in Phase 2."""

    # Field order matters: the model writes fields top to bottom, so asking for
    # evidence (skills, gaps) BEFORE the score makes the score better grounded.
    matching_skills: list[SkillMatch] = Field(
        description="ONLY requirements the resume proves. Never list a missing "
        "skill here; put those in missing_skills."
    )
    missing_skills: list[str] = Field(
        description="Required skills/qualifications NOT shown anywhere in the resume"
    )
    talking_points: list[str] = Field(
        description="3-5 short, specific achievements or projects FROM THE RESUME "
        "(with numbers if the resume has them) worth highlighting for THIS job"
    )
    fit_score: int = Field(
        ge=0,
        le=100,
        description="0-100. 80+ strong match, 60-79 good, 40-59 partial, <40 weak. "
        "Weigh required skills much more than nice-to-haves.",
    )
    verdict: str = Field(
        description="One honest sentence: should the candidate apply, and why?"
    )


class CompanyBrief(BaseModel):
    """Short company research summary. Produced by the LLM in Phase 3."""

    what_they_do: str = Field(
        description="2-3 sentences: what the company does and for whom"
    )
    products: list[str] = Field(description="Main products or services")
    size_and_stage: str = Field(
        description="Employees, funding stage / public, founding year, HQ - "
        "whatever the research found. 'Unknown' if not found."
    )
    recent_news: list[str] = Field(
        description="Up to 4 notable recent events (launches, funding, "
        "acquisitions, results), each with its date if known"
    )
    culture_and_values: list[str] = Field(
        description="Stated values, work style (e.g. remote, async), mission"
    )
    cover_note_hooks: list[str] = Field(
        description="2-3 specific, concrete facts (a recent launch, a product "
        "direction, a stated value) that connect the company to the applicant's "
        "role. NOT marketing slogans or generic descriptions."
    )
    sources: list[str] = Field(
        description="URLs the facts came from. Only URLs that appeared in the "
        "search results."
    )


class ResumeMatch(BaseModel):
    """A FitAnalysis plus which resume it was for. Built by code, not the LLM."""

    resume_name: str
    analysis: FitAnalysis  # only contains matches that passed verification
    rejected_matches: list[SkillMatch] = []  # claims whose evidence wasn't found
