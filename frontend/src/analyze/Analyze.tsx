// Analyze screen (12d): paste a link, watch the agent's steps live, then
// approve, rewrite or reject the cover note.
//
//   ┌ link ............................................ [Analyze] ┐
//   ┌ What the agent is doing ┐  ┌ Cover note draft / paste / result ┐
//   │ 1 ✓ Read the posting 22s │  │                                    │
//   │ ...                      │  │                                    │
//   ├ Live log ────────────────┤  │                                    │

import { useEffect, useState, type FormEvent } from "react";
import { errorMessage, getApi } from "../bridge/bridge";
import type { Answer } from "../bridge/types";
import { ContinueBanner } from "./ContinueBanner";
import { LiveLog } from "./LiveLog";
import { PastePanel } from "./PastePanel";
import { ResultPanel } from "./ResultPanel";
import { ResumeChoice } from "./ResumeChoice";
import { ReviewPanel, WarnIcon } from "./ReviewPanel";
import { dismiss, markBusy, useRun, type RunView } from "./runStore";
import { Steps } from "./Steps";
import { formatDuration, useNow } from "./time";

export function Analyze() {
  const run = useRun();
  const [url, setUrl] = useState(run.url);
  const [fresh, setFresh] = useState(false);
  const [resumes, setResumes] = useState<string[] | null>(null); // 14b: this job's resumes
  const [checking, setChecking] = useState(false);
  const [problem, setProblem] = useState<{ text: string; settings: boolean } | null>(null);
  const [estimates, setEstimates] = useState<Partial<Record<string, number>>>({});

  // A run that started before this page opened (or before a reload) shows its link.
  useEffect(() => {
    if (run.url) setUrl((current) => current || run.url);
  }, [run.url]);

  // Typical step times on this PC (12j), refreshed when a run ends.
  useEffect(() => {
    if (run.busy) return;
    getApi()
      .then((api) => api.step_estimates())
      .then(setEstimates)
      .catch(() => setEstimates({}));
  }, [run.busy]);

  const waiting = run.phase === "review" || run.phase === "paste";
  const locked = checking || run.busy || waiting;

  const start = async (e?: FormEvent) => {
    e?.preventDefault();
    const link = url.trim();
    if (!link || locked) return;
    setProblem(null);
    setChecking(true);
    try {
      const api = await getApi();
      const status = await api.llm_status(); // ~2 s; better than failing 3 minutes in
      if (!status.ok) {
        setProblem({ text: status.message, settings: true });
        return;
      }
      await api.start_run(link, fresh, resumes);
    } catch (err) {
      setProblem({ text: errorMessage(err), settings: false });
    } finally {
      setChecking(false);
    }
  };

  const call = async (send: (api: Awaited<ReturnType<typeof getApi>>) => Promise<void>) => {
    setProblem(null);
    markBusy(true);
    try {
      await send(await getApi());
    } catch (err) {
      markBusy(false);
      setProblem({ text: errorMessage(err), settings: false });
    }
  };
  const answer = (a: Answer) => call((api) => api.resume(a));
  const paste = (text: string) => call((api) => api.paste_text(text));

  /** 14d: pick the stopped run up after its last finished step. */
  const carryOn = () =>
    call(async (api) => {
      const status = await api.llm_status();
      if (!status.ok) throw new Error(status.message);
      await api.continue_run(run.runId!);
    });

  const another = () => {
    dismiss();
    setUrl("");
    setFresh(false);
  };

  return (
    <div className="page analyze">
      <header className="page-head">
        <h1>Analyze a job</h1>
        <p>The agent reads the posting, scores your resumes, researches the company, then drafts a cover note for you to review.</p>
      </header>

      <form className="analyze-form" onSubmit={start}>
        <div className="field grow">
          <label htmlFor="job-url">Job posting link</label>
          <input
            id="job-url"
            className="input"
            type="text"
            inputMode="url"
            autoComplete="off"
            spellCheck={false}
            placeholder="https://job-boards.greenhouse.io/..."
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            disabled={locked}
          />
        </div>
        <label className="check">
          <input type="checkbox" checked={fresh} onChange={(e) => setFresh(e.target.checked)} disabled={locked} />
          <span>Analyze again if already tracked</span>
        </label>
        <StartButton run={run} checking={checking} disabled={locked || !url.trim()} />
        {run.busy && run.phase === "running" && <StopControl stopping={run.stopping} />}
      </form>
      <ResumeChoice value={resumes} onChange={setResumes} disabled={locked} />
      {run.phase === "idle" && !run.busy && <ContinueBanner refresh={run.runId} disabled={checking} />}

      {problem && (
        <div className="notice notice-danger" role="alert">
          <WarnIcon />
          <span>
            {problem.text}
            {problem.settings && (
              <>
                {" "}
                <a href="#/settings">Open Settings</a>
              </>
            )}
          </span>
        </div>
      )}

      <div className="analyze-grid">
        <section className="analyze-progress" aria-label="Agent progress">
          <Steps steps={run.steps} estimates={estimates} />
          <LiveLog lines={run.log} />
        </section>
        <div className="analyze-panel">
          <Panel run={run} onAnswer={answer} onPaste={paste} onAnother={another} onRetry={() => void start()} onContinue={() => void carryOn()} />
        </div>
      </div>
    </div>
  );
}

