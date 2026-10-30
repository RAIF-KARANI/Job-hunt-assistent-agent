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
  status: string;
  updated_at: string;
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

export type PausedEvent =
  | { type: "paused"; kind: "review"; run_id: string; payload: ReviewPayload; summary: RunSummary }
  | { type: "paused"; kind: "paste_posting"; run_id: string; payload: PastePayload; summary: RunSummary };

export type AgentEvent =
  | { type: "busy"; busy: boolean }
  | { type: "log"; text: string }
  | PausedEvent
  | {
      type: "finished";
      run_id: string;
      saved_path: string | null;
      job_id: number | null;
      decision: "approve" | "reject" | null;
      suggested_rating: string | null;
    }
  | { type: "failed"; error: string };

export interface RunState {
  busy: boolean;
  run_id: string | null;
  paused: PausedEvent | null;
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
  feedback_options(): Promise<Record<string, string[]>>;
  statuses(): Promise<string[]>;
  list_jobs(): Promise<JobRow[]>;
  get_job(jobId: number): Promise<Record<string, unknown>>;
  set_status(jobId: number, status: string): Promise<void>;
  get_settings(): Promise<Settings>;
  save_settings(updates: Partial<Record<string, string>>): Promise<Settings>;
  set_api_key(key: string): Promise<Settings>;
}
