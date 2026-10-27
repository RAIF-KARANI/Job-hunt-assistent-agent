"""
Phase 5: draft a cover note and get HUMAN APPROVAL before saving it.

New ideas in this file:

1. Human-in-the-loop with LangGraph's interrupt()
   The review node calls interrupt(draft). The graph STOPS right there and
   returns control to our program, which shows you the draft. When you
   answer, the program resumes the graph with Command(resume=your_answer)
   and it continues exactly where it stopped.

2. Checkpointer
   To resume later, LangGraph must remember the paused state (the draft,
   the job, the revision count...). A checkpointer saves it after every node,
   keyed by a thread_id. We use the in-memory one here; Phase 6 can switch
   to a SQLite checkpointer so a paused run even survives a restart.

3. Guardrail in code
   save_cover_note() REFUSES to save unless approved=True. The rule is
   enforced by code, so no prompt mistake or model misbehavior can bypass it.

4. Flag, don't fix
   Numbers in the draft that don't appear in your resume / the research are
   shown to you as warnings. In prose we can't safely delete them, so the
   human (you) makes the call - that's what the review step is for.

The graph:

    START -> draft -> review --approve--> save -> END
               ^        |
               +--edit--+
                        +--reject--> END   (nothing saved)
"""

import re
from pathlib import Path
from typing import TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from job_agent.llm import structured_llm
from job_agent.models import CompanyBrief, CoverNote, JobPosting, ResumeMatch
from job_agent.resume import DATA_DIR
from job_agent.tracker import add_cover_note, update_status

NOTES_DIR = DATA_DIR / "cover_notes"

# ---------------------------------------------------------------------------
# 1. DRAFTING (LLM)
# ---------------------------------------------------------------------------

WRITER_PROMPT = """You write short, specific cover notes for job applications.
Write in the FIRST PERSON as the candidate.
Rules:
- 150-220 words, 3 short paragraphs, start with "Dear Hiring Team,".
- Paragraph 1: the role, and ONE genuine reason for interest in this company
  (a product, direction or value - never stock prices, outages or lawsuits).
- Paragraph 2: 2-3 concrete achievements FROM THE RESUME that match the job's
  requirements. Use numbers only if they appear in the resume.
- Paragraph 3: short, confident close. Sign off with the candidate's name.
- Never claim skills or experience the resume doesn't show.
- No clichés ("I am writing to express my interest", "team player",
  "passionate"). No placeholders like [Company]."""


def draft_cover_note(
    job: JobPosting,
    best_match: ResumeMatch,
    company: CompanyBrief | None,
    resume_text: str,
    previous_draft: str = "",
    feedback: str = "",
) -> CoverNote:
    """One LLM call. On a revision, the previous draft + your feedback are included."""
    fit = best_match.analysis
    verified = "\n".join(
        f"- {m.requirement}: \"{m.resume_evidence}\"" for m in fit.matching_skills
    )
    company_info = company.model_dump_json(indent=2) if company else "No research available."

    prompt = (
        f"=== JOB ===\n{job.model_dump_json(indent=2)}\n\n"
        f"=== VERIFIED MATCHES (requirement: resume quote) ===\n{verified}\n\n"
        f"=== SUGGESTED TALKING POINTS ===\n" + "\n".join(f"- {t}" for t in fit.talking_points)
        + f"\n\n=== COMPANY RESEARCH ===\n{company_info}\n\n"
        f"=== RESUME ===\n{resume_text}\n=== END RESUME ==="
    )
    system = WRITER_PROMPT
    if previous_draft and feedback:
        # The revision loop: the model sees what it wrote and what you want changed.
        prompt += f"\n\n=== PREVIOUS DRAFT ===\n{previous_draft}"
        # Feedback goes into the SYSTEM message and overrides the defaults:
        # small models tend to ignore an instruction buried at the end of a
        # long user message, especially one that conflicts with the rules above.
        system += (
            "\n\nREVISION - the candidate reviewed the previous draft and asked:\n"
            f'"{feedback}"\n'
            "Apply this feedback. It takes priority over the default rules above "
            "(e.g. if asked to be shorter, go below 150 words)."
        )

    return structured_llm(CoverNote).invoke(
        [SystemMessage(content=system), HumanMessage(content=prompt)]
    )


# ---------------------------------------------------------------------------
# 2. CHECKING (code)
# ---------------------------------------------------------------------------

NUMBER_PATTERN = re.compile(r"\d+(?:[.,]\d+)?")


