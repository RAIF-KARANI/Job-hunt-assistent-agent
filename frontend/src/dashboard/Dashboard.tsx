// Dashboard (12f): key numbers, the job galaxy, and where the time goes.
// Jobs come from the tracker (all time); run numbers come from the run log
// for the chosen range, via the same code as the old Qt Dashboard (D19).

import { useCallback, useEffect, useState } from "react";
import { errorMessage, getApi, onEvent } from "../bridge/bridge";
import type { DashboardData, JobRow, Ui3D } from "../bridge/types";
import { JobSheet } from "../tracker/JobSheet";
import { useJobs } from "../tracker/useJobs";
import { SafetyNets, seconds, StatusFunnel, StepTimes } from "./Charts";
import { Galaxy } from "./galaxy/Galaxy";
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

const count = (jobs: JobRow[], ...statuses: string[]) => jobs.filter((j) => statuses.includes(j.status)).length;
const compact = (n: number) => (n >= 10_000 ? `${Math.round(n / 1000)}k` : n.toLocaleString());

/** Strongest fit still in play (not rejected), else the strongest overall. */
function bestJob(jobs: JobRow[]): JobRow | undefined {
  const open = jobs.filter((j) => j.status !== "rejected");
  return [...(open.length ? open : jobs)].sort((a, b) => b.fit_score - a.fit_score)[0];
}

export function Dashboard({ level }: { level: Ui3D }) {
  const { jobs, error: jobsError, load: reloadJobs, move, followUp } = useJobs();
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
      <header className="tracker-head">
        <div className="page-head">
          <h1>Dashboard</h1>
          <p>Every job you analyzed, and how well JobLens did.</p>
        </div>
        <div className="tracker-tools">
          <div className="segmented" role="group" aria-label="Run numbers from">
            {RANGES.map((r) => (
              <label key={r.label} className="segment">
                <input type="radio" name="dashboard-range" checked={days === r.days} onChange={() => setDays(r.days)} />
                <span>{r.label}</span>
              </label>
            ))}
          </div>
          <a className="btn btn-primary" href="#/analyze">
            New analysis
          </a>
        </div>
      </header>

      {(error || jobsError) && (
        <p className="notice notice-danger" role="alert">
          {error ? `Couldn't read the run log: ${error}` : jobsError}
        </p>
      )}

      <section className="tiles" aria-label="Key numbers">
        <div className="tile">
          <span className="tile-label">Jobs tracked</span>
          <span className="tile-value">{jobs ? jobs.length : "–"}</span>
          <span className="tile-note">
            {jobs ? `${count(jobs, "applied", "interviewing", "offer")} applied · ${count(jobs, "interviewing")} interviewing` : " "}
          </span>
        </div>
        <div className="tile">
          <span className="tile-label">Median full run</span>
          <span className="tile-value">{k?.median_full_run != null ? seconds(k.median_full_run) : "–"}</span>
          <span className="tile-note">
            {k ? `${k.runs} runs · ${k.llm_calls} LLM calls · ${compact(k.tokens_in + k.tokens_out)} tokens` : " "}
          </span>
        </div>
        <div className="tile">
          <span className="tile-label">Evidence verified</span>
          <span className="tile-value">{data?.pass_rate != null ? `${Math.round(data.pass_rate * 100)}%` : "–"}</span>
          <span className="tile-note">
            {judged ? `the judge rejected ${Math.round(judged.total)} claims` : "share of fit claims that held up"}
          </span>
        </div>
        <div className="tile">
          <span className="tile-label">Cover notes approved</span>
          <span className="tile-value">{k ? k.approved : "–"}</span>
          <span className="tile-note">
            {k?.approval_rate != null ? `${Math.round(k.approval_rate * 100)}% of decided · ${data?.decisions.reject ?? 0} rejected` : "none decided yet"}
          </span>
        </div>
      </section>
      <p className="hint range-note">
        Jobs: everything in your tracker. Run numbers: {rangeText}, from the run log on this PC. Nothing is sent anywhere.
      </p>

      <div className="galaxy-row">
        {jobs ? (
          <Galaxy jobs={jobs} level={level} selectedId={selected?.id ?? null} onSelect={setPickedId} />
        ) : (
          <section className="card galaxy-card" aria-busy="true">
            <p className="galaxy-loading hint">Loading your jobs…</p>
          </section>
        )}
        {selected && <SelectedJob job={selected} onOpen={setSheetId} />}
      </div>

      <div className="chart-row">
        <StepTimes data={data} />
        <SafetyNets data={data} />
        <StatusFunnel jobs={jobs} />
      </div>

      {sheetId !== null && (
        <JobSheet
          jobId={sheetId}
          status={jobs?.find((j) => j.id === sheetId)?.status}
          row={jobs?.find((j) => j.id === sheetId)}
          onMove={(id, to) => void move(id, to)}
          onFollowUp={followUp}
          onChanged={reloadJobs}
          onClose={() => setSheetId(null)}
        />
      )}
    </div>
  );
}
