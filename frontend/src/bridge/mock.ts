// Fake bridge for `npm run dev` in a normal browser: just enough data to
// build and look at screens without Python. Not included in production
// builds (bridge.ts only loads it when import.meta.env.DEV).

import type { AgentEvent, Answer, JobRow, PyApi, Settings } from "./types";

export function mockApi(emit: (event: AgentEvent) => void): PyApi {
  let settings: Settings = {
    LLM_PROVIDER: "ollama",
    LLM_MODEL: "qwen3:8b",
    TRACING: "off",
    UI_3D: "animated",
    UI_THEME: "system",
    ANTHROPIC_API_KEY_SET: false,
  };
  const jobs: JobRow[] = [
    { id: 1, title: "AI Engineer", company: "Northwind Labs", fit_score: 86, best_resume: "AI_Engineer.pdf", status: "interviewing", updated_at: "2026-10-29 10:42" },
    { id: 2, title: "Backend Engineer (Python)", company: "Lumen Robotics", fit_score: 78, best_resume: "Software_Engineer.pdf", status: "applied", updated_at: "2026-10-28 09:15" },
  ];
  const notInMock = async (): Promise<never> => {
    throw new Error("Not available in the browser preview");
  };
  const run = fakeRun(emit);

  return {
    app_info: async () => ({ version: "dev", installed: false, data_dir: "(browser preview)", settings }),
    llm_status: async () => ({ ok: true, message: "Preview: pretend 'qwen3:8b' is ready." }),
    run_state: async () => ({ busy: false, run_id: null, paused: null, events: [] }),
    list_jobs: async () => jobs,
    statuses: async () => ["researched", "cover_note_ready", "applied", "interviewing", "offer", "rejected"],
    get_settings: async () => settings,
    save_settings: async (updates) => {
      settings = { ...settings, ...updates };
      return settings;
    },
    set_api_key: async (key) => {
      settings = { ...settings, ANTHROPIC_API_KEY_SET: Boolean(key) };
      return settings;
    },
    feedback_options: async () => ({
      fit_score: ["too low", "about right", "too high"],
      cover_note: ["usable as is", "needed edits", "not usable"],
    }),
    start_run: async (url) => run.start(url),
    resume: async (answer) => run.resume(answer),
    paste_text: async () => run.pasted(),
    save_feedback: async (_run, _job, ratings) => Object.values(ratings).filter(Boolean).length,
    get_job: notInMock,
    set_status: notInMock,
  };
}

