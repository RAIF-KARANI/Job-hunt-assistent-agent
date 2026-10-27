"""
Phase 3: research a company with a tool-using agent, built as a LangGraph graph.

This is the first REAL agent in the project. Until now, our code decided every
step. Here, the LLM decides: which tool to call, what to search for, and when
it has learned enough. Our code only runs the tools it asks for.

The graph (the classic "ReAct" loop = Reason + Act):

        START
          |
          v
      +-------+   wants a tool?   +-------+
      | agent | ----------------> | tools |
      +-------+ <---------------- +-------+
          |        tool results
          | no tool call (done)
          v
         END

After the loop, one more LLM call turns the research notes into a
structured CompanyBrief, and code verifies the source URLs.
"""

import re
from datetime import date

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from job_agent.llm import get_llm, structured_llm
from job_agent.models import CompanyBrief

# Safety limit: after this many tool calls, the agent must stop and answer.
# Without it, a confused model could search forever.
MAX_TOOL_CALLS = 5


# ---------------------------------------------------------------------------
# 1. TOOLS
# The @tool decorator turns a Python function into something the LLM can call.
# The function NAME, the TYPE HINTS and the DOCSTRING are sent to the model as
# the tool's description, so the docstring is effectively part of the prompt.
# ---------------------------------------------------------------------------

# ---- Search backend: DuckDuckGo (current choice: free, no API key) ----
from ddgs import DDGS


@tool
def web_search(query: str) -> str:
    """Search the web. Use for general facts: what a company does, its
    products, size, founding, mission and culture. Returns titles, URLs and
    short snippets."""
    try:
        results = DDGS().text(query, max_results=5)
    except Exception as e:
        # Never let a tool crash the agent: return the error as text so the
        # LLM can read it and adapt (e.g. try a different query).
        return f"Search failed ({e}). Try a simpler or different query."
    return _format_results(results, url_key="href", text_key="body")


@tool
def news_search(query: str) -> str:
    """Search recent news articles. Use for recent events: product launches,
    funding, acquisitions, earnings, layoffs. Returns dates, titles, URLs and
    short snippets."""
    try:
        results = DDGS().news(query, max_results=5)
    except Exception as e:
        return f"News search failed ({e}). Try a simpler or different query."
    return _format_results(results, url_key="url", text_key="body", date_key="date")


# ---- Alternative backend: Tavily (better results, needs a free API key) ----
# pip install langchain-tavily ; set TAVILY_API_KEY in .env ; then replace the
# two tools above with:
#
#   from langchain_tavily import TavilySearch
#   web_search = TavilySearch(max_results=5)                   # general web
#   news_search = TavilySearch(max_results=5, topic="news")    # news only


def _format_results(results, url_key, text_key, date_key=None) -> str:
    """Turn search results into compact text the LLM can read."""
    if not results:
        return "No results found. Try a different query."
    blocks = []
    for r in results:
        date_line = f"Date: {r.get(date_key, '')[:10]}\n" if date_key else ""
        blocks.append(
            f"{date_line}Title: {r.get('title', '')}\n"
            f"URL: {r.get(url_key, '')}\n"
            f"Snippet: {r.get(text_key, '')}"
        )
    return "\n\n".join(blocks)


TOOLS = [web_search, news_search]


# ---------------------------------------------------------------------------
# 2. THE GRAPH
# State = MessagesState: just a growing list of messages. Every node returns
# new messages, and LangGraph appends them to the list.
# ---------------------------------------------------------------------------

RESEARCH_PROMPT = """You are researching a company for a job applicant.
Today's date: {today}.
Use the tools to find out:
  1. what the company does and its main products
  2. size / stage (employees, funding or public, HQ)
  3. notable news from the last 12 months
  4. culture, values and ways of working
Make 2-4 focused searches (one topic per search). Don't repeat a search.
When you have enough, STOP calling tools and write short research notes
that include the source URLs."""


def agent_node(state: MessagesState) -> dict:
    """The 'brain': the LLM looks at everything so far and decides what next."""
    tool_calls_so_far = sum(isinstance(m, ToolMessage) for m in state["messages"])

    llm = get_llm()
    if tool_calls_so_far < MAX_TOOL_CALLS:
        # bind_tools() sends the tool descriptions with the request, so the
        # model CAN reply with a tool call instead of text.
        llm = llm.bind_tools(TOOLS)
    # else: no tools bound -> the model can only answer in text -> loop ends.

    system = SystemMessage(content=RESEARCH_PROMPT.format(today=date.today()))
    response = llm.invoke([system] + state["messages"])
    return {"messages": [response]}


