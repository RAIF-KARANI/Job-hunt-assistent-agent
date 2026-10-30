// Types for desktop_web/bridge.py. Keep the two in step: a renamed Python
// method or event field should fail `npm run typecheck`, not the user.

export type Theme = "system" | "dark" | "light";
export type Ui3D = "animated" | "still" | "off";

export interface Settings {
  LLM_PROVIDER: string;
  LLM_MODEL: string;
  TRACING: string;
  UI_3D?: Ui3D;
  UI_THEME?: Theme;
  SETUP_DONE?: string;
  ANTHROPIC_API_KEY_SET: boolean;
  [key: string]: string | boolean | undefined;
}

export interface AppInfo {
  version: string;
  installed: boolean;
  data_dir: string;
  settings: Settings;
  /** First launch: the wizard was never finished and there are no resumes. */
  setup_needed: boolean;
}

export interface LlmStatus {
  ok: boolean;
  message: string;
}

export interface JobRow {
  id: number;
  title: string;
  company: string;
  fit_score: number;
  best_resume: string;
  status: JobStatus;
  created_at: string; // UTC "YYYY-MM-DD HH:MM:SS": when the agent analyzed it
  updated_at: string; // last status change
}

export type JobStatus = "researched" | "cover_note_ready" | "applied" | "interviewing" | "offer" | "rejected";

export interface SkillMatch {
  requirement: string;
  resume_evidence: string;
}

export interface JobDetail {
  id: number;
  url: string;
  title: string;
  company: string;
  location: string | null;
  seniority: string | null;
  salary: string | null;
  fit_score: number;
  best_resume: string;
  status: JobStatus;
  created_at: string; // UTC "YYYY-MM-DD HH:MM:SS"
  updated_at: string;
  job: {
    title: string;
    company: string;
    location: string;
    employment_type: string;
    seniority: string;
    salary: string;
    summary: string;
    required_skills: string[];
    nice_to_have_skills: string[];
    responsibilities: string[];
  };
  best_match: {
    resume_name: string;
    fit_score: number;
    score_breakdown: string;
    analysis: { matching_skills: SkillMatch[]; missing_skills: string[]; talking_points: string[]; verdict: string };
  };
  company_brief: {
    what_they_do: string;
    products: string[];
    size_and_stage: string;
    recent_news: string[];
    culture_and_values: string[];
    cover_note_hooks: string[];
    sources: string[];
  } | null;
  cover_notes: { id: number; text: string; approved_at: string }[];
}

export interface RunSummary {
  title?: string;
  company?: string;
  fit_score?: number;
  breakdown?: string;
  resume?: string;
  matches?: { requirement: string; evidence: string }[];
  gaps?: string[];
}

export interface ReviewPayload {
  kind: "approval";
  draft: string;
  warnings: string[];
  revision: number;
  word_count: number;
}

export interface PastePayload {
  kind: "paste_posting";
  reason: string;
}

// `at` = Python's time.time() (seconds), on every event except log and busy.
export type PausedEvent =
  | { type: "paused"; kind: "review"; run_id: string; payload: ReviewPayload; summary: RunSummary; at: number }
  | { type: "paused"; kind: "paste_posting"; run_id: string; payload: PastePayload; summary: RunSummary; at: number };

export interface FinishedEvent {
  type: "finished";
  run_id: string;
  saved_path: string | null;
  job_id: number | null;
  decision: "approve" | "edit" | "reject" | null;
  suggested_rating: string | null;
  at: number;
}

/** Steps 1-4 come from the agent's "[n/5]" lines, step 5 is the cover note. */
export type StepNumber = 1 | 2 | 3 | 4 | 5;

export type AgentEvent =
  | { type: "busy"; busy: boolean }
  | { type: "log"; text: string }
  | { type: "started"; run_id: string; url: string; at: number }
  | { type: "step"; step: StepNumber; text: string; at: number }
  | { type: "step_detail"; step: StepNumber; text: string; warn: boolean; at: number }
  | { type: "reused"; job_id: number; at: number }
  | PausedEvent
  | FinishedEvent
  | { type: "failed"; error: string; at: number }
  | { type: "stopping"; at: number } // Stop pressed (12j)
  | { type: "stopped"; run_id: string; at: number } // the run ended at its next checkpoint
  | { type: "update_available"; latest: string; page: string } // 13b
  | { type: "update_progress"; done: number; total: number } // 13d: bytes
  | { type: "update_ready"; latest: string } // downloaded and verified
  | SetupProgress;

/** Api.update_status() / check_for_updates() (13b). */
export interface UpdateStatus {
  current: string;
  latest: string | null; // "v1.0.0"
  newer: boolean;
  page?: string; // the release page
  name?: string;
  notes?: string;
  installer?: { name: string; size: number; url: string; sha256: string | null } | null;
  checked_at: number | null; // seconds
  error: string | null;
  enabled: boolean; // the UPDATE_CHECK setting
}

/** Installing Ollama or downloading a model (12g). Not part of an agent run. */
export interface SetupProgress {
  type: "setup_progress";
  what: "install" | "pull";
  message: string;
  fraction: number | null; // 0..1 for the progress bar; null = no size yet
  done: boolean;
  ok: boolean | null;
}

export interface Resume {
  name: string;
  kb: number;
}

export type Verdict = "fast" | "slower" | "too big" | "no disk space";

export interface SystemCheck {
  info: { ram_gb: number; gpu_name: string | null; vram_gb: number | null; vram_exact: boolean; disk_free_gb: number; cpu_threads: number };
  advice: { name: string; download_gb: number; description: string; verdict: Verdict; reason: string; recommended: boolean }[];
  summary: string;
  ui3d: { level: Ui3D; reason: string };
}

