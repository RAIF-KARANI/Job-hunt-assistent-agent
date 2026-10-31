// 14d: "Your last run didn't finish": Continue picks it up after its last
// finished step (finished steps aren't redone); Discard stops offering it.

import { useEffect, useState } from "react";
import { errorMessage, getApi } from "../bridge/bridge";
import type { UnfinishedRun } from "../bridge/types";
import { parseUtc } from "../tracker/status";
import { STEP_TITLES } from "./runStore";

function where(run: UnfinishedRun): string {
  if (run.status === "paused") {
    return run.next_step === 1 ? "It was waiting for you to paste the job text." : "The cover note is waiting for your decision.";
  }
  const how = run.status === "stopped" ? "You stopped it" : "JobLens was closed";
  return `${how} during step ${run.next_step} (${STEP_TITLES[run.next_step]}).`;
}

interface Props {
  /** Re-ask Python after this changes (a run ended or was cleared). */
  refresh: unknown;
  disabled: boolean;
}

export function ContinueBanner({ refresh, disabled }: Props) {
  const [run, setRun] = useState<UnfinishedRun | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    getApi()
      .then((api) => api.unfinished_run())
      .then((r) => live && setRun(r))
      .catch(() => live && setRun(null));
    return () => {
      live = false;
    };
  }, [refresh]);

  if (!run) return null;

  const act = async (what: "continue" | "discard") => {
    setBusy(true);
    setError(null);
    try {
      const api = await getApi();
      if (what === "continue") {
        if (run.status !== "paused") {
          const status = await api.llm_status(); // as Analyze does: fail now, not minutes in
          if (!status.ok) throw new Error(status.message);
        }
        await api.continue_run(run.run_id);
      } else {
        await api.discard_run(run.run_id);
      }
      setRun(null);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  const job = run.title ? `${run.title}${run.company ? ` at ${run.company}` : ""}` : run.url;
  const when = parseUtc(run.updated_at).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
  return (
    <section className="continue-banner" aria-labelledby="continue-title">
      <div className="continue-text">
        <h2 id="continue-title">Your last run didn't finish</h2>
        <p>
          <strong>{job}</strong> · {when}
        </p>
        <p className="hint">
          {where(run)} {run.done.length > 0 && `Continue keeps the ${run.done.length} finished step${run.done.length > 1 ? "s" : ""}.`}
        </p>
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
      </div>
      <div className="continue-actions">
        <button type="button" className="btn btn-primary" onClick={() => void act("continue")} disabled={busy || disabled}>
          Continue
        </button>
        <button type="button" className="btn btn-ghost" onClick={() => void act("discard")} disabled={busy || disabled}>
          Discard
        </button>
      </div>
    </section>
  );
}
