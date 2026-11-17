// 17g: "A run, step by step" (features F28 to F30). The agent's steps in
// the order it works. Each row: how long the step takes, and its main
// result. The steps that are checked open to show their checks and charts.
//
// Which check belongs to which step comes from what each check looks at
// (job_agent/monitoring.py, EVAL_CHECKS): claims and quotes are checked in
// the fit analysis, sources and dates against the search results, numbers
// and rewrites in the cover note.

import { useState, type ReactNode } from "react";
import { Icon } from "../app/Icon";
import type { EvalsData } from "../bridge/types";
import { seconds, STEP_LABELS } from "../dashboard/Charts";
import { kilo, money, pct, plural, share } from "./format";
import { PassRateChart } from "./PassRateChart";
import { Ratings } from "./Ratings";
import { ModelTrend } from "./RunCharts";

const STEP_CHECKS: Record<string, string[]> = {
  analyze_fit: ["claims_checked", "fake_quotes_caught", "judge_rejections"],
  research_company: ["invented_urls_removed", "invented_dates_removed"],
  draft: ["number_warnings", "draft_rewrites"],
};

const STEP_ABOUT: Record<string, string> = {
  check_tracker: "Is this job already in your tracker?",
  read_posting: "The title, the company and what they ask for",
  analyze_fit: "Every skill claim must be proven by a quote from your resume",
  research_company: "Web and news search; sources are checked against the results",
  save_to_tracker: "With the job description, so it is still here later",
  draft: "Per draft. Then you approve, rewrite or reject it",
};

function Checks({ data, node }: { data: EvalsData; node: string }) {
  const rows = (STEP_CHECKS[node] ?? []).map((key) => data.checks.find((c) => c.check === key)).filter((c) => c !== undefined);
  if (!rows.length) return null;
  return (
    <ul className="nets step-checks">
      {rows.map((c) => (
        <li key={c.check} className="net">
          <span className="net-label">
            {c.label}
            <span className="cell-sub">{c.meaning}</span>
          </span>
          <span className="net-rate">{c.per_run !== null ? `${c.per_run.toFixed(1)} per run` : "not run yet"}</span>
          <span className={c.runs && c.total ? "net-value" : "net-value none"}>{c.runs ? Math.round(c.total) : "–"}</span>
        </li>
      ))}
    </ul>
  );
}

interface RowProps {
  n: number;
  node: string;
  time: number;
  /** 0..1 of the slowest step */
  part: number;
  top: boolean;
  metric: ReactNode;
  title: string;
  defaultOpen?: boolean;
  children?: ReactNode;
}

function StepRow({ n, node, time, part, top, metric, title, defaultOpen = false, children }: RowProps) {
  const [open, setOpen] = useState(defaultOpen);
  const row = (
    <>
      <span className="stepno">{n}</span>
      <span className="e-name">
        <span className="e-title">{STEP_LABELS[node] ?? node}</span>
        <span className="e-about">{STEP_ABOUT[node] ?? ""}</span>
      </span>
      <span className={top ? "e-bar top" : "e-bar"} aria-hidden="true">
        <span style={{ width: part > 0 ? `max(${(part * 100).toFixed(1)}%, 4px)` : 0 }} />
      </span>
      <span className="e-time">{seconds(time)}</span>
      <span className="e-metric">{metric}</span>
    </>
  );
  if (!children) {
    return (
      <li className="estep" title={title}>
        <div className="erow">
          {row}
          <span />
        </div>
      </li>
    );
  }
  return (
    <li className="estep">
      <details open={open} onToggle={(e) => setOpen(e.currentTarget.open)}>
        <summary className="erow" title={title}>
          {row}
          <Icon name="chevron" size={16} />
        </summary>
        <div className="estep-body">{children}</div>
      </details>
    </li>
  );
}

function Stat({ label, value, note, good }: { label: string; value: string; note?: string; good?: boolean }) {
  return (
    <div className="estat">
      <span className="estat-label">{label}</span>
      <span className="estat-value">{value}</span>
      {note && <span className={good ? "estat-note good" : "estat-note"}>{note}</span>}
    </div>
  );
}

