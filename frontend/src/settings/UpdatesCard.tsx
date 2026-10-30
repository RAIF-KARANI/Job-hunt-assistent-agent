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

const MB = (bytes: number) => `${(bytes / 1e6).toFixed(0)} MB`;

/** 13d (D27): download → verified → install. Nothing runs until the file
 *  matches the size and SHA-256 GitHub published for it. */
function InstallUpdate({ status }: { status: UpdateStatus }) {
  const installer = status.installer!;
  const [step, setStep] = useState<"idle" | "downloading" | "ready" | "installing">("idle");
  const [progress, setProgress] = useState<{ done: number; total: number } | null>(null);
  const [problem, setProblem] = useState<string | null>(null);

  useEffect(
    () =>
      onEvent((e) => {
        if (e.type === "update_progress") setProgress({ done: e.done, total: e.total });
      }),
    [],
  );

  const run = async (call: "download_update" | "install_update") => {
    setProblem(null);
    setStep(call === "download_update" ? "downloading" : "installing");
    try {
      await (await getApi())[call]();
      setStep(call === "download_update" ? "ready" : "installing"); // installing: JobLens is about to close
    } catch (e) {
      setProblem(errorMessage(e));
      setStep(call === "download_update" ? "idle" : "ready");
    }
  };

  const fraction = progress && progress.total ? progress.done / progress.total : null;
  return (
    <div className="install-update">
      {step === "idle" && (
        <button type="button" className="btn btn-primary" onClick={() => void run("download_update")}>
          Download and install {status.latest} ({MB(installer.size)})
        </button>
      )}
      {step === "downloading" && (
        <>
          <p className="hint" role="status">
            Downloading {installer.name}… {progress ? `${MB(progress.done)} of ${MB(progress.total)}` : ""}
          </p>
          <div className="progress" role="progressbar" aria-label="Downloading the update" aria-valuemin={0} aria-valuemax={100}
            aria-valuenow={fraction === null ? undefined : Math.round(fraction * 100)}>
            <span className={fraction === null ? "progress-fill indeterminate" : "progress-fill"} style={fraction === null ? undefined : { width: `${fraction * 100}%` }} />
          </div>
        </>
      )}
      {step === "ready" && (
        <>
          <p className="check-status ok" role="status">
            <span aria-hidden="true">✓</span> Downloaded and verified: size and SHA-256 match what GitHub published.
          </p>
          <div className="row-actions">
            <button type="button" className="btn btn-primary" onClick={() => void run("install_update")}>
              Install now
            </button>
            <span className="hint">JobLens closes, updates, and opens again. Your data stays.</span>
          </div>
        </>
      )}
      {step === "installing" && (
        <p className="hint" role="status">
          Installing {status.latest}… JobLens will open again in a moment.
        </p>
      )}
      {problem && (
        <p className="error" role="alert">
          {problem}
        </p>
      )}
    </div>
  );
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

      {/* Right under "Version X is available": the one thing to do next. */}
      {status?.newer && status.installer && <InstallUpdate status={status} />}

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
