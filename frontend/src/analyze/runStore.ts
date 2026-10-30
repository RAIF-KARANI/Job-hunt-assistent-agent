// The current agent run, as the Analyze screen shows it.
//
// It lives outside React on purpose: switching to the Tracker mid-run
// unmounts the Analyze page, but the run (and its log) must still be there
// when you come back. Every Python event goes through one pure function,
// reduce(), so a reloaded page can rebuild the same view by replaying the
// run's events from api.run_state().

import { useSyncExternalStore } from "react";
import { getApi, onEvent } from "../bridge/bridge";
import type { AgentEvent, FinishedEvent, PastePayload, ReviewPayload, RunSummary, StepNumber } from "../bridge/types";

export type StepStatus = "pending" | "running" | "done" | "reused" | "waiting" | "failed";

export interface Step {
  n: StepNumber;
  title: string;
  status: StepStatus;
  detail: string | null;
  warn: boolean;
  startedAt: number | null; // ms
  endedAt: number | null; // ms
}

export type Phase = "idle" | "running" | "review" | "paste" | "finished" | "failed";

export interface RunView {
  phase: Phase;
  busy: boolean;
  runId: string | null;
  url: string;
  startedAt: number | null; // ms
  steps: Step[];
  log: string[];
  review: { payload: ReviewPayload; summary: RunSummary; at: number } | null;
  paste: PastePayload | null;
  result: FinishedEvent | null;
  error: string | null;
}

export const STEP_TITLES: Record<StepNumber, string> = {
  1: "Read the posting",
  2: "Compare with your resumes",
  3: "Research the company",
  4: "Save to tracker",
  5: "Cover note",
};

const MAX_LOG_LINES = 600;

function freshSteps(): Step[] {
  return ([1, 2, 3, 4, 5] as const).map((n) => ({
    n,
    title: STEP_TITLES[n],
    status: "pending",
    detail: null,
    warn: false,
    startedAt: null,
    endedAt: null,
  }));
}

export const IDLE: RunView = {
  phase: "idle",
  busy: false,
  runId: null,
  url: "",
  startedAt: null,
  steps: freshSteps(),
  log: [],
  review: null,
  paste: null,
  result: null,
  error: null,
};

const ms = (seconds: number) => seconds * 1000;

/** Finish every running step (a later step started, or the run paused/ended). */
function closeRunning(steps: Step[], at: number, status: StepStatus = "done"): Step[] {
  return steps.map((s) => (s.status === "running" ? { ...s, status, endedAt: at } : s));
}

function setStep(steps: Step[], n: StepNumber, change: Partial<Step>): Step[] {
  return steps.map((s) => (s.n === n ? { ...s, ...change } : s));
}

export function reduce(view: RunView, event: AgentEvent): RunView {
  switch (event.type) {
    case "busy":
      return { ...view, busy: event.busy };

    case "log": {
      const log = view.log.length >= MAX_LOG_LINES ? view.log.slice(-MAX_LOG_LINES + 1) : view.log.slice();
      log.push(event.text);
      return { ...view, log };
    }

    case "started":
      return { ...IDLE, busy: view.busy, phase: "running", runId: event.run_id, url: event.url, startedAt: ms(event.at), steps: freshSteps() };

    case "step": {
      const at = ms(event.at);
      const steps = closeRunning(view.steps, at).map((s) =>
        // A step that was skipped over (e.g. 4 after a paste) still counts as done.
        s.n < event.step && s.status === "pending" ? { ...s, status: "done" as const } : s,
      );
      return {
        ...view,
        phase: "running",
        review: null,
        paste: null,
        steps: setStep(steps, event.step, { status: "running", detail: event.text, warn: false, startedAt: at, endedAt: null }),
      };
    }

    case "step_detail":
      return { ...view, steps: setStep(view.steps, event.step, { detail: event.text, warn: event.warn }) };

    case "reused": {
      const at = ms(event.at);
      return {
        ...view,
        steps: view.steps.map((s) =>
          s.n < 5 ? { ...s, status: "reused", detail: `Saved analysis of job #${event.job_id} reused`, startedAt: at, endedAt: at } : s,
        ),
      };
    }

    case "paused": {
      const at = ms(event.at);
      if (event.kind === "paste_posting") {
        return {
          ...view,
          phase: "paste",
          paste: event.payload,
          steps: setStep(closeRunning(view.steps, at), 1, {
            status: "waiting",
            detail: "Couldn't read the page: paste the job text",
            warn: true,
            startedAt: view.steps[0].startedAt ?? at,
            endedAt: null,
          }),
        };
      }
      const steps = closeRunning(view.steps, at);
      return {
        ...view,
        phase: "review",
        review: { payload: event.payload, summary: event.summary, at },
        steps: setStep(steps, 5, {
          status: "waiting",
          detail: "Waiting for your decision. Nothing is saved until you approve",
          warn: false,
          startedAt: steps[4].startedAt ?? at,
          endedAt: null,
        }),
      };
    }

    case "finished": {
      const at = ms(event.at);
      const detail =
        event.decision === "approve" ? "Approved and saved" : event.decision === "reject" ? "Rejected: nothing saved" : view.steps[4].detail;
      const steps = closeRunning(view.steps, at).map((s) => (s.status === "waiting" ? { ...s, status: "done" as const, endedAt: at } : s));
      return {
        ...view,
        phase: "finished",
        review: null,
        paste: null,
        result: event,
        steps: event.decision ? setStep(steps, 5, { status: "done", detail, warn: false }) : steps,
      };
    }

    case "failed":
      return { ...view, phase: "failed", error: event.error, review: null, paste: null, steps: closeRunning(view.steps, ms(event.at), "failed") };
  }
}

// ---- the store --------------------------------------------------------------

let view: RunView = IDLE;
const subscribers = new Set<() => void>();

function set(next: RunView) {
  view = next;
  for (const notify of subscribers) notify();
}

onEvent((event) => set(reduce(view, event)));

/** Once per page load: rebuild the view of a run that started before this page did. */
let caughtUp = false;
export function catchUp(): void {
  if (caughtUp) return;
  caughtUp = true;
  getApi()
    .then((api) => api.run_state())
    .then((state) => {
      if (view.runId || !state.events.length) return; // live events already arrived
      set({ ...state.events.reduce(reduce, IDLE), busy: state.busy });
    })
    .catch(() => undefined);
}

/** Back to the empty screen (after a finished run, or to give up on a paste). */
export function dismiss(): void {
  if (!view.busy) set({ ...IDLE });
}

/** Fill in the Analyze form (from the Tracker's "Draft a cover note"). Ignored while a run needs you. */
export function prefill(url: string): boolean {
  if (view.busy || view.phase === "review" || view.phase === "paste") return false;
  set({ ...IDLE, url });
  return true;
}

/** Local-only change: "sending your answer" before Python's busy event arrives, or undo it if the call failed. */
export function markBusy(busy: boolean): void {
  set({ ...view, busy });
}

export function useRun(): RunView {
  return useSyncExternalStore(
    (notify) => {
      subscribers.add(notify);
      return () => subscribers.delete(notify);
    },
    () => view,
  );
}