export interface OllamaStatus {
  installed: boolean;
  running: boolean;
  models: string[];
  winget: boolean;
}

export interface RunState {
  busy: boolean;
  run_id: string | null;
  paused: PausedEvent | null;
  /** This run's events so far, so a reloaded page can replay them. */
  events: AgentEvent[];
}

export interface FeedbackOptions {
  fit_score: string[];
  cover_note: string[];
  [aspect: string]: string[];
}

export type Answer =
  | { decision: "approve"; text: string }
  | { decision: "edit"; feedback: string }
  | { decision: "reject" };

/** Api.dashboard(): run-log numbers from job_agent/monitoring.py. */
export interface DashboardData {
  days: number | null; // null = all time
  kpis: {
    runs: number;
    llm_calls: number;
    tokens_in: number;
    tokens_out: number;
    median_full_run: number | null; // seconds of agent work, runs with >= 5 LLM calls
    approved: number;
    decided: number;
    approval_rate: number | null;
  };
  decisions: { approve: number; edit: number; reject: number };
  /** Pipeline steps in order (monitoring.PIPELINE_NODES). */
  steps: { node: string; avg_seconds: number; max_seconds: number; count: number }[];
  /** Safety nets (monitoring.QUALITY_LABELS): catches per run that ran the check. */
  quality: { check: string; per_run: number; total: number; runs: number }[];
  pass_rate: number | null; // share of fit claims the evidence check kept
}

/** Api.evals(): monitoring.build_evals() — how well the agent did (D9). */
export interface EvalsData {
  model: string | null; // the filter; null = all models
  models: {
    model: string;
    provider: string; // "ollama" | "anthropic"
    runs: number;
    pass_rate: number | null;
    approved: number;
    decided: number;
    median_seconds: number | null;
    tokens_per_run: number | null;
  }[];
  kpis: {
    runs: number;
    pass_rate: number | null;
    pass_rate_delta: number | null; // latest `window` runs vs the `window` before
    pass_rate_window: number | null;
    approved: number;
    decided: number;
    median_seconds: number | null;
    full_runs: number;
    tokens_in_per_run: number | null;
    tokens_out_per_run: number | null;
    tool_calls: number;
    tool_failures: number;
    unfinished: number; // closed app, Stop or error (12j)
    unfinished_seconds: number;
  };
  trend: { run_id: string; started_at: string; rate: number }[]; // oldest first
  ratings: { label: string; aspect: string; rating: string; count: number }[];
  checks: { check: string; label: string; meaning: string; total: number; runs: number; per_run: number | null }[];
  steps: { node: string; avg_seconds: number; count: number; out_tokens: number }[];
  correlation: { output: number | null; input: number | null; calls: number };
  recent: {
    run_id: string;
    started_at: string;
    model: string;
    result: "approved" | "rejected" | "not finished" | "error" | "done" | "stopped" | "interrupted" | "running";
    agent_seconds: number;
    llm_calls: number;
    tokens: number;
    pass_rate: number | null;
    tracing: string; // what was on during that run: off / langfuse / langsmith
    job: { id: number; company: string; title: string } | null;
  }[];
}

export interface TracingStatus {
  mode: "off" | "langfuse" | "langsmith";
  langfuse: "off" | "running" | "not reachable";
  langfuse_sessions: string | null; // + run_id = that run's trace
  langsmith: "off" | "on" | "no key";
  langsmith_url: string;
}

/** window.pywebview.api: every public method of bridge.Api (all async from JS). */
export interface PyApi {
  app_info(): Promise<AppInfo>;
  llm_status(): Promise<LlmStatus>;
  start_run(url: string, fresh?: boolean): Promise<{ run_id: string }>;
  resume(answer: Answer): Promise<void>;
  paste_text(text: string): Promise<void>;
  stop_run(): Promise<boolean>;
  update_status(): Promise<UpdateStatus>;
  check_for_updates(): Promise<UpdateStatus>;
  /** 13d: download + verify (size and SHA-256 from GitHub); runs nothing. */
  download_update(): Promise<{ ok: boolean; latest: string; verified: boolean }>;
  /** 13d: run the verified installer; JobLens closes and the new version opens. */
  install_update(): Promise<{ ok: boolean }>;
  /** Typical seconds per timeline step on this PC: {"1": 27.4, "2": 66.4, ...}. */
  step_estimates(): Promise<Partial<Record<string, number>>>;
  run_state(): Promise<RunState>;
  save_feedback(runId: string | null, jobId: number | null, ratings: Record<string, string>, comment?: string): Promise<number>;
  feedback_options(): Promise<FeedbackOptions>;
  statuses(): Promise<JobStatus[]>;
  list_jobs(): Promise<JobRow[]>;
  get_job(jobId: number): Promise<JobDetail>;
  set_status(jobId: number, status: JobStatus): Promise<void>;
  open_link(url: string): Promise<void>;
  dashboard(days: number | null): Promise<DashboardData>;
  evals(model: string | null): Promise<EvalsData>;
  tracing_status(): Promise<TracingStatus>;
  list_resumes(): Promise<Resume[]>;
  add_resumes(): Promise<string[]>;
  remove_resume(name: string): Promise<void>;
  open_data_folder(): Promise<void>;
  system_check(provider?: string | null, model?: string | null): Promise<SystemCheck>;
  ollama_status(): Promise<OllamaStatus>;
  install_ollama(): Promise<{ ok: boolean; manual: boolean }>;
  pull_model(model: string): Promise<{ ok: boolean; model: string }>;
  test_api_key(key: string | null, model: string): Promise<LlmStatus>;
  get_settings(): Promise<Settings>;
  save_settings(updates: Partial<Record<string, string>>): Promise<Settings>;
  set_api_key(key: string): Promise<Settings>;
}