function StartButton({ run, checking, disabled }: { run: RunView; checking: boolean; disabled: boolean }) {
  const now = useNow(run.busy);
  const waiting = run.phase === "review" || run.phase === "paste";
  let label = "Analyze";
  if (checking) label = "Checking the model...";
  else if (waiting) label = "Waiting for you";
  else if (run.busy) label = run.startedAt ? `Running · ${formatDuration(now - run.startedAt)}` : "Running...";
  const status = label !== "Analyze";
  return (
    <button type="submit" className={`btn start ${status ? `btn-status${waiting ? " waiting" : ""}` : "btn-primary"}`} disabled={disabled}>
      {label}
    </button>
  );
}

/** Stop the running step (12j). Asks once, like Reject (D17): a run is minutes of work. */
function StopControl({ stopping }: { stopping: boolean }) {
  const [confirm, setConfirm] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const stop = async () => {
    setError(null);
    try {
      await (await getApi()).stop_run();
    } catch (e) {
      setError(errorMessage(e));
    }
  };

  if (stopping) {
    return (
      <button type="button" className="btn btn-secondary start" disabled>
        Stopping…
      </button>
    );
  }
  if (!confirm) {
    return (
      <button type="button" className="btn btn-secondary start" onClick={() => setConfirm(true)}>
        Stop
      </button>
    );
  }
  return (
    <span className="stop-confirm" role="group" aria-label="Stop this run?">
      <span className="hint">Stop this run? Nothing is saved.</span>
      <button type="button" className="btn btn-danger btn-sm" onClick={() => void stop()} autoFocus>
        Stop
      </button>
      <button type="button" className="btn btn-ghost btn-sm" onClick={() => setConfirm(false)}>
        Keep going
      </button>
      {error && <span className="error">{error}</span>}
    </span>
  );
}

interface PanelProps {
  run: RunView;
  onAnswer(answer: Answer): void;
  onPaste(text: string): void;
  onAnother(): void;
  onRetry(): void;
  onContinue(): void;
}

function Panel({ run, onAnswer, onPaste, onAnother, onRetry, onContinue }: PanelProps) {
  switch (run.phase) {
    case "review":
      return (
        // A new draft (after a rewrite) starts a fresh editor.
        <ReviewPanel
          key={`${run.runId}-${run.review!.payload.revision}`}
          payload={run.review!.payload}
          summary={run.review!.summary}
          busy={run.busy}
          onAnswer={onAnswer}
        />
      );
    case "paste":
      return <PastePanel key={run.runId} payload={run.paste!} busy={run.busy} onPaste={onPaste} onStop={onAnother} />;
    case "finished":
      return <ResultPanel key={run.runId} result={run.result!} onAnother={onAnother} />;
    case "stopped":
      return (
        <section className="card review" aria-labelledby="stopped-title">
          <header className="panel-head">
            <h2 id="stopped-title">Stopped</h2>
          </header>
          <p className="lead">
            You stopped the run. Nothing was saved to the tracker. Continue picks it up at the step you stopped; the steps already
            finished aren't redone.
          </p>
          <div className="actions">
            <button type="button" className="btn btn-primary" onClick={onContinue} disabled={run.busy}>
              Continue
            </button>
            <button type="button" className="btn btn-secondary" onClick={onRetry} disabled={run.busy}>
              Start again
            </button>
            <button type="button" className="btn btn-ghost" onClick={onAnother}>
              Clear
            </button>
          </div>
        </section>
      );
    case "failed":
      return (
        <section className="card review" aria-labelledby="failed-title">
          <header className="panel-head">
            <h2 id="failed-title" className="danger-ink">
              Something went wrong
            </h2>
          </header>
          <p className="lead">The agent stopped. Nothing new was saved after the last finished step.</p>
          <pre className="error-box">{run.error}</pre>
          <div className="actions">
            <button type="button" className="btn btn-primary" onClick={onRetry} disabled={run.busy}>
              Try again
            </button>
            <button type="button" className="btn btn-ghost" onClick={onAnother}>
              Clear
            </button>
          </div>
        </section>
      );
    default: {
      const rewriting = run.steps[4].status === "running";
      return (
        <section className="card review empty" aria-labelledby="draft-title">
          <header className="panel-head">
            <h2 id="draft-title">Cover note draft</h2>
          </header>
          {run.phase === "running" ? (
            <p className="lead">{rewriting ? "The agent is writing the draft..." : "The draft appears here when the agent gets to it."}</p>
          ) : (
            <>
              <p className="lead">Paste a job link above to start. When the draft is ready the agent pauses here and waits for you:</p>
              <ul className="how">
                <li>
                  <strong>Approve</strong> it as it is, or after editing the text yourself
                </li>
                <li>
                  <strong>Rewrite</strong>: tell the agent what to change
                </li>
                <li>
                  <strong>Reject</strong> it: nothing is saved
                </li>
              </ul>
            </>
          )}
        </section>
      );
    }
  }
}
