// Dashboard. Two groups (17d): your job search first (the pipeline, what to
// do next, the job galaxy), then how well JobLens did the work.
// Jobs come from the tracker (all time); run numbers come from the run log
// for the chosen range, via the same code as the old Qt Dashboard (D19).

import { useCallback, useEffect, useState } from "react";
import { Icon, type IconName } from "../app/Icon";
import { errorMessage, getApi, onEvent } from "../bridge/bridge";
import type { DashboardData, JobRow, Ui3D } from "../bridge/types";
import { JobSheet } from "../tracker/JobSheet";
import { useJobs } from "../tracker/useJobs";
import { SafetyNets, seconds, StepTimes } from "./Charts";
import { DoNext } from "./DoNext";
import { Galaxy } from "./galaxy/Galaxy";
import { Pipeline } from "./Pipeline";
import { SelectedJob } from "./SelectedJob";

type Range = 7 | 30 | null;
const RANGES: { days: Range; label: string }[] = [
  { days: 7, label: "7 days" },
  { days: 30, label: "30 days" },
  { days: null, label: "All" },
];
const RANGE_KEY = "joblens.dashboard.days";

function savedRange(): Range {
  try {
    const v = localStorage.getItem(RANGE_KEY);
    return v === "7" ? 7 : v === "all" ? null : 30;
  } catch {
    return 30;
  }
}

const compact = (n: number) => (n >= 10_000 ? `${Math.round(n / 1000)}k` : n.toLocaleString());

/** Strongest fit still in play (not rejected), else the strongest overall. */
function bestJob(jobs: JobRow[]): JobRow | undefined {
  const open = jobs.filter((j) => j.status !== "rejected");
  return [...(open.length ? open : jobs)].sort((a, b) => b.fit_score - a.fit_score)[0];
}

function Kpi({ tone, icon, label, value, note }: { tone: string; icon: IconName; label: string; value: string; note: string }) {
  return (
    <div className={`kpi kpi-${tone}`}>
      <span className="kpi-label">
        <span className="kpi-icon">
          <Icon name={icon} size={15} />
        </span>
        {label}
      </span>
      <span className="kpi-value">{value}</span>
      <span className="kpi-note">{note}</span>
    </div>
  );
}

export function Dashboard({ level }: { level: Ui3D }) {
  const { jobs, error: jobsError, load: reloadJobs, move, followUp, applyAnswer } = useJobs();
  const [days, setDays] = useState<Range>(savedRange);
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pickedId, setPickedId] = useState<number | null>(null);
  const [sheetId, setSheetId] = useState<number | null>(null);

  const load = useCallback(() => {
    getApi()
      .then((api) => api.dashboard(days))
      .then((d) => {
        setData(d);
        setError(null);
      })
      .catch((e) => setError(errorMessage(e)));
  }, [days]);

  useEffect(() => {
    load();
    try {
      localStorage.setItem(RANGE_KEY, days === null ? "all" : String(days));
    } catch {
      /* not remembered, still works */
    }
    return onEvent((e) => {
      if (e.type === "finished") load(); // a run just landed in the run log
    });
  }, [days, load]);

  const selected = jobs?.find((j) => j.id === pickedId) ?? (jobs ? bestJob(jobs) : undefined);
  const k = data?.kpis;
  const judged = data?.quality.find((q) => q.check === "Claims rejected by the judge");
  const rangeText = days === null ? "all time" : `the last ${days} days`;

  return (
    <div className="page dashboard">
      <header className="page-head">
        <h1>Dashboard</h1>
        <p>Your job search first, then how well JobLens did the work.</p>
      </header>

      {(error || jobsError) && (
        <p className="notice notice-danger" role="alert">
          {error ? `Couldn't read the run log: ${error}` : jobsError}
        </p>
      )}

      <section className="dash-section" aria-labelledby="search-title">
        <div className="dash-head">
          <h2 id="search-title">Your job search</h2>
        </div>

        <Pipeline jobs={jobs} />

        <div className="search-row">
          {jobs && <DoNext jobs={jobs} onOpen={setSheetId} />}
          {/* The galaxy and the job picked in it are one panel: picking a dot fills the side next to it. */}
          <div className="card joined galaxy-panel">
            {jobs ? (
              <Galaxy jobs={jobs} level={level} selectedId={selected?.id ?? null} onSelect={setPickedId} />
            ) : (
              <section className="card galaxy-card" aria-busy="true">
                <p className="galaxy-loading hint">Loading your jobs…</p>
              </section>
            )}
            {selected && <SelectedJob job={selected} onOpen={setSheetId} />}
          </div>
        </div>
      </section>

      <section className="dash-section" aria-labelledby="agent-title">
        <div className="dash-head">
          <h2 id="agent-title">How JobLens is doing</h2>
          {/* The range only changes the numbers in this group, so it sits with them. */}
          <div className="segmented" role="group" aria-label="Run numbers from">
            {RANGES.map((r) => (
              <label key={r.label} className="segment">
                <input type="radio" name="dashboard-range" checked={days === r.days} onChange={() => setDays(r.days)} />
                <span>{r.label}</span>
              </label>
            ))}
          </div>
          <a href="#/evals" className="link-sm">
            All agent evals
          </a>
        </div>

        <div className="kpis" aria-label="Key numbers">
          <Kpi
            tone="purple"
            icon="clock"
            label="Median full run"
            value={k?.median_full_run != null ? seconds(k.median_full_run) : "–"}
            note={k ? `${k.runs} runs · ${k.llm_calls} AI calls · ${compact(k.tokens_in + k.tokens_out)} tokens` : " "}
          />
          <Kpi
            tone="pink"
            icon="shield"
            label="Evidence verified"
            value={data?.pass_rate != null ? `${Math.round(data.pass_rate * 100)}%` : "–"}
            note={judged ? `The judge rejected ${Math.round(judged.total)} claims` : "Share of fit claims that held up"}
          />
          <Kpi
            tone="orange"
            icon="note"
            label="Cover notes approved"
            value={k ? String(k.approved) : "–"}
            note={k?.approval_rate != null ? `${Math.round(k.approval_rate * 100)}% of your decisions · ${data?.decisions.reject ?? 0} rejected` : "None decided yet"}
          />
        </div>

        <div className="card joined agent-panel">
          <StepTimes data={data} />
          <SafetyNets data={data} />
        </div>
        <p className="hint range-note">Run numbers are for {rangeText}, from the run log on this PC. Nothing is sent anywhere.</p>
      </section>

      {sheetId !== null && (
        <JobSheet
          jobId={sheetId}
          status={jobs?.find((j) => j.id === sheetId)?.status}
          row={jobs?.find((j) => j.id === sheetId)}
          onMove={(id, to) => void move(id, to)}
          onFollowUp={followUp}
          onApply={applyAnswer}
          onChanged={reloadJobs}
          onDeleted={() => {
            setSheetId(null);
            reloadJobs();
          }}
          onClose={() => setSheetId(null)}
        />
      )}
    </div>
  );
}
