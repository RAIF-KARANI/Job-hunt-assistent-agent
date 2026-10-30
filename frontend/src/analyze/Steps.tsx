// "What the agent is doing": the five steps, each with its live status.

import type { Step, StepStatus } from "./runStore";
import { formatDuration, useNow } from "./time";

const SPOKEN: Record<StepStatus, string> = {
  pending: "not started",
  running: "in progress",
  done: "done",
  reused: "reused from the tracker",
  waiting: "waiting for you",
  failed: "failed",
  stopped: "stopped",
};

function Marker({ step }: { step: Step }) {
  switch (step.status) {
    case "done":
    case "reused":
      return (
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true">
          <path d="M2.5 6.2l2.4 2.3 4.6-5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      );
    case "waiting":
      return (
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true">
          <path d="M4 2.5v7M8 2.5v7" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
        </svg>
      );
    case "failed":
    case "stopped":
      return (
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true">
          <path d="M3 3l6 6M9 3l-6 6" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
        </svg>
      );
    default:
      return <span aria-hidden="true">{step.n}</span>;
  }
}

/** "16s", or "16s · 3m 33s waiting for you" when the step also waited for you (step 5). */
function timing(step: Step, now: number): string | null {
  if (step.status === "reused" || step.startedAt === null) return null;
  const end = step.endedAt ?? (step.status === "running" || step.status === "waiting" ? now : null);
  if (end === null) return null;
  const worked = step.workedMs + (step.status === "running" && step.runningSince !== null ? now - step.runningSince : 0);
  const waited = end - step.startedAt - worked;
  return waited >= 1000 ? `${formatDuration(worked)} · ${formatDuration(waited)} waiting for you` : formatDuration(end - step.startedAt);
}

interface Props {
  steps: Step[];
  /** Typical seconds per step on this PC (12j), keyed "1".."5". */
  estimates?: Partial<Record<string, number>>;
}

export function Steps({ steps, estimates = {} }: Props) {
  const live = steps.some((s) => s.status === "running" || s.status === "waiting");
  const now = useNow(live);
  const running = steps.some((s) => s.status === "running");
  const total = Object.values(estimates).reduce<number>((sum, s) => sum + (s ?? 0), 0);

  return (
    <div className="card steps-card">
      <h2>What the agent is doing</h2>
      {running && total >= 60 && (
        <p className="hint steps-estimate">A run usually takes about {formatDuration(total * 1000)} on this PC, plus the time you spend on the draft.</p>
      )}
      <ol className="steps">
        {steps.map((step) => {
          const took = timing(step, now);
          const usual = estimates[String(step.n)];
          return (
            <li key={step.n} className="step" data-status={step.status}>
              <span className="step-marker">
                <Marker step={step} />
              </span>
              <div className="step-body">
                <div className="step-line">
                  <span className="step-title">
                    {step.n === 5 && step.status === "waiting" ? "Cover note: waiting for your decision" : step.title}
                  </span>
                  <span className="sr-only">, {SPOKEN[step.status]}</span>
                  {took && <span className="step-time">{took}</span>}
                </div>
                {step.detail && <span className={step.warn ? "step-detail warn" : "step-detail"}>{step.detail}</span>}
                {step.status === "running" && usual !== undefined && usual >= 5 && (
                  <span className="step-usual">usually about {formatDuration(usual * 1000)} here</span>
                )}
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
