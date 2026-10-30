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
      return (
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true">
          <path d="M3 3l6 6M9 3l-6 6" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
        </svg>
      );
    default:
      return <span aria-hidden="true">{step.n}</span>;
  }
}

export function Steps({ steps }: { steps: Step[] }) {
  const live = steps.some((s) => s.status === "running" || s.status === "waiting");
  const now = useNow(live);

  return (
    <div className="card steps-card">
      <h2>What the agent is doing</h2>
      <ol className="steps">
        {steps.map((step) => {
          const end = step.endedAt ?? (step.status === "running" || step.status === "waiting" ? now : null);
          const took = step.startedAt !== null && end !== null && step.status !== "reused" ? formatDuration(end - step.startedAt) : null;
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
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
