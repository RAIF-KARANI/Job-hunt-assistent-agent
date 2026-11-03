"""15e: research must be about THIS employer (finding F8).

Pure functions plus research_company with a fake agent and a fake summary
LLM, so no network and no model."""

from langchain_core.messages import AIMessage, ToolMessage

from job_agent import research
from job_agent.models import CompanyBrief

NEXORA = "Nexora Embedded Technologies Pvt. Ltd. (Fictional)"


def block(title, url, snippet):
    return f"Title: {title}\nURL: {url}\nSnippet: {snippet}"


def test_core_names():
    assert research.core_name("Nexora Embedded Technologies Pvt. Ltd.") == "Nexora Embedded"
    assert research.core_name("Qualcomm Technologies, Inc.") == "Qualcomm"
    assert research.core_name("Hakkōda, an IBM Company") == "Hakkōda"
    assert research.core_name("Tag-N-Trac") == "Tag-N-Trac"
    assert research.core_name("Cranes Varsity") == "Cranes Varsity"
    assert research.core_name("Global Technologies") == "Global Technologies"  # all generic: keep it


def test_fictional_or_hidden_employers_are_not_searched():
    for name in (NEXORA, "Confidential", "Stealth-mode startup", "Our client", "Not specified", ""):
        assert not research.is_real_name(name), name
    for name in ("ByteDance", "Tag-N-Trac", "Vertex Embedded Labs Pvt. Ltd.", "Hakkōda, an IBM Company"):
        assert research.is_real_name(name), name


def test_a_result_must_name_the_employer():
    # The real Nexora brief came from these (job 16).
    other = block("DCC Energy agrees $725 million Nexora sale", "https://finchannel.com/dcc-nexora",
                  "DCC agreed to sell its technology division, Nexora, to One Equity Partners")
    ours = block("Nexora Embedded Technologies | IoT firmware", "https://nexora-embedded.in",
                 "Nexora Embedded builds sensor nodes")
    assert not research.is_about(other, "Nexora Embedded Technologies Pvt. Ltd.")
    assert research.is_about(ours, "Nexora Embedded Technologies Pvt. Ltd.")
    # Spelling and accents differ in results; the letters still match.
    assert research.is_about(block("TagNTrac raises seed", "https://tagntrac.com", ""), "Tag-N-Trac")
    assert research.is_about(block("Hakkoda named partner", "https://hakkoda.io", ""), "Hakkōda, an IBM Company")
    assert research.is_about(block("Careers", "https://www.cranesvarsity.com/careers", "Embedded training"),
                             "Cranes Varsity")


def test_keep_results_about_drops_others_and_counts_them():
    text = "\n\n".join([
        block("Vertex Research Centre Pvt Ltd", "https://in.linkedin.com/company/vertex-research-centre", "R&D"),
        block("Scam alert: impersonation of Vertex", "https://vertexholdings.com/news/scam", "Vertex Holdings"),
        "No results found. Try a different query.",
    ])
    kept, n_kept, n_dropped = research.keep_results_about(text, "Vertex Embedded Labs Pvt. Ltd.")
    assert (kept, n_kept, n_dropped) == ("", 0, 2)


class FakeGraph:
    def __init__(self, tool_text):
        self.tool_text = tool_text

    def stream(self, state, stream_mode):
        yield {"agent": {"messages": [AIMessage(content="", tool_calls=[
            {"name": "web_search", "args": {"query": "x"}, "id": "1"}])]}}
        yield {"tools": {"messages": [ToolMessage(content=self.tool_text, tool_call_id="1", name="web_search")]}}
        yield {"agent": {"messages": [AIMessage(content="Nexora sold for $725M")]}}  # notes about the wrong one


def run(monkeypatch, company, tool_text):
    seen = {}

    class Summary:
        def invoke(self, messages):
            seen["notes"] = messages[-1].content
            return CompanyBrief(what_they_do="Builds sensor nodes", products=[], size_and_stage="Unknown",
                                recent_news=[], culture_and_values=[], cover_note_hooks=[],
                                sources=["https://nexora-embedded.in", "https://finchannel.com/dcc-nexora"])
    monkeypatch.setattr(research, "build_research_graph", lambda: FakeGraph(tool_text))
    monkeypatch.setattr(research, "structured_llm", lambda schema: Summary())
    stats = {}
    return research.research_company(company, "Engineer", stats=stats, location="Bangalore"), stats, seen


def test_only_results_about_the_employer_reach_the_brief(monkeypatch):
    text = "\n\n".join([
        block("DCC Energy agrees $725 million Nexora sale", "https://finchannel.com/dcc-nexora", "Nexora sold"),
        block("Nexora Embedded Technologies", "https://nexora-embedded.in", "Nexora Embedded builds sensor nodes"),
    ])
    brief, stats, seen = run(monkeypatch, "Nexora Embedded Technologies Pvt. Ltd.", text)
    assert "finchannel" not in seen["notes"] and "$725" not in seen["notes"]  # neither result nor agent notes
    assert brief.sources == ["https://nexora-embedded.in"]                 # the other URL is dropped too
    assert stats["unrelated_results"] == 1


def test_nothing_about_the_employer_means_no_research(monkeypatch):
    text = block("DCC Energy agrees $725 million Nexora sale", "https://finchannel.com/dcc-nexora", "Nexora sold")
    brief, stats, _ = run(monkeypatch, "Nexora Embedded Technologies Pvt. Ltd.", text)
    assert brief is None and stats["skipped"] == "no search result about this employer"


def test_a_fictional_employer_is_never_searched(monkeypatch):
    monkeypatch.setattr(research, "build_research_graph", lambda: (_ for _ in ()).throw(AssertionError("searched")))
    stats = {}
    assert research.research_company(NEXORA, stats=stats) is None
    assert stats["skipped"] == "not a real company name"
