# Job Hunt Assistant — Idea

## One-line pitch
Paste a job posting link → an AI agent reads it, compares it with my resume, researches the company, saves the job to a tracker, and drafts a tailored cover note that I approve before it's saved.

## Why I'm building this
- To learn how AI agents work: the agent loop, tools, state, and human-in-the-loop approval.
- To get a useful tool for my own job search.

## What the user does
1. Runs the assistant and pastes a job posting URL.
2. Watches the agent work through each step (it explains what it's doing).
3. Reviews the fit analysis and the drafted cover note.
4. Approves, edits, or rejects the cover note.

## What the agent does
| Step | What happens | Output |
|------|--------------|--------|
| 1. Read the posting | Fetch the URL and extract the important parts | Title, company, location, requirements, nice-to-haves, salary (if listed) |
| 2. Compare with resume | Match my skills and experience to the requirements | Fit score, matching skills, gaps, talking points |
| 3. Research the company | Search the web for what the company does and recent news | Short company brief |
| 4. Save to tracker | Add a row for this job | Tracker entry with status "Researched" |
| 5. Draft cover note | Write a short note using the fit analysis + company brief | Draft text |
| 6. Ask for approval | Show me the draft; I approve, edit, or reject | Saved cover note only if approved |

## Key agent concepts this project teaches
- **Tools**: functions the model can call (fetch page, web search, read resume, save to tracker, save cover note).
- **Agent loop**: the model decides which tool to call next, sees the result, and continues until done.
- **Structured output**: turning messy web pages into clean, predictable data.
- **Human-in-the-loop**: the agent must pause and wait for my approval before saving the cover note.
- **State / memory**: the tracker persists jobs across runs.

## Out of scope (for v1)
- Auto-applying to jobs or submitting forms.
- Sending emails.
- Scraping sites that require login (e.g. LinkedIn behind auth). If a page can't be fetched, I paste the job text instead.

## Success criteria
- Given a public job posting URL, the agent completes all six steps end to end.
- Nothing is saved as a cover note without my explicit approval.
- Each step prints a clear explanation of what the agent is doing and why.

## Decisions
- **Language**: Python
- **Agent framework**: LangChain + LangGraph
- **Tracker**: SQLite database
- **Resume**: PDF (text extracted at runtime)

## Open questions
- LLM provider (Claude via `langchain-anthropic` is the default plan)
- Web search tool for company research (e.g. Tavily)
- CLI first, web UI later?
