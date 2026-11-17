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

/** 18a: what Tauri puts on the page (withGlobalTauri). Only the Tauri spike has it. */
interface TauriGlobal {
  core: { invoke(command: string, args?: Record<string, unknown>): Promise<unknown> };
  event: { listen(name: string, handler: (event: { payload: unknown }) => void): Promise<unknown> };
}

declare global {
  interface Window {
    pywebview?: { api: PyApi };
    joblens?: { onEvent(event: AgentEvent): void };
    __joblens_ready?: { bridge: "pywebview" | "mock" | "tauri"; version: string };
    __TAURI__?: TauriGlobal;
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

export let bridgeKind: "pywebview" | "mock" | "tauri" = "pywebview";

/**
 * 18a: in the Tauri spike every `api.name(...args)` becomes one Rust
 * command, call(name, args), which passes it to the Python side; Python's
 * events arrive as "joblens-event". The page itself doesn't change.
 */
function tauriApi(tauri: TauriGlobal): PyApi {
  void tauri.event.listen("joblens-event", (e) => window.joblens?.onEvent(e.payload as AgentEvent));
  return new Proxy({} as PyApi, {
    get(_target, name) {
      // "then": a Promise resolving with this object checks for it; it must stay undefined.
      if (typeof name !== "string" || name === "then") return undefined;
      return (...args: unknown[]) => tauri.core.invoke("call", { method: name, args });
    },
  });
}

let apiPromise: Promise<PyApi> | null = null;

export function getApi(): Promise<PyApi> {
  apiPromise ??= new Promise<PyApi>((resolve, reject) => {
    if (window.__TAURI__) {
      bridgeKind = "tauri";
      return resolve(tauriApi(window.__TAURI__));
    }
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

/** Web links open in your browser: a plain <a href="https://..."> would navigate
 * the app window itself away from JobLens. Installed once, for the whole page. */
export function routeLinksToBrowser(): void {
  document.addEventListener("click", (e) => {
    const link = (e.target as Element | null)?.closest?.("a[href]") as HTMLAnchorElement | null;
    if (!link || !/^https?:/i.test(link.href) || link.origin === window.location.origin) return;
    e.preventDefault();
    getApi()
      .then((api) => api.open_link(link.href))
      .catch(() => undefined);
  });
}
