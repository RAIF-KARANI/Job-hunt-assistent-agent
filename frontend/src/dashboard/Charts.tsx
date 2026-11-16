// The Dashboard's 2D cards. Exact numbers live here, not in the galaxy (D8).
// Every bar has its value written next to it and a hover title with the
// details, so nothing depends on reading a bar's length or color.

import type { DashboardData } from "../bridge/types";

export const STEP_LABELS: Record<string, string> = {
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

function Bar({ label, value, share, title, top }: { label: string; value: string; share: number; title: string; top?: boolean }) {
  return (
    <li className={top ? "bar-row top" : "bar-row"} title={title}>
      <span className="bar-label">{label}</span>
      <span className="bar-track" aria-hidden="true">
        {/* A tiny value still shows a sliver, so "0" and "almost 0" look different. */}
        <span className="bar-fill" style={{ width: share > 0 ? `max(${(share * 100).toFixed(1)}%, 4px)` : 0 }} />
      </span>
      <span className="bar-value">{value}</span>
    </li>
  );
}

export function StepTimes({ data }: { data: DashboardData | null }) {
  const steps = data?.steps ?? [];
  const slowest = Math.max(0, ...steps.map((s) => s.avg_seconds));
  // 17d: say where the time goes, don't leave it to the bars. The shares are
  // of the step averages added up, so "about".
  const all = steps.reduce((sum, s) => sum + s.avg_seconds, 0);
  const top = steps.find((s) => s.avg_seconds === slowest);
  const share = top && all ? Math.round((top.avg_seconds / all) * 100) : 0;
  return (
    <section className="card chart-card" aria-labelledby="steps-title">
      <h3 id="steps-title">Time per step</h3>
      <p className="hint">
        {top && share >= 40 ? `${STEP_LABELS[top.node] ?? top.node} takes about ${share}% of a run. ` : ""}
        Average agent time; waiting for you isn't counted.
      </p>
      {steps.length ? (
        <ul className="bars">
          {steps.map((s) => (
            <Bar
              key={s.node}
              label={STEP_LABELS[s.node] ?? s.node}
              value={seconds(s.avg_seconds)}
              share={slowest ? s.avg_seconds / slowest : 0}
              top={s === top}
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
      <h3 id="nets-title">Safety nets caught</h3>
      <p className="hint">Model mistakes JobLens stopped before you saw them.</p>
      {quality.length ? (
        <ul className="nets">
          {quality.map((q) => (
            <li key={q.check} className="net" title={`${q.per_run.toFixed(1)} per run, over ${plural(q.runs, "run")}`}>
              <span className="net-label">{q.check}</span>
              <span className="net-rate">{q.per_run.toFixed(1)} per run</span>
              <span className={q.total ? "net-value" : "net-value none"}>{Math.round(q.total)}</span>
            </li>
          ))}
        </ul>
      ) : (
        <Empty data={data} />
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