/** A scripted agent run, a few seconds long. A link containing "linkedin" asks for pasted text. */
function fakeRun(emit: (event: AgentEvent) => void) {
  const runId = "preview-run";
  let revision = 0;
  const at = () => Date.now() / 1000;
  const summary = {
    title: "AI Engineer",
    company: "Northwind Labs",
    fit_score: 86,
    resume: "AI_Engineer.pdf",
    breakdown: "skills 34/40 · experience 26/30 · tools 26/30",
    matches: [
      { requirement: "LangGraph agents", evidence: "Built a LangGraph agent with human approval steps" },
      { requirement: "Python", evidence: "4 years of Python in production" },
    ],
    gaps: ["Kubernetes", "Insurance domain experience"],
  };

  function play(script: [number, AgentEvent | (() => void)][]) {
    let t = 0;
    for (const [wait, item] of script) {
      t += wait;
      setTimeout(() => (typeof item === "function" ? item() : emit({ ...item, ...("at" in item ? { at: at() } : {}) } as AgentEvent)), t);
    }
  }
  const log = (text: string): AgentEvent => ({ type: "log", text });

  function draft() {
    revision += 1;
    play([
      [0, { type: "busy", busy: true }],
      [0, log(`  [draft] writing draft #${revision}...`)],
      [0, { type: "step", step: 5, text: revision === 1 ? "Writing the cover note" : `Rewriting the cover note (draft ${revision})`, at: 0 }],
      [1500, { type: "busy", busy: false }],
      [
        0,
        {
          type: "paused",
          kind: "review",
          run_id: runId,
          summary,
          at: 0,
          payload: {
            kind: "approval",
            revision,
            word_count: 96,
            warnings: revision === 1 ? ["40%"] : [],
            draft:
              "Dear Northwind Labs team,\n\nYour applied-AI team is building agents that read insurance documents, and that is the work I have been doing. " +
              "I built JobLens, a LangGraph agent that reads job postings, checks every claim against a source, and pauses for human approval before saving anything.\n\n" +
              (revision === 1 ? "In my last project I cut manual review time by 40% with automatic evidence checks.\n\n" : "") +
              "I would love to talk about the role.\n\n[Your name]",
          },
        },
      ],
    ]);
  }

  return {
    start(url: string) {
      revision = 0;
      const paste = url.includes("linkedin");
      emit({ type: "started", run_id: runId, url, at: at() });
      play([
        [0, { type: "busy", busy: true }],
        [0, log("[1/5] Reading the job posting...")],
        [0, { type: "step", step: 1, text: "Reading the job posting", at: 0 }],
        ...(paste
          ? ([
              [700, log("  ! couldn't read the posting: 999 Request denied")],
              [0, { type: "busy", busy: false }],
              [0, { type: "paused", kind: "paste_posting", run_id: runId, summary: {}, payload: { kind: "paste_posting", reason: "999 Request denied" }, at: 0 }],
            ] as [number, AgentEvent][])
          : rest()),
      ]);
      return { run_id: runId };
    },
    pasted() {
      play([[0, { type: "busy", busy: true }], [0, log("[1/5] Reading the job posting...")], [0, { type: "step", step: 1, text: "Reading the job posting", at: 0 }], ...rest()]);
    },
    resume(answer: Answer) {
      if (answer.decision === "edit") return draft();
      play([
        [0, { type: "busy", busy: true }],
        [600, log(answer.decision === "approve" ? "  [save] saved to tracker + cover_notes/3_northwind.md" : "Rejected.")],
        [0, { type: "busy", busy: false }],
        [
          0,
          {
            type: "finished",
            run_id: runId,
            job_id: 3,
            decision: answer.decision,
            saved_path: answer.decision === "approve" ? "C:/Users/you/JobLens/data/cover_notes/3_northwind.md" : null,
            suggested_rating: answer.decision === "approve" ? (revision > 1 ? "needed edits" : "usable as is") : "not usable",
            at: 0,
          },
        ],
      ]);
    },
  };

  function rest(): [number, AgentEvent | (() => void)][] {
    return [
      [700, log("  -> AI Engineer @ Northwind Labs (Remote)")],
      [0, { type: "step_detail", step: 1, text: "AI Engineer @ Northwind Labs (Remote)", warn: false, at: 0 }],
      [300, log("[2/5] Comparing your resumes with the job...")],
      [0, { type: "step", step: 2, text: "Comparing your resumes with the job", at: 0 }],
      [500, { type: "step_detail", step: 2, text: "Scoring AI_Engineer.pdf", warn: false, at: 0 }],
      [900, log("   86/100  AI_Engineer.pdf   [skills 34/40]")],
      [0, { type: "step_detail", step: 2, text: "best: AI_Engineer.pdf", warn: false, at: 0 }],
      [300, log("[3/5] Researching the company (agent picks its own searches)...")],
      [0, { type: "step", step: 3, text: "Researching the company (agent picks its own searches)", at: 0 }],
      [600, log("  [agent] decides to call web_search({'query': 'Northwind Labs applied AI'})")],
      [600, log("  [verify] dropped 1 source URL(s) not in the search results")],
      [0, { type: "step_detail", step: 3, text: "3 verified sources", warn: false, at: 0 }],
      [300, log("[4/5] Saving to the job tracker...")],
      [0, { type: "step", step: 4, text: "Saving to the job tracker", at: 0 }],
      [300, { type: "step_detail", step: 4, text: "job #3", warn: false, at: 0 }],
      [0, () => draft()],
    ];
  }
}
