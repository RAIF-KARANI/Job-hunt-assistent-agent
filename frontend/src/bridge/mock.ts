// Fake bridge for `npm run dev` in a normal browser: just enough data to
// build and look at screens without Python. Not included in production
// builds (bridge.ts only loads it when import.meta.env.DEV).

import type { AgentEvent, Answer, EvalsData, JobDetail, JobRow, PyApi, Settings, UpdateStatus } from "./types";

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
    { id: 1, title: "AI Engineer", company: "Northwind Labs", fit_score: 86, best_resume: "AI_Engineer.pdf", status: "interviewing", created_at: "2026-10-29 10:42", updated_at: "2026-10-29 10:42" },
    { id: 2, title: "Backend Engineer (Python)", company: "Lumen Robotics", fit_score: 78, best_resume: "Software_Engineer.pdf", status: "applied", created_at: "2026-10-21 09:15", updated_at: "2026-10-21 09:15" },
    { id: 3, title: "Applied Scientist", company: "Peregrine AI", fit_score: 81, best_resume: "AI_Engineer.pdf", status: "researched", created_at: "2026-10-28 14:02", updated_at: "2026-10-28 14:02" },
    { id: 4, title: "Platform Engineer (Rust)", company: "Tessellate", fit_score: 52, best_resume: "Software_Engineer.pdf", status: "researched", created_at: "2026-10-26 08:30", updated_at: "2026-10-26 08:30" },
    { id: 5, title: "LLM Engineer", company: "Halcyon Data", fit_score: 72, best_resume: "AI_Engineer.pdf", status: "cover_note_ready", created_at: "2026-10-30 07:10", updated_at: "2026-10-30 07:10" },
    { id: 6, title: "Full-stack Engineer", company: "Atlas Freight", fit_score: 39, best_resume: "Software_Engineer.pdf", status: "rejected", created_at: "2026-10-15 16:45", updated_at: "2026-10-15 16:45" },
  ];
  const run = fakeRun(emit);
  const resumes = ["AI_Engineer.pdf", "Software_Engineer.pdf"];
  const pulled = new Set(["qwen3:4b"]);

  return {
    // ?setup in the address shows the first-run wizard
    app_info: async () => ({ version: "dev", installed: false, data_dir: "(browser preview)", settings, setup_needed: location.search.includes("setup") }),
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
    // The scripted run's timers keep going after this; fine for a preview.
    stop_run: async () => {
      emit({ type: "stopping", at: Date.now() / 1000 });
      setTimeout(() => emit({ type: "stopped", run_id: "preview-run", at: Date.now() / 1000 }), 600);
      return true;
    },
    step_estimates: async () => ({ "1": 27, "2": 205, "3": 59, "4": 0.2, "5": 16 }),
    // ?update in the address pretends a newer version exists
    update_status: async () => mockUpdate(),
    check_for_updates: async () => mockUpdate(),
    save_feedback: async (_run, _job, ratings) => Object.values(ratings).filter(Boolean).length,
    get_job: async (id) => mockJob(jobs.find((j) => j.id === id) ?? jobs[0]),
    set_status: async (id, status) => {
      const job = jobs.find((j) => j.id === id);
      if (job) job.status = status;
    },
    open_link: async (url) => void window.open(url, "_blank", "noopener"),
    dashboard: async (days) => {
      const runs = days === 7 ? 4 : days === 30 ? 11 : 17;
      return {
        days,
        kpis: { runs, llm_calls: runs * 9, tokens_in: runs * 15400, tokens_out: runs * 3900, median_full_run: 182, approved: Math.round(runs * 0.6), decided: runs - 1, approval_rate: 0.6 },
        decisions: { approve: Math.round(runs * 0.6), edit: 0, reject: runs - 1 - Math.round(runs * 0.6) },
        steps: [
          { node: "check_tracker", avg_seconds: 0.1, max_seconds: 0.2, count: runs },
          { node: "read_posting", avg_seconds: 23, max_seconds: 41, count: runs },
          { node: "analyze_fit", avg_seconds: 82, max_seconds: 130, count: runs },
          { node: "research_company", avg_seconds: 48, max_seconds: 77, count: runs },
          { node: "save_to_tracker", avg_seconds: 0.4, max_seconds: 1, count: runs },
          { node: "draft", avg_seconds: 28, max_seconds: 60, count: runs },
        ],
        quality: [
          { check: "Fake resume quotes caught", per_run: 0.3, total: 3, runs },
          { check: "Claims rejected by the judge", per_run: 1.6, total: 18, runs },
          { check: "Invented source URLs removed", per_run: 0.2, total: 2, runs },
          { check: "Unverified numbers flagged", per_run: 0.5, total: 5, runs },
          { check: "Web searches that failed", per_run: 0.1, total: 1, runs: 9 },
        ],
        pass_rate: 0.58,
      };
    },
    evals: async (model) => mockEvals(model),
    list_resumes: async () => resumes.map((name) => ({ name, kb: 84 })),
    add_resumes: async () => {
      resumes.push(`Resume ${resumes.length + 1}.pdf`);
      return [resumes[resumes.length - 1]];
    },
    remove_resume: async (name) => void resumes.splice(resumes.indexOf(name), 1),
    open_data_folder: async () => undefined,
    system_check: async (provider) => {
      await new Promise((r) => setTimeout(r, 900));
      return {
        info: { ram_gb: 16, gpu_name: "NVIDIA GeForce RTX 4060 Laptop GPU", vram_gb: 8, vram_exact: true, disk_free_gb: 210, cpu_threads: 16 },
        advice: [
          { name: "qwen3:14b", download_gb: 9.3, description: "Highest quality of the local options", verdict: "slower", reason: "needs ~11 GB; split between GPU and RAM", recommended: false },
          { name: "qwen3:8b", download_gb: 5.2, description: "Best balance - JobLens was built and tested with it", verdict: "fast", reason: "fits in your 8 GB graphics memory", recommended: true },
          { name: "qwen3:4b", download_gb: 2.6, description: "Lighter, for 8 GB PCs; noticeably less accurate", verdict: "fast", reason: "fits in your 8 GB graphics memory", recommended: false },
          { name: "llama3.2", download_gb: 2.0, description: "Smallest (3B); weakest at the structured answers JobLens needs", verdict: "fast", reason: "fits in your 8 GB graphics memory", recommended: false },
        ],
        summary: "16 GB RAM · NVIDIA GeForce RTX 4060 Laptop GPU (8 GB). Recommended: qwen3:8b - runs fast on your graphics card.",
        ui3d: provider === "anthropic"
          ? { level: "animated", reason: "The AI runs in the cloud, so the graphics card is free for 3D." }
          : { level: "still", reason: "qwen3:8b leaves only ~1.1 GB graphics memory free: 3D moves only when you drag it." },
      };
    },
    ollama_status: async () => ({ installed: true, running: true, models: [...pulled], winget: true }),
    install_ollama: async () => ({ ok: true, manual: false }),
    pull_model: async (model) => {
      for (let i = 1; i <= 10; i++) {
        await new Promise((r) => setTimeout(r, 300));
        emit({ type: "setup_progress", what: "pull", message: `pulling: ${(i * 0.52).toFixed(2)} GB of 5.20 GB`, fraction: i / 10, done: false, ok: null });
      }
      pulled.add(model);
      emit({ type: "setup_progress", what: "pull", message: `${model} is ready.`, fraction: 1, done: true, ok: true });
      return { ok: true, model };
    },
    test_api_key: async (key) => (key?.startsWith("sk-ant-") ? { ok: true, message: "The key works." } : { ok: false, message: "authentication_error: invalid x-api-key" }),
    tracing_status: async () => ({
      mode: "langfuse",
      langfuse: "running",
      langfuse_sessions: "http://localhost:3000/project/demo/sessions/",
      langsmith: "off",
      langsmith_url: "https://smith.langchain.com/",
    }),
  };
}

