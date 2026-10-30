// Evals (12f2, D9): how well the agent did, measured on this PC from the
// run log. Langfuse / LangSmith are optional: their state is shown, and runs
// recorded while one was on link to their trace (D20).

import { useCallback, useEffect, useState } from "react";
import { errorMessage, getApi, onEvent } from "../bridge/bridge";
import type { EvalsData, TracingStatus } from "../bridge/types";
import { seconds, STEP_LABELS } from "../dashboard/Charts";
import { parseUtc } from "../tracker/status";
import { PassRateChart } from "./PassRateChart";
import { Ratings } from "./Ratings";

const pct = (v: number | null) => (v === null ? "–" : `${Math.round(v * 100)}%`);
const kilo = (n: number | null) => (n === null ? "–" : n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(Math.round(n)));
const share = (part: number, whole: number) => (whole ? part / whole : null);
const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? "" : "s"}`;
const where = (provider: string) => (provider === "anthropic" ? "API · your key" : "local · this PC");

const RESULT_TONE: Record<string, string> = {
  approved: "ok",
  rejected: "danger",
  "not finished": "warn",
  error: "danger",
  done: "neutral",
};

function TracingChips({ status }: { status: TracingStatus | null }) {
  const langfuse = status?.langfuse ?? "…";
  const langsmith = status?.langsmith ?? "…";
  const tone = (s: string) => (s === "running" || s === "on" ? "ok" : s === "not reachable" || s === "no key" ? "warn" : "off");
  return (
    <ul className="tracing" aria-label="Where run data is recorded">
      <li className="trace-chip ok">
        <span className="trace-dot" aria-hidden="true" />
        Run log · always on
      </li>
      <li className={`trace-chip ${tone(langfuse)}`} title={langfuse === "not reachable" ? "Start it with: cd infra\\langfuse && docker compose up -d" : undefined}>
        <span className="trace-dot" aria-hidden="true" />
        Langfuse · {langfuse}
      </li>
      <li className={`trace-chip ${tone(langsmith)}`}>
        <span className="trace-dot" aria-hidden="true" />
        LangSmith · {langsmith}
      </li>
    </ul>
  );
}

function TraceLink({ run, status }: { run: EvalsData["recent"][number]; status: TracingStatus | null }) {
  if (run.tracing === "langfuse" && status?.langfuse_sessions) {
    return <a href={status.langfuse_sessions + encodeURIComponent(run.run_id)}>Langfuse</a>;
  }
  if (run.tracing === "langsmith" && status) {
    return (
      <a href={status.langsmith_url} title={`Find the thread with session id ${run.run_id}`}>
        LangSmith
      </a>
    );
  }
  if (run.tracing === "langfuse") return <span className="muted" title="Langfuse isn't running">Langfuse (off)</span>;
  return <span className="muted">off</span>;
}

function correlationNote(c: EvalsData["correlation"]): string | null {
  if (c.output === null || c.input === null) return null;
  const r = (v: number) => v.toFixed(2);
  if (c.output >= 0.6 && c.output - c.input >= 0.3) {
    return `Call time follows output tokens (r = ${r(c.output)}), not input tokens (${r(c.input)}). Shorter answers make runs faster.`;
  }
  return `Call time vs output tokens: r = ${r(c.output)}; vs input tokens: ${r(c.input)} (${c.calls} LLM calls).`;
}

export function Evals() {
  const [model, setModel] = useState<string>(""); // "" = all models
  const [data, setData] = useState<EvalsData | null>(null);
  const [tracing, setTracing] = useState<TracingStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    getApi()
      .then((api) => api.evals(model || null))
      .then((d) => {
        setData(d);
        setError(null);
      })
      .catch((e) => setError(errorMessage(e)));
  }, [model]);

  useEffect(() => {
    load();
    return onEvent((e) => {
      if (e.type === "finished") load();
    });
  }, [load]);

  useEffect(() => {
    getApi()
      .then((api) => api.tracing_status())
      .then(setTracing)
      .catch(() => setTracing(null));
  }, []);

  const k = data?.kpis;
  const slowest = Math.max(0, ...(data?.steps ?? []).map((s) => s.avg_seconds));
  const note = data ? correlationNote(data.correlation) : null;
  const delta = k?.pass_rate_delta ?? null;

  return (
    <div className="page evals">
      <header className="tracker-head">
        <div className="page-head">
          <h1>Agent evals</h1>
          <p>How well the agent did, measured on this PC. Nothing is sent anywhere.</p>
        </div>
        <div className="tracker-tools">
          <label className="field">
            <span>Model</span>
            <select className="input" value={model} onChange={(e) => setModel(e.target.value)}>
              <option value="">All models</option>
              {data?.models.map((m) => (
                <option key={m.model} value={m.model}>
                  {m.model} ({m.provider === "anthropic" ? "API" : "local"})
                </option>
              ))}
            </select>
          </label>
        </div>
      </header>
      <TracingChips status={tracing} />

      {error && (
        <p className="notice notice-danger" role="alert">
          Couldn't read the run log: {error}
        </p>
      )}

      {data && data.kpis.runs === 0 ? (
        <section className="card evals-empty">
          <h2>No runs yet</h2>
          <p>Analyze a job and its numbers appear here: how many skill claims held up, what you approved, and where the time went.</p>
          <a className="btn btn-primary" href="#/analyze">
            Analyze a job
          </a>
        </section>
      ) : (
        <>
          <section className="tiles" aria-label="Key numbers">
            <div className="tile">
              <span className="tile-label">Evidence pass rate</span>
              <span className="tile-value">{pct(k?.pass_rate ?? null)}</span>
              <span className={delta !== null && delta >= 0.005 ? "tile-note good" : "tile-note"}>
                {delta !== null && k?.pass_rate_window
                  ? `${Math.abs(delta) < 0.005 ? "same as" : `${delta > 0 ? "up" : "down"} ${Math.round(Math.abs(delta) * 100)} points vs`} the ${k.pass_rate_window} runs before`
                  : "skill claims that held up"}
              </span>
            </div>
            <div className="tile">
              <span className="tile-label">Cover notes approved</span>
              <span className="tile-value">{k ? pct(share(k.approved, k.decided)) : "–"}</span>
              <span className="tile-note">{k ? `${k.approved} of ${plural(k.decided, "decision")}` : " "}</span>
            </div>
            <div className="tile">
              <span className="tile-label">Agent time per run</span>
              <span className="tile-value">{k?.median_seconds != null ? seconds(k.median_seconds) : "–"}</span>
              <span className="tile-note">{k ? `median of ${plural(k.full_runs, "full run")}; waiting for you excluded` : " "}</span>
            </div>
            <div className="tile">
              <span className="tile-label">Tokens per run</span>
              <span className="tile-value">
                {k?.tokens_in_per_run != null ? kilo(k.tokens_in_per_run + (k.tokens_out_per_run ?? 0)) : "–"}
              </span>
              <span className="tile-note">
                {k?.tokens_in_per_run != null ? `${kilo(k.tokens_in_per_run)} in · ${kilo(k.tokens_out_per_run)} out` : " "}
              </span>
            </div>
            <div className="tile">
              <span className="tile-label">Tool failures</span>
              <span className="tile-value">{k ? pct(share(k.tool_failures, k.tool_calls)) : "–"}</span>
              <span className="tile-note">{k ? `${k.tool_failures} of ${k.tool_calls} ${k.tool_calls === 1 ? "search" : "searches"} failed` : " "}</span>
            </div>
          </section>

          <div className="chart-row">
            <section className="card chart-card wide" aria-labelledby="trend-title">
              <h2 id="trend-title">Evidence pass rate per run</h2>
              <p className="hint">Share of skill claims that survived the quote check and the judge. Hover a point for its run.</p>
              {data?.trend.length ? <PassRateChart trend={data.trend} /> : <p className="chart-empty">No analyzed runs yet.</p>}
            </section>
            <section className="card chart-card" aria-labelledby="ratings-title">
              <h2 id="ratings-title">Your ratings</h2>
              {data && <Ratings ratings={data.ratings} />}
            </section>
          </div>

          <div className="chart-row">
            <section className="card chart-card" aria-labelledby="checks-title">
              <h2 id="checks-title">Safety nets</h2>
              <p className="hint">Automatic checks on every run. Per run = average over the runs that ran the check.</p>
              <div className="table-wrap flat">
                <table className="eval-table">
                  <thead>
                    <tr>
                      <th scope="col">Check</th>
                      <th scope="col" className="num">
                        Total
                      </th>
                      <th scope="col" className="num">
                        Per run
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {data?.checks.map((c) => (
                      <tr key={c.check}>
                        <th scope="row">
                          {c.label}
                          <span className="cell-sub">{c.meaning}</span>
                        </th>
                        <td className="num">{c.runs ? Math.round(c.total) : "–"}</td>
                        <td className="num">{c.per_run !== null ? c.per_run.toFixed(1) : "not run yet"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>

            <section className="card chart-card" aria-labelledby="time-title">
              <h2 id="time-title">Where the time goes</h2>
              <p className="hint">Average agent time and output tokens per step (the draft: per draft).</p>
              <div className="table-wrap flat">
                <table className="eval-table">
                  <thead>
                    <tr>
                      <th scope="col">Step</th>
                      <th scope="col">
                        <span className="sr-only">Share of the slowest step</span>
                      </th>
                      <th scope="col" className="num">
                        Time
                      </th>
                      <th scope="col" className="num">
                        Out tokens
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {data?.steps.map((s) => (
                      <tr key={s.node}>
                        <th scope="row">{STEP_LABELS[s.node] ?? s.node}</th>
                        <td className="cell-bar">
                          <span className="bar-track" aria-hidden="true">
                            <span className="bar-fill" style={{ width: slowest ? `max(${((s.avg_seconds / slowest) * 100).toFixed(1)}%, 4px)` : 0 }} />
                          </span>
                        </td>
                        <td className="num">{seconds(s.avg_seconds)}</td>
                        <td className="num">{kilo(s.out_tokens)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {note && <p className="notice insight">{note}</p>}
            </section>
          </div>

          <section className="card chart-card" aria-labelledby="models-title">
            <h2 id="models-title">Models compared</h2>
            <p className="hint">Always every model. Cost isn't shown: prices change and aren't in the run log, so compare tokens.</p>
            <div className="table-wrap flat">
              <table className="eval-table">
                <thead>
                  <tr>
                    <th scope="col">Model</th>
                    <th scope="col" className="num">
                      Runs
                    </th>
                    <th scope="col" className="num">
                      Evidence pass
                    </th>
                    <th scope="col" className="num">
                      Notes approved
                    </th>
                    <th scope="col" className="num">
                      Agent time
                    </th>
                    <th scope="col" className="num">
                      Tokens / run
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {data?.models.map((m) => (
                    <tr key={m.model} className={m.model === model ? "current" : undefined}>
                      <th scope="row">
                        <span className="mono">{m.model}</span>
                        <span className="cell-sub">{where(m.provider)}</span>
                      </th>
                      <td className="num">{m.runs}</td>
                      <td className="num">{pct(m.pass_rate)}</td>
                      <td className="num">{m.decided ? `${pct(share(m.approved, m.decided))} (${m.approved} of ${m.decided})` : "–"}</td>
                      <td className="num">{m.median_seconds !== null ? seconds(m.median_seconds) : "–"}</td>
                      <td className="num">{kilo(m.tokens_per_run)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="card chart-card" aria-labelledby="recent-title">
            <h2 id="recent-title">Recent runs</h2>
            <p className="hint">Trace links appear for runs recorded while Langfuse or LangSmith tracing was on.</p>
            <div className="table-wrap flat">
              <table className="eval-table">
                <thead>
                  <tr>
                    <th scope="col">When</th>
                    <th scope="col">Job</th>
                    <th scope="col">Model</th>
                    <th scope="col">Result</th>
                    <th scope="col" className="num">
                      Time
                    </th>
                    <th scope="col" className="num">
                      LLM calls
                    </th>
                    <th scope="col" className="num">
                      Tokens
                    </th>
                    <th scope="col" className="num">
                      Evidence
                    </th>
                    <th scope="col">Trace</th>
                  </tr>
                </thead>
                <tbody>
                  {data?.recent.map((r) => (
                    <tr key={r.run_id}>
                      <td className="nowrap">{parseUtc(r.started_at).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })}</td>
                      <td className="cell-job">
                        {r.job ? (
                          <>
                            {r.job.company}
                            <span className="cell-sub" title={r.job.title}>
                              {r.job.title}
                            </span>
                          </>
                        ) : (
                          <span className="muted">no job saved</span>
                        )}
                      </td>
                      <td className="mono nowrap">{r.model}</td>
                      <td>
                        <span className={`result result-${RESULT_TONE[r.result] ?? "neutral"}`}>{r.result}</span>
                      </td>
                      <td className="num">{seconds(r.agent_seconds)}</td>
                      <td className="num">{r.llm_calls}</td>
                      <td className="num">{kilo(r.tokens)}</td>
                      <td className="num">{pct(r.pass_rate)}</td>
                      <td>
                        <TraceLink run={r} status={tracing} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </div>
  );
}