export function RunSteps({ data, note }: { data: EvalsData; note: string | null }) {
  const k = data.kpis;
  const slowest = Math.max(0, ...data.steps.map((s) => s.avg_seconds));
  const delta = k.pass_rate_delta ?? null;
  const hasCloud = data.models.some((m) => m.provider !== "ollama");
  const approved = share(k.approved, k.decided);
  const failed = share(k.tool_failures, k.tool_calls);

  const deltaNote =
    delta !== null && k.pass_rate_window
      ? `${Math.abs(delta) < 0.005 ? "Same as" : `${delta > 0 ? "Up" : "Down"} ${Math.round(Math.abs(delta) * 100)} points on`} the ${k.pass_rate_window} runs before`
      : "Skill claims that held up";

  const metric = (node: string, outTokens: number): ReactNode => {
    switch (node) {
      case "analyze_fit":
        return (
          <>
            <strong>{pct(k.pass_rate ?? null)}</strong> evidence passes
          </>
        );
      case "research_company":
        return (
          <>
            <strong>{pct(failed)}</strong> of searches failed
          </>
        );
      case "draft":
        return (
          <>
            <strong>{pct(approved)}</strong> approved by you
          </>
        );
      default:
        return outTokens >= 1 ? `${kilo(outTokens)} tokens written` : "";
    }
  };

  const details = (node: string): ReactNode => {
    switch (node) {
      case "analyze_fit":
        return (
          <>
            <div className="estats">
              <Stat label="Evidence pass rate" value={pct(k.pass_rate ?? null)} note={deltaNote} good={delta !== null && delta >= 0.005} />
            </div>
            <Checks data={data} node={node} />
            <div className="estep-charts">
              <div>
                <h4>Pass rate, run by run</h4>
                <p className="hint">Share of skill claims that survived the quote check and the judge. Hover a point for its run.</p>
                {data.trend.length ? <PassRateChart trend={data.trend} /> : <p className="chart-empty">No analyzed runs yet.</p>}
              </div>
              <div>
                <h4>By model</h4>
                <p className="hint">
                  {data.model_trend.length === 1
                    ? `Only ${data.model_trend[0].model} has analyzed runs so far. Another model gets its own line.`
                    : "One line per model, oldest run on the left. Always every model, whatever is chosen above."}
                  {data.models_not_charted > 0 && ` ${plural(data.models_not_charted, "more model")} with fewer runs: see Models compared.`}
                </p>
                {data.model_trend.length ? <ModelTrend series={data.model_trend} /> : <p className="chart-empty">No analyzed runs yet.</p>}
              </div>
            </div>
            <Ratings ratings={data.ratings} aspect="fit_score" />
          </>
        );
      case "research_company":
        return (
          <>
            <div className="estats">
              <Stat
                label="Searches that failed"
                value={pct(failed)}
                note={`${k.tool_failures} of ${k.tool_calls} ${k.tool_calls === 1 ? "search" : "searches"}` + (k.tool_empty ? ` · ${k.tool_empty} found nothing` : "")}
              />
            </div>
            <Checks data={data} node={node} />
          </>
        );
      case "draft":
        return (
          <>
            <div className="estats">
              <Stat label="Cover notes approved" value={pct(approved)} note={`${k.approved} of ${plural(k.decided, "decision")}`} />
            </div>
            <Checks data={data} node={node} />
            <Ratings ratings={data.ratings} aspect="cover_note" />
          </>
        );
      default:
        return null;
    }
  };

  return (
    <section className="card evals-run" aria-labelledby="run-title">
      <header className="evals-run-head">
        <h2 id="run-title">A run, step by step</h2>
        <dl className="run-totals">
          <div title={`Median of ${plural(k.full_runs, "full run")}; waiting for you isn't counted`}>
            <dt>Whole run</dt>
            <dd>{k.median_seconds != null ? seconds(k.median_seconds) : "–"}</dd>
          </div>
          <div title={k.tokens_in_per_run != null ? `${kilo(k.tokens_in_per_run)} in · ${kilo(k.tokens_out_per_run)} out` : undefined}>
            <dt>Tokens</dt>
            <dd>{k.tokens_in_per_run != null ? kilo(k.tokens_in_per_run + (k.tokens_out_per_run ?? 0)) : "–"}</dd>
          </div>
          {hasCloud && (
            <div title={k.cost_total != null ? `${plural(k.cost_runs, "run")} with a priced model` : "Enter the model's price in Settings to see it"}>
              <dt>Cost</dt>
              <dd>{k.cost_total != null ? `${money(k.cost_per_run ?? null)} a run` : <a href="#/settings">add a price</a>}</dd>
            </div>
          )}
          <div title={k.unfinished ? `${seconds(k.unfinished_seconds)} of agent time; closed, stopped or failed` : "Every run finished"}>
            <dt>Unfinished runs</dt>
            <dd>{k.unfinished}</dd>
          </div>
        </dl>
      </header>

      <ol className="esteps">
        {data.steps.map((s, i) => (
          <StepRow
            key={s.node}
            n={i + 1}
            node={s.node}
            time={s.avg_seconds}
            part={slowest ? s.avg_seconds / slowest : 0}
            top={s.avg_seconds === slowest && slowest > 0}
            metric={metric(s.node, s.out_tokens)}
            title={`Average ${seconds(s.avg_seconds)} over ${plural(s.count, s.node === "draft" ? "draft" : "run")}; ${kilo(s.out_tokens)} tokens written`}
            defaultOpen={s.node === "analyze_fit"}
          >
            {details(s.node)}
          </StepRow>
        ))}
      </ol>

      <p className="hint evals-run-foot">
        Step times are averages; each bar compares a step with the slowest one. Time spent waiting for you isn't counted.
        {note && ` ${note}`}
      </p>
    </section>
  );
}
