// The Dashboard's 2D cards. Exact numbers live here, not in the galaxy (D8).
// Every bar has its value written next to it and a hover title with the
// details, so nothing depends on reading a bar's length or color.

import type { DashboardData, JobRow } from "../bridge/types";
import { STATUSES } from "../tracker/status";

const STEP_LABELS: Record<string, string> = {
  check_tracker: "Check tracker",
  read_posting: "Read posting",
  analyze_fit: "Compare resumes",
  research_company: "Research company",
  save_to_tracker: "Save",
  draft: "Draft cover note", // per draft: a rewrite counts again
};

export function seconds(s: number): string {
  if (s < 1) return "<1 s";
  if (s < 90) return `${Math.round(s)} s`;
  const m = Math.floor(s / 60);
  return `${m}m ${String(Math.round(s % 60)).padStart(2, "0")}s`;
}

const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? "" : "s"}`;

function Bar({ label, value, share, title, color }: { label: string; value: string; share: number; title: string; color?: string }) {
  return (
    <li className="bar-row" title={title}>
      <span className="bar-label">{label}</span>
      <span className="bar-track" aria-hidden="true">
        {/* A tiny value still shows a sliver, so "0" and "almost 0" look different. */}
        <span className="bar-fill" style={{ width: share > 0 ? `max(${(share * 100).toFixed(1)}%, 4px)` : 0, background: color }} />
      </span>
      <span className="bar-value">{value}</span>
    </li>
  );
}

export function StepTimes({ data }: { data: DashboardData | null }) {
  const steps = data?.steps ?? [];
  const slowest = Math.max(0, ...steps.map((s) => s.avg_seconds));
  return (
    <section className="card chart-card" aria-labelledby="steps-title">
      <h2 id="steps-title">Time per step</h2>
      <p className="hint">Average agent time; waiting for you isn't counted.</p>
      {steps.length ? (
        <ul className="bars">
          {steps.map((s) => (
            <Bar
              key={s.node}
              label={STEP_LABELS[s.node] ?? s.node}
              value={seconds(s.avg_seconds)}
              share={slowest ? s.avg_seconds / slowest : 0}
              title={`Average ${seconds(s.avg_seconds)}, slowest ${seconds(s.max_seconds)}, ${plural(s.count, s.node === "draft" ? "draft" : "run")}`}
            />
          ))}
        </ul>
      ) : (
        <Empty data={data} />
      )}
    </section>
  );
}

export function SafetyNets({ data }: { data: DashboardData | null }) {
  const quality = data?.quality ?? [];
  return (
    <section className="card chart-card" aria-labelledby="nets-title">
      <div className="section-head">
        <h2 id="nets-title">Safety nets caught</h2>
        <a href="#/evals" className="link-sm">
          All agent evals
        </a>
      </div>
      <p className="hint">Mistakes the agent's checks stopped before you saw them.</p>
      {quality.length ? (
        <ul className="nets">
          {quality.map((q) => (
            <li key={q.check} className="net" title={`${q.per_run.toFixed(1)} per run, over ${plural(q.runs, "run")}`}>
              <span className="net-value">{Math.round(q.total)}</span>
              <span className="net-label">{q.check}</span>
              <span className="net-rate">{q.per_run.toFixed(1)} per run</span>
            </li>
          ))}
        </ul>
      ) : (
        <Empty data={data} />
      )}
    </section>
  );
}

export function StatusFunnel({ jobs }: { jobs: JobRow[] | null }) {
  const counts = STATUSES.map((s) => ({ ...s, count: jobs?.filter((j) => j.status === s.id).length ?? 0 }));
  const most = Math.max(0, ...counts.map((c) => c.count));
  return (
    <section className="card chart-card" aria-labelledby="funnel-title">
      <h2 id="funnel-title">Where your applications are</h2>
      <p className="hint">Every tracked job, by status.</p>
      {jobs?.length ? (
        <ul className="bars">
          {counts.map((c) => (
            <Bar
              key={c.id}
              label={c.label}
              value={String(c.count)}
              share={most ? c.count / most : 0}
              title={`${plural(c.count, "job")}: ${c.label.toLowerCase()}`}
              color={c.color}
            />
          ))}
        </ul>
      ) : (
        <p className="chart-empty">{jobs ? "No tracked jobs yet." : "Loading…"}</p>
      )}
    </section>
  );
}

function Empty({ data }: { data: DashboardData | null }) {
  if (!data) return <p className="chart-empty">Loading…</p>;
  return (
    <p className="chart-empty">
      {data.kpis.runs
        ? "Nothing recorded in this time range."
        : data.days !== null
          ? "No runs in this time range."
          : "Analyze a job to see this."}
    </p>
  );
}
