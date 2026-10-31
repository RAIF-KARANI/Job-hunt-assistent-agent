// The quick-analyze box (14f): Ctrl+Alt+J anywhere opens this small window.
// Paste a link, press Enter: the run goes on in the background and Windows
// tells you (with a sound) when the cover note is ready.

import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { errorMessage, getApi } from "../bridge/bridge";
import type { QuickApi, Theme } from "../bridge/types";
import { useTheme } from "../app/useTheme";

declare global {
  interface Window {
    /** Called by Python each time the shortcut shows the box. */
    joblensQuick?: { opened(): void };
  }
}

type Phase = "ready" | "starting" | "started";

const quickApi = async () => (await getApi()) as unknown as QuickApi;

export function QuickBox() {
  const [url, setUrl] = useState("");
  const [phase, setPhase] = useState<Phase>("ready");
  const [error, setError] = useState<string | null>(null);
  const [theme, setTheme] = useState<Theme>("system");
  const input = useRef<HTMLInputElement>(null);
  const closeTimer = useRef<number | undefined>(undefined);
  useTheme(theme);

  const close = useCallback(() => {
    window.clearTimeout(closeTimer.current);
    void quickApi().then((api) => api.close());
  }, []);

  const opened = useCallback(() => {
    window.clearTimeout(closeTimer.current);
    setPhase("ready");
    setError(null);
    setUrl("");
    input.current?.focus();
    quickApi()
      .then((api) => api.clipboard_link())
      .then((link) => {
        if (link) setUrl((now) => now || link); // never over what you've started typing
        input.current?.select();
      })
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    window.joblensQuick = { opened };
    quickApi()
      .then((api) => api.app_info())
      .then((info) => {
        setTheme(info.settings.UI_THEME ?? "system");
        window.__joblens_ready = { bridge: "pywebview", version: info.version };
      })
      .catch(() => undefined);
    opened();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && close();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [opened, close]);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!url.trim() || phase !== "ready") return;
    setPhase("starting");
    setError(null);
    try {
      await (await quickApi()).quick_start(url.trim());
      setPhase("started");
      closeTimer.current = window.setTimeout(close, 1800);
    } catch (err) {
      setError(errorMessage(err));
      setPhase("ready");
      input.current?.focus();
    }
  };

  return (
    <main className="quick">
      <header className="quick-head pywebview-drag-region">
        <span className="quick-title">Quick analyze</span>
        <button type="button" className="btn btn-ghost icon-btn" aria-label="Close" onClick={close}>
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true">
            <path d="M3.5 3.5l9 9M12.5 3.5l-9 9" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
          </svg>
        </button>
      </header>
      {phase === "started" ? (
        <p className="quick-started" role="status">
          Started. Carry on with your day: you'll get a notification when the cover note is ready.
        </p>
      ) : (
        <form className="quick-form" onSubmit={submit}>
          <label className="sr-only" htmlFor="quick-url">
            Job link
          </label>
          <input
            id="quick-url"
            ref={input}
            className="input"
            type="url"
            placeholder="Paste the job link"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            disabled={phase === "starting"}
            autoComplete="off"
            spellCheck={false}
          />
          <button type="submit" className="btn btn-primary" disabled={!url.trim() || phase === "starting"}>
            {phase === "starting" ? "Checking…" : "Analyze"}
          </button>
        </form>
      )}
      {error ? (
        <p className="error quick-note" role="alert">
          {error}
        </p>
      ) : (
        phase !== "started" && <p className="hint quick-note">Runs in the background with your default resumes. Esc closes this box.</p>
      )}
    </main>
  );
}
