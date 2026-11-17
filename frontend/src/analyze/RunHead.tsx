// 17f: the top of the run card. Where the run is ("Step 2 of 5"), its
// state, how long it has taken and how long it usually takes, and one bar
// for the whole run (feature F25).

import type { RunView } from "./runStore";
import { formatDuration, useNow } from "./time";

interface Props {
  run: RunView;
  /** Typical seconds per step on this PC (12j), keyed "1".."5". */
  estimates: Partial<Record<string, number>>;
}

export function RunHead({ run, estimates }: Props) {
  const now = useNow(run.busy);
  const steps = run.steps;
  const finished = steps.filter((s) => s.status === "done" || s.status === "reused").length;
  // The step the run is at: the one in progress, else the one waiting for you, else where it stopped.
  const at =
    steps.find((s) => s.status === "running") ??
    steps.find((s) => s.status === "waiting") ??
    steps.find((s) => s.status === "failed" || s.status === "stopped");
  const usual = Object.values(estimates).reduce<number>((sum, s) => sum + (s ?? 0), 0);

  let title = "The five steps";
  let state: { text: string; tone: string } | null = null;
  switch (run.phase) {
    case "running":
      title = at ? `Step ${at.n} of 5` : "Starting";
      state = { text: "Running", tone: "run" };
      break;
    case "review":
      title = "Step 5 of 5";
      state = { text: "Your decision", tone: "wait" };
      break;
    case "paste":
      title = at ? `Step ${at.n} of 5` : "Step 1 of 5";
      state = { text: "Needs the posting text", tone: "wait" };
      break;
    case "finished":
      title = "All five steps";
      state = { text: "Done", tone: "done" };
      break;
    case "failed":
      title = at ? `Stopped at step ${at.n}` : "Stopped";
      state = { text: run.quota ? "API limit used up" : "Something went wrong", tone: "fail" };
      break;
    case "stopped":
      title = at ? `Stopped at step ${at.n}` : "Stopped";
      state = { text: "You stopped it", tone: "idle" };
      break;
  }

  const time =
    run.phase === "running" && run.startedAt
      ? `${formatDuration(now - run.startedAt)} so far${usual >= 60 ? ` · usually about ${formatDuration(usual * 1000)}` : ""}`
      : usual >= 60
        ? `Usually about ${formatDuration(usual * 1000)} on this PC, plus your time on the draft`
        : "";

  // The bar counts finished steps; the step in progress shows as half of its share.
  const share = run.phase === "finished" ? 1 : (finished + (at && run.phase !== "failed" && run.phase !== "stopped" ? 0.5 : 0)) / 5;

  return (
    <header className="run-head">
      <div className="run-head-line">
        <h2>{title}</h2>
        {state && (
          <span className={`run-state ${state.tone}`}>
            {(state.tone === "run" || state.tone === "wait") && <span className="dot pulse" />}
            {state.text}
          </span>
        )}
        {time && <span className="run-time">{time}</span>}
      </div>
      <div
        className="run-bar"
        role="progressbar"
        aria-label="Run progress"
        aria-valuemin={0}
        aria-valuemax={5}
        aria-valuenow={finished}
        aria-valuetext={`${finished} of 5 steps finished`}
      >
        <span style={{ width: `${share * 100}%` }} />
      </div>
    </header>
  );
}