function mockUpdate(): UpdateStatus {
  const newer = location.search.includes("update");
  return {
    current: "dev",
    latest: newer ? "v1.0.0" : "v0.3.1",
    newer,
    page: "https://github.com/RAIF-KARANI/Job-hunt-assistent-agent/releases",
    checked_at: Date.now() / 1000,
    error: null,
    enabled: true,
  };
}

function mockEvals(model: string | null): EvalsData {
  const rates = [0.5, 0.58, 0.46, 0.62, 0.55, 0.71, 0.58, 0.64, 0.69, 0.6, 0.72, 0.58];
  const local = model !== "claude-haiku-5-5";
  return {
    model,
    models: [
      { model: "qwen3:8b", provider: "ollama", runs: 10, pass_rate: 0.6, approved: 6, decided: 9, median_seconds: 182, tokens_per_run: 19400 },
      { model: "claude-haiku-5-5", provider: "anthropic", runs: 2, pass_rate: 0.74, approved: 2, decided: 2, median_seconds: 48, tokens_per_run: 17800 },
    ],
    kpis: {
      runs: local ? 10 : 2,
      pass_rate: local ? 0.6 : 0.74,
      pass_rate_delta: local ? 0.06 : null,
      pass_rate_window: local ? 5 : null,
      approved: local ? 6 : 2,
      decided: local ? 9 : 2,
      median_seconds: local ? 182 : 48,
      full_runs: local ? 9 : 2,
      tokens_in_per_run: 14600,
      tokens_out_per_run: 4800,
      tool_calls: 26,
      tool_failures: 1,
      unfinished: 2,
      unfinished_seconds: 1490,
    },
    trend: (local ? rates : [0.7, 0.78]).map((rate, i) => ({ run_id: `r${i}`, started_at: `2026-10-${String(10 + i).padStart(2, "0")} 10:00:00`, rate })),
    ratings: [
      { label: "Fit score: too low", aspect: "fit_score", rating: "too low", count: 1 },
      { label: "Fit score: about right", aspect: "fit_score", rating: "about right", count: 6 },
      { label: "Fit score: too high", aspect: "fit_score", rating: "too high", count: 2 },
      { label: "Cover note: usable as is", aspect: "cover_note", rating: "usable as is", count: 3 },
      { label: "Cover note: needed edits", aspect: "cover_note", rating: "needed edits", count: 2 },
      { label: "Cover note: not usable", aspect: "cover_note", rating: "not usable", count: 1 },
    ],
    checks: [
      { check: "claims_checked", label: "Claims checked", meaning: "skill claims the fit analysis made", total: 124, runs: 10, per_run: 12.4 },
      { check: "fake_quotes_caught", label: "Fake quotes caught", meaning: "quote not found in your resume", total: 3, runs: 10, per_run: 0.3 },
      { check: "judge_rejections", label: "Judge rejections", meaning: "quote is real but doesn't prove the skill", total: 18, runs: 10, per_run: 1.8 },
      { check: "invented_urls_removed", label: "Invented URLs removed", meaning: "source not in the search results", total: 2, runs: 10, per_run: 0.2 },
      { check: "invented_dates_removed", label: "Invented dates removed", meaning: "news date not in the search results", total: 1, runs: 10, per_run: 0.1 },
      { check: "number_warnings", label: "Number warnings", meaning: "number in the cover note found nowhere", total: 4, runs: 10, per_run: 0.4 },
      { check: "draft_rewrites", label: "Draft rewrites", meaning: "times you asked for a new draft", total: 5, runs: 10, per_run: 0.5 },
    ],
    steps: [
      { node: "read_posting", avg_seconds: 23, count: 10, out_tokens: 600 },
      { node: "analyze_fit", avg_seconds: 82, count: 10, out_tokens: 2100 },
      { node: "research_company", avg_seconds: 48, count: 10, out_tokens: 1200 },
      { node: "save_to_tracker", avg_seconds: 0.4, count: 10, out_tokens: 0 },
      { node: "draft", avg_seconds: 28, count: 12, out_tokens: 900 },
    ],
    correlation: { output: 0.9, input: 0.16, calls: 90 },
    recent: [
      { run_id: "r11", started_at: "2026-10-21 10:00:00", model: "qwen3:8b", result: "approved", agent_seconds: 182, llm_calls: 9, tokens: 19400, pass_rate: 0.58, tracing: "langfuse", job: { id: 1, company: "Northwind Labs", title: "AI Engineer" } },
      { run_id: "r10", started_at: "2026-10-20 10:00:00", model: "qwen3:8b", result: "not finished", agent_seconds: 160, llm_calls: 9, tokens: 18200, pass_rate: 0.72, tracing: "off", job: { id: 3, company: "Peregrine AI", title: "Applied Scientist" } },
      { run_id: "r9", started_at: "2026-10-19 10:00:00", model: "claude-haiku-5-5", result: "rejected", agent_seconds: 48, llm_calls: 8, tokens: 17800, pass_rate: 0.74, tracing: "off", job: { id: 6, company: "Atlas Freight", title: "Full-stack Engineer" } },
    ],
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

function mockJob(row: JobRow): JobDetail {
  return {
    ...row,
    url: `https://jobs.example/${row.id}`,
    location: "Remote",
    seniority: "Mid",
    salary: "Not specified",
    job: {
      title: row.title,
      company: row.company,
      location: "Remote",
      employment_type: "Full-time",
      seniority: "Mid",
      salary: "Not specified",
      summary: "Build agent features and the evaluations that keep them honest.",
      required_skills: ["Python", "LLM applications", "Testing"],
      nice_to_have_skills: ["Kubernetes"],
      responsibilities: ["Ship agent features"],
    },
    best_match: {
      resume_name: row.best_resume,
      fit_score: row.fit_score,
      score_breakdown: "6 proven / (6 proven + 1 required gaps) = 86",
      analysis: {
        matching_skills: [{ requirement: "Python", resume_evidence: "Python, FastAPI, pytest" }],
        missing_skills: ["Kubernetes"],
        talking_points: [],
        verdict: "Strong match; the main gap is Kubernetes.",
      },
    },
    company_brief: {
      what_they_do: `${row.company} builds software for teams that work with data.`,
      products: ["Platform"],
      size_and_stage: "About 200 people, Series B",
      recent_news: ["Launched an agent platform (Sep 2026)"],
      culture_and_values: ["Remote-first"],
      cover_note_hooks: [],
      sources: ["https://example.com/about"],
    },
    cover_notes: row.status === "researched" ? [] : [{ id: 1, text: "Dear team,\n\nI would love to talk about the role.\n\n[Your name]", approved_at: row.updated_at }],
  };
}
