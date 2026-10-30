// Settings → Updates (13c, D26): this version, the newest on GitHub, the
// once-a-day switch and "Check now".

import { useEffect, useState } from "react";
import { errorMessage, getApi, onEvent } from "../bridge/bridge";
import type { UpdateStatus } from "../bridge/types";

function checkedAgo(seconds: number | null): string {
  if (!seconds) return "not checked yet";
  const minutes = Math.round((Date.now() / 1000 - seconds) / 60);
  if (minutes < 1) return "checked just now";
  if (minutes < 60) return `checked ${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  return hours < 24 ? `checked ${hours} h ago` : `checked ${new Date(seconds * 1000).toLocaleDateString()}`;
}

/** The checker's error, in words (it keeps the exception's name for the log). */
function plainError(error: string): string {
  if (/ConnectionError|Timeout|NameResolution|getaddrinfo/i.test(error)) return "Couldn't reach GitHub (no internet?).";
  if (/403|429|rate limit/i.test(error)) return "GitHub asked to wait (too many requests). It'll try again later.";
  return `The check failed: ${error}`;
}

export function UpdatesCard({ enabled, onToggle }: { enabled: boolean; onToggle(on: boolean): void }) {
  const [status, setStatus] = useState<UpdateStatus | null>(null);
  const [checking, setChecking] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  useEffect(() => {
    getApi()
      .then((api) => api.update_status())
      .then(setStatus)
      .catch(() => setStatus(null));
    // The background check (13b) may finish while this page is open.
    return onEvent((e) => {
      if (e.type === "update_available") {
        getApi()
          .then((api) => api.update_status())
          .then(setStatus)
          .catch(() => undefined);
      }
    });
  }, []);

  const checkNow = async () => {
    setChecking(true);
    setProblem(null);
    try {
      setStatus(await (await getApi()).check_for_updates());
    } catch (e) {
      setProblem(errorMessage(e));
    } finally {
      setChecking(false);
    }
  };

  const latest = status?.latest;
  return (
    <div className="updates">
      <p className="update-state" role="status" aria-live="polite">
        {!status ? (
          "…"
        ) : status.newer && latest ? (
          <>
            <strong>Version {latest.replace(/^v/, "")} is available</strong> (you have {status.current}).{" "}
            {status.page && <a href={status.page}>See what's new and download</a>}
          </>
        ) : latest ? (
          <>
            <strong>You're up to date</strong>: JobLens {status.current} is the newest version.
          </>
        ) : (
          <>JobLens {status.current}.</>
        )}
      </p>
      <p className="hint">
        {status ? checkedAgo(status.checked_at) : ""}
        {status?.error && ` · ${plainError(status.error)}`}
      </p>

      <label className="check">
        <input type="checkbox" checked={enabled} onChange={(e) => onToggle(e.target.checked)} />
        <span>
          Check for updates automatically (once a day)
          <span className="hint">Asks GitHub for the newest release. Only the app's version is sent; nothing about you or your jobs.</span>
        </span>
      </label>

      <div className="row-actions">
        <button type="button" className="btn btn-secondary" onClick={() => void checkNow()} disabled={checking}>
          {checking ? "Checking…" : "Check now"}
        </button>
      </div>
      {problem && (
        <p className="error" role="alert">
          {problem}
        </p>
      )}
    </div>
  );
}
