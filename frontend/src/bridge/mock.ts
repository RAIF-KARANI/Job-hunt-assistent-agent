// Fake bridge for `npm run dev` in a normal browser: just enough data to
// build and look at screens without Python. Not included in production
// builds (bridge.ts only loads it when import.meta.env.DEV).

import type { AgentEvent, JobRow, PyApi, Settings } from "./types";

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
  void emit; // later screens use it to fake a run

  return {
    app_info: async () => ({ version: "dev", installed: false, data_dir: "(browser preview)", settings }),
    llm_status: async () => ({ ok: true, message: "Preview: pretend 'qwen3:8b' is ready." }),
    run_state: async () => ({ busy: false, run_id: null, paused: null }),
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
    start_run: notInMock,
    resume: notInMock,
    paste_text: notInMock,
    save_feedback: notInMock,
    get_job: notInMock,
    set_status: notInMock,
  };
}
