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


# ---- 16b: a search that finds nothing tries easier searches, then gives up ----

class FakeSearch:
    """Stands in for the search library: `found` maps (kind, query) to results;
    anything else raises what the library raises."""
    asked: list = []
    found: dict = {}
    error = "No results found."

    def _run(self, kind, query):
        FakeSearch.asked.append((kind, query))
        if (kind, query) in FakeSearch.found:
            return FakeSearch.found[(kind, query)]
        raise RuntimeError(FakeSearch.error)

    def text(self, query, max_results=5):
        return self._run("text", query)

    def news(self, query, max_results=5):
        return self._run("news", query)


def fake_search(monkeypatch, found, error="No results found."):
    FakeSearch.asked, FakeSearch.found, FakeSearch.error = [], found, error
    monkeypatch.setattr(research, "DDGS", FakeSearch)


def test_the_first_search_that_finds_something_wins(monkeypatch):
    fake_search(monkeypatch, {("text", "AiPrise funding"): [{"title": "AiPrise", "href": "https://aiprise.com", "body": "KYC"}]})
    results, kind, error = research.search_with_fallbacks("text", "AiPrise funding", "AiPrise Inc.")
    assert len(results) == 1 and kind == "text" and error is None
    assert FakeSearch.asked == [("text", "AiPrise funding")]              # no extra searches


def test_nothing_found_tries_the_name_then_the_other_kind(monkeypatch):
    fake_search(monkeypatch, {("news", "AiPrise"): [{"title": "AiPrise raises", "url": "https://news.example/a", "body": "x", "date": "2026-10-01T00:00"}]})
    results, kind, error = research.search_with_fallbacks("text", "AiPrise funding", "AiPrise Inc.")
    assert FakeSearch.asked == [("text", "AiPrise funding"), ("text", "AiPrise"), ("news", "AiPrise")]
    assert kind == "news" and error is None and results[0]["url"] == "https://news.example/a"
    # and the tool formats what it got the news way (the URL is under "url", with a date)
    monkeypatch.setattr(research, "_company", "AiPrise Inc.")
    assert "URL: https://news.example/a" in research.web_search.invoke({"query": "AiPrise funding"})


def test_nothing_anywhere_is_no_results_not_a_failure(monkeypatch):
    fake_search(monkeypatch, {})
    monkeypatch.setattr(research, "_company", "AiPrise Inc.")
    assert research.news_search.invoke({"query": "AiPrise news"}) == research.NO_RESULTS
    assert FakeSearch.asked == [("news", "AiPrise news"), ("news", "AiPrise"), ("text", "AiPrise news")]


def test_a_real_error_on_every_try_is_a_failure(monkeypatch):
    fake_search(monkeypatch, {}, error="operation timed out")
    monkeypatch.setattr(research, "_company", "")                         # no name: one try only
    answer = research.web_search.invoke({"query": "anything"})
    assert answer.startswith("Search failed (operation timed out)") and len(FakeSearch.asked) == 1


def test_the_same_query_is_not_searched_twice(monkeypatch):
    fake_search(monkeypatch, {})
    research.search_with_fallbacks("text", "AiPrise", "AiPrise")          # the query already is the name
    assert FakeSearch.asked == [("text", "AiPrise"), ("news", "AiPrise")]


def tool(text):
    return ToolMessage(content=text, tool_call_id="1", name="web_search")


def test_research_stops_when_searches_keep_finding_nothing():
    found, nothing = tool(block("Acme", "https://acme.example", "anvils")), tool(research.NO_RESULTS)
    assert research.stop_reason([nothing], 5, 180) is None                # one empty search: try again
    assert research.stop_reason([nothing, nothing], 5, 180) == "2 searches in a row found nothing"
    assert research.stop_reason([nothing, found], 5, 180) is None
    assert research.stop_reason([found, nothing, nothing], 5, 180) is not None
    assert research.stop_reason([nothing, nothing, AIMessage(content="notes")], 5, 180) is None  # the agent ended it


def test_research_stops_at_the_time_limit(monkeypatch):
    found = tool(block("Acme", "https://acme.example", "anvils"))
    assert research.stop_reason([found], 179, 180) is None
    assert research.stop_reason([found], 181, 180) == "it took over 180 seconds"
    monkeypatch.setenv("RESEARCH_MAX_SECONDS", "60")
    assert research.max_seconds() == 60
    monkeypatch.setenv("RESEARCH_MAX_SECONDS", "soon")                    # nonsense: the default
    assert research.max_seconds() == 180


def test_a_stopped_search_still_uses_what_it_found(monkeypatch):
    class SlowGraph:
        def stream(self, state, stream_mode):
            yield {"tools": {"messages": [tool(block("Nexora Embedded", "https://nexora-embedded.in", "Nexora Embedded builds sensor nodes"))]}}
            yield {"tools": {"messages": [tool("should never be reached")]}}

    class Summary:
        def invoke(self, messages):
            return CompanyBrief(what_they_do="Builds sensor nodes", products=[], size_and_stage="Unknown", recent_news=[],
                                culture_and_values=[], cover_note_hooks=[], sources=["https://nexora-embedded.in"])
    monkeypatch.setattr(research, "build_research_graph", lambda: SlowGraph())
    monkeypatch.setattr(research, "structured_llm", lambda schema: Summary())
    monkeypatch.setattr(research, "max_seconds", lambda: 0.0)             # the limit is already over
    stats = {}
    brief = research.research_company("Nexora Embedded Technologies Pvt. Ltd.", stats=stats)
    assert stats["stopped_early"] == "it took over 0 seconds"
    assert brief is not None and brief.sources == ["https://nexora-embedded.in"]
