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
  | { type: "failed"; error: string; at: number };

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

/** window.pywebview.api: every public method of bridge.Api (all async from JS). */
export interface PyApi {
  app_info(): Promise<AppInfo>;
  llm_status(): Promise<LlmStatus>;
  start_run(url: string, fresh?: boolean): Promise<{ run_id: string }>;
  resume(answer: Answer): Promise<void>;
  paste_text(text: string): Promise<void>;
  run_state(): Promise<RunState>;
  save_feedback(runId: string | null, jobId: number | null, ratings: Record<string, string>, comment?: string): Promise<number>;
  feedback_options(): Promise<FeedbackOptions>;
  statuses(): Promise<JobStatus[]>;
  list_jobs(): Promise<JobRow[]>;
  get_job(jobId: number): Promise<JobDetail>;
  set_status(jobId: number, status: JobStatus): Promise<void>;
  open_link(url: string): Promise<void>;
  get_settings(): Promise<Settings>;
  save_settings(updates: Partial<Record<string, string>>): Promise<Settings>;
  set_api_key(key: string): Promise<Settings>;
}