def build_research_graph():
    graph = StateGraph(MessagesState)

    graph.add_node("agent", agent_node)
    # ToolNode = prebuilt node that runs whichever tools the last AI message
    # asked for, and returns their outputs as ToolMessages.
    graph.add_node("tools", ToolNode(TOOLS))

    graph.add_edge(START, "agent")
    # Conditional edge: tools_condition looks at the last message.
    #   has tool calls -> go to "tools";   no tool calls -> go to END
    graph.add_conditional_edges("agent", tools_condition)
    graph.add_edge("tools", "agent")  # after tools, always back to the agent

    return graph.compile()


# ---------------------------------------------------------------------------
# 3. RUN IT + STRUCTURE THE RESULT + VERIFY
# ---------------------------------------------------------------------------

SUMMARY_PROMPT = """Turn these research notes into a company brief.
Use ONLY facts found in the notes. If something wasn't found, say 'Unknown'
or leave the list empty. Only cite URLs that appear in the notes.
Copy dates exactly as they appear in the search results; never guess a date."""

URL_PATTERN = re.compile(r"https?://[^\s)\]>\"']+")
DATE_PATTERN = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")


def research_company(company: str, role_context: str = "") -> CompanyBrief:
    """Run the research agent, then turn its notes into a verified CompanyBrief."""
    request = f"Research the company '{company}'."
    if role_context:
        request += f" The applicant is applying for: {role_context}."

    graph = build_research_graph()

    # stream(..., stream_mode="updates") yields after every node runs, so we
    # can print each step of the agent loop as it happens.
    messages = [HumanMessage(content=request)]
    for update in graph.stream({"messages": messages}, stream_mode="updates"):
        for node_name, output in update.items():
            for msg in output["messages"]:
                messages.append(msg)
                _print_step(node_name, msg)

    # Everything the tools returned is our "evidence". The agent's final
    # message is its own summary of that evidence.
    tool_outputs = "\n\n".join(m.content for m in messages if isinstance(m, ToolMessage))
    notes = f"SEARCH RESULTS:\n{tool_outputs}\n\nAGENT NOTES:\n{messages[-1].content}"
    if role_context:
        notes = f"APPLICANT'S ROLE: {role_context}\n\n{notes}"

    print("  [summarize] turning research notes into a structured CompanyBrief...")
    brief = structured_llm(CompanyBrief).invoke(
        [SystemMessage(content=SUMMARY_PROMPT), HumanMessage(content=notes)]
    )

    verified = verify_sources(brief.sources, tool_outputs)
    if len(verified) < len(brief.sources):
        print(f"  [verify] dropped {len(brief.sources) - len(verified)} source URL(s) "
              "not found in search results")

    news = remove_invented_dates(brief.recent_news, tool_outputs)
    if news != brief.recent_news:
        print("  [verify] removed invented date(s) from news items")

    return brief.model_copy(update={"sources": verified, "recent_news": news})


# Pure functions (no LLM, no network) -> easy to unit-test. See tests/.


def verify_sources(sources: list[str], tool_outputs: str) -> list[str]:
    """Keep only URLs that really came back from a search.
    (LLMs sometimes invent plausible-looking URLs.)"""
    real_urls = set(URL_PATTERN.findall(tool_outputs))
    return [u for u in sources if u in real_urls]


def remove_invented_dates(news: list[str], tool_outputs: str) -> list[str]:
    """Replace dates that never appeared in the search results.
    Small models like to "fill in" a missing date (often today minus N years)."""
    real_dates = set(DATE_PATTERN.findall(tool_outputs))
    cleaned = []
    for item in news:
        for d in DATE_PATTERN.findall(item):
            if d not in real_dates:
                item = item.replace(d, "date unknown")
        cleaned.append(item)
    return cleaned


def _print_step(node_name: str, msg) -> None:
    """Show what the agent is doing, so the loop isn't a black box."""
    if node_name == "agent":
        if getattr(msg, "tool_calls", None):
            for call in msg.tool_calls:
                print(f"  [agent] decides to call {call['name']}({call['args']})")
        else:
            print("  [agent] has enough information -> finishing research")
    elif node_name == "tools":
        if "failed" in msg.content[:40]:
            print(f"  [tools] {msg.name} FAILED -> error passed back to the agent")
        else:
            n_results = msg.content.count("URL:")
            print(f"  [tools] {msg.name} returned {n_results} results")