def unverified_numbers(note: str, source_text: str) -> list[str]:
    """Numbers in the note that appear nowhere in the source material."""
    known = set(NUMBER_PATTERN.findall(source_text))
    return sorted({n for n in NUMBER_PATTERN.findall(note) if n not in known})


# ---------------------------------------------------------------------------
# 3. SAVING (code, with the guardrail)
# ---------------------------------------------------------------------------


def save_cover_note(job_id: int, job: JobPosting, text: str, approved: bool) -> Path:
    """Save to the DB + a Markdown file. Refuses unless explicitly approved."""
    if approved is not True:
        raise PermissionError("Cover note not approved by the user - refusing to save.")

    add_cover_note(job_id, text)
    update_status(job_id, "cover_note_ready")

    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", f"{job.company} {job.title}".lower()).strip("-")[:60]
    path = NOTES_DIR / f"{job_id}_{slug}.md"
    path.write_text(f"# {job.title} @ {job.company}\n\n{text}\n", encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# 4. THE GRAPH
# ---------------------------------------------------------------------------


class CoverNoteState(TypedDict, total=False):
    # inputs
    job_id: int
    job: JobPosting
    best_match: ResumeMatch
    company_brief: CompanyBrief | None
    resume_text: str
    # produced along the way
    draft: str
    warnings: list[str]
    revision: int
    decision: str        # "approve" | "edit" | "reject"
    feedback: str
    saved_path: str


def draft_node(state: CoverNoteState) -> dict:
    revision = state.get("revision", 0) + 1
    print(f"  [draft] writing draft #{revision}...")
    note = draft_cover_note(
        state["job"],
        state["best_match"],
        state.get("company_brief"),
        state["resume_text"],
        previous_draft=state.get("draft", ""),
        feedback=state.get("feedback", ""),
    )
    sources = (
        state["resume_text"]
        + state["job"].model_dump_json()
        + (state["company_brief"].model_dump_json() if state.get("company_brief") else "")
    )
    return {
        "draft": note.text,
        "warnings": unverified_numbers(note.text, sources),
        "revision": revision,
    }


def review_node(state: CoverNoteState) -> dict:
    # interrupt() pauses the whole graph here and hands this payload to the
    # program. When resumed, interrupt() RETURNS the human's answer.
    #
    # Gotcha: on resume, LangGraph re-runs this node from the top. So never
    # put side effects (saving, sending email) BEFORE interrupt() in a node.
    answer = interrupt(
        {
            "kind": "approval",  # lets the program tell different questions apart
            "draft": state["draft"],
            "warnings": state["warnings"],
            "revision": state["revision"],
            "word_count": len(state["draft"].split()),
        }
    )
    return {"decision": answer["decision"], "feedback": answer.get("feedback", "")}


def route_after_review(state: CoverNoteState) -> str:
    """Conditional edge: your decision picks the next node."""
    return {"approve": "save", "edit": "draft", "reject": END}[state["decision"]]


def save_node(state: CoverNoteState) -> dict:
    path = save_cover_note(
        state["job_id"],
        state["job"],
        state["draft"],
        approved=state["decision"] == "approve",
    )
    print(f"  [save] saved to tracker + {path}")
    return {"saved_path": str(path)}


def build_cover_note_graph(checkpointer=None, as_subgraph: bool = False):
    """Standalone (Phase 5): own checkpointer.
    Subgraph (Phase 6): no checkpointer - it uses the parent graph's one."""
    graph = StateGraph(CoverNoteState)
    graph.add_node("draft", draft_node)
    graph.add_node("review", review_node)
    graph.add_node("save", save_node)

    graph.add_edge(START, "draft")
    graph.add_edge("draft", "review")
    graph.add_conditional_edges("review", route_after_review, ["save", "draft", END])
    graph.add_edge("save", END)

    if as_subgraph:
        # Inside another graph: the parent's checkpointer saves our state too.
        return graph.compile()
    # interrupt() REQUIRES a checkpointer - otherwise there's nowhere to keep
    # the paused state.
    return graph.compile(checkpointer=checkpointer or InMemorySaver(serde=SAFE_SERDE))


# The checkpointer serializes the state (incl. our Pydantic objects) and
# rebuilds them on resume. Rebuilding arbitrary classes from stored data is a
# security risk (a tampered checkpoint could create unexpected objects), so
# LangGraph wants an explicit allow-list of the classes we trust.
SAFE_SERDE = JsonPlusSerializer(
    allowed_msgpack_modules=[
        ("job_agent.models", name)
        for name in ("JobPosting", "SkillMatch", "FitAnalysis", "ResumeMatch", "CompanyBrief")
    ]
)
