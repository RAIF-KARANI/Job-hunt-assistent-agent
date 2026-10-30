// The page's side of the bridge.
//
//   const api = await getApi();          // waits until Python's API exists
//   const jobs = await api.list_jobs();  // JS -> Python: calls that return
//   onEvent((e) => ...);                 // Python -> JS: one-way events
//
// Lessons from spike 12a: pywebview's "ready" event can fire BEFORE this
// module runs, so we check for the API first and only then listen. Events
// that arrive while the page is still loading are lost; callers catch up
// with api.run_state().

import { mockApi } from "./mock";
import type { AgentEvent, PyApi } from "./types";

declare global {
  interface Window {
    pywebview?: { api: PyApi };
    joblens?: { onEvent(event: AgentEvent): void };
    __joblens_ready?: { bridge: "pywebview" | "mock"; version: string };
  }
}

type Listener = (event: AgentEvent) => void;
const listeners = new Set<Listener>();

// bridge.window_sender() calls window.joblens.onEvent(...) for every event.
window.joblens = {
  onEvent(event) {
    for (const listener of listeners) listener(event);
  },
};

export function onEvent(listener: Listener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export let bridgeKind: "pywebview" | "mock" = "pywebview";

let apiPromise: Promise<PyApi> | null = null;

export function getApi(): Promise<PyApi> {
  apiPromise ??= new Promise<PyApi>((resolve, reject) => {
    const hasApi = () => typeof window.pywebview?.api?.app_info === "function";
    if (hasApi()) return resolve(window.pywebview!.api);

    const onReady = () => {
      if (hasApi()) {
        clearTimeout(timer);
        resolve(window.pywebview!.api);
      }
    };
    window.addEventListener("pywebviewready", onReady, { once: true });

    // Opened in a normal browser (`npm run dev`)? Use fake data so the UI
    // can be built and tested without Python. Never in a production build.
    const timer = setTimeout(
      () => {
        window.removeEventListener("pywebviewready", onReady);
        if (import.meta.env.DEV) {
          bridgeKind = "mock";
          resolve(mockApi(window.joblens!.onEvent));
        } else {
          reject(new Error("JobLens couldn't connect to its engine. Restart the app."));
        }
      },
      import.meta.env.DEV ? 800 : 15000,
    );
  });
  return apiPromise;
}

/** A readable message from a rejected call (pywebview rejects with plain objects, not Errors). */
export function errorMessage(e: unknown): string {
  if (e instanceof Error) return e.message;
  if (e && typeof e === "object" && "message" in e) return String((e as { message: unknown }).message);
  return String(e);
}
