// Evals (12f2, D9): how well the agent did, measured on this PC from the
// run log. Langfuse / LangSmith are optional: their state is shown, and runs
// recorded while one was on link to their trace (D20).

import { useCallback, useEffect, useState } from "react";
import { errorMessage, getApi, onEvent } from "../bridge/bridge";
import type { EvalsData, TracingStatus } from "../bridge/types";
import { Fold } from "../app/Fold";
import { seconds } from "../dashboard/Charts";
import { parseUtc } from "../tracker/status";
import { kilo, money, pct, plural, share } from "./format";
import { correlation, niceMinutes, RunLine, RunScatter } from "./RunCharts";
import { RunSteps } from "./RunSteps";

/** 16d: axis labels: "50k" not "50.0k", "5 min" not "5m 00s". */
const axisKilo = (n: number) => (n >= 1000 ? `${Math.round(n / 100) / 10}k` : String(Math.round(n)));
const axisMinutes = (s: number) => (s === 0 ? "0" : `${Math.round(s / 6) / 10} min`);
const where = (provider: string) => (provider === "ollama" ? "local · this PC" : "API · your key"); // 16c: any cloud provider

const RESULT_TONE: Record<string, string> = {
  approved: "ok",
  rejected: "danger",
  "not finished": "warn",
  error: "danger",
  done: "neutral",
  stopped: "neutral", // you chose to stop: not an error
  interrupted: "warn", // the app was closed mid-run
  "out of quota": "warn", // 16c: the API key's limit ran out
  running: "neutral",
};

function TracingChips({ status }: { status: TracingStatus | null }) {
  const langfuse = status?.langfuse ?? "…";
  const langsmith = status?.langsmith ?? "…";
  const tone = (s: string) =>
    s === "running" || s === "on" ? "ok" : ["not reachable", "no key", "no keys", "keys rejected"].includes(s) ? "warn" : "off";
  const langfuseHint: Record<string, string> = {
    "not reachable": "Start it with: cd infra\\langfuse && docker compose up -d",
    "no keys": "Add its keys in Settings → Options → Tracing",
    "keys rejected": "Langfuse rejected the keys: copy them again into Settings → Options → Tracing",
  };
  return (
    <ul className="tracing" aria-label="Where run data is recorded">
      <li className="trace-chip ok">
        <span className="trace-dot" aria-hidden="true" />
        Run log · always on
      </li>
      <li className={`trace-chip ${tone(langfuse)}`} title={langfuseHint[langfuse]}>
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
  if (run.tracing === "langfuse") return <span className="muted" title="No connection to Langfuse right now (see the chip above)">Langfuse (off)</span>;
  // 15h: Langfuse wasn't answering when this run started, so it has no trace
  if (run.tracing === "langfuse_down") return <span className="muted" title="Start Langfuse (docker compose up -d) before a run to trace it">no trace (Langfuse wasn't running)</span>;
  return <span className="muted">off</span>;
}

/** 16a: Recent runs shows this many, and "Show more" adds as many again. */
const RECENT_STEP = 15;
/** A run that could have a trace link: tracing was on and reached its server. */
const hasTrace = (run: EvalsData["recent"][number]) => run.tracing === "langfuse" || run.tracing === "langsmith";

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

  const [recentCount, setRecentCount] = useState(RECENT_STEP); // 16a: 0 = all runs

  const load = useCallback(() => {
    getApi()
      .then((api) => api.evals(model || null, recentCount))
      .then((d) => {
        setData(d);
        setError(null);
      })
      .catch((e) => setError(errorMessage(e)));
  }, [model, recentCount]);

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

  const note = data ? correlationNote(data.correlation) : null;
  const showTrace = data?.recent.some(hasTrace) ?? false; // 16a: an all-empty column is noise
  const showCost = data?.recent.some((r) => r.cost !== null) ?? false;
  const points = data?.run_points ?? [];
  const r = correlation(points.map((p) => p.tokens_in + p.tokens_out), points.map((p) => p.seconds));

  return (
    <div className="page evals">
      <header className="tracker-head">
        <div className="page-head">
          <h1>Agent evals</h1>
          <p>How the agent did at each step of a run, in the order it works. Measured on this PC; nothing is sent anywhere.</p>
        </div>
        <div className="tracker-tools">
          <label className="field">
            <span>Showing</span>
            <select className="input" value={model} onChange={(e) => setModel(e.target.value)}>
              <option value="">All models</option>
              {data?.models.map((m) => (
                <option key={m.model} value={m.model}>
                  {m.model} ({m.provider === "ollama" ? "local" : "API"})
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
          {data && <RunSteps data={data} note={note} />}

          <Fold
            level={2}
            defaultOpen
            title="Models compared"
            digest={data ? data.models.map((m) => `${m.model} ${plural(m.runs, "run")}`).join(" · ") : ""}
          >
            <p className="hint">
              Always every model. Cost uses the price you enter for a model in Settings; without one it shows –, and a local model costs nothing.
            </p>
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
                    <th scope="col" className="num">
                      Cost / run
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
                      <td className="num">{m.provider === "ollama" ? "free" : money(m.cost_per_run)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Fold>


          {/* 16d: tokens and time run by run, and how they go together */}
          <Fold level={2} title="Run by run" digest={points.length ? `Tokens and agent time of ${plural(points.length, "full run")}` : "No full runs yet"}>
            {points.length ? (
              <div className="evals-charts">
                <div>
                  <h3>Tokens per run</h3>
                  <p className="hint">Input plus output tokens of each full run, oldest left. Hover a run for the split.</p>
                  <RunLine
                    points={points}
                    value={(p) => p.tokens_in + p.tokens_out}
                    format={(v) => kilo(v)}
                    axis={axisKilo}
                    unit="tokens"
                    detail={(p) => `${kilo(p.tokens_in)} in · ${kilo(p.tokens_out)} out` + (p.cost !== null ? ` · ${money(p.cost)}` : "")}
                    caption="Tokens per full run"
                  />
                </div>
                <div>
                  <h3>Agent time per run</h3>
                  <p className="hint">Working time of each full run, oldest left. Waiting for you isn't counted.</p>
                  <RunLine points={points} value={(p) => p.seconds} format={(v) => seconds(v)} axis={axisMinutes} top={niceMinutes} unit="of agent time" caption="Agent time per full run" />
                </div>
                <div>
                  <h3>Time against tokens</h3>
                  <p className="hint">
                    One dot per full run: up = slower, right = more tokens.
                    {r !== null && ` Across these ${points.length} runs the two move together with r = ${r.toFixed(2)} (1 = perfectly, 0 = not at all).`}
                  </p>
                  <RunScatter points={points} formatTokens={(v) => kilo(v)} formatTime={(v) => seconds(v)} axisTokens={axisKilo} axisTime={axisMinutes} />
                </div>
              </div>
            ) : (
              <p className="chart-empty">No full runs yet.</p>
            )}
          </Fold>

          <Fold
            level={2}
            title="Recent runs"
            digest={data?.recent.length ? `${data.recent_total} in all · the latest: ${data.recent[0].result}` : "None yet"}
          >
            <p className="hint">
              {showTrace
                ? "Trace links appear for runs recorded while Langfuse or LangSmith tracing was on."
                : "None of these runs has a trace. Start Langfuse before a run (or turn tracing on in Settings) to get trace links."}
            </p>
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
                    {showCost && (
                      <th scope="col" className="num">
                        Cost
                      </th>
                    )}
                    <th scope="col" className="num">
                      Evidence
                    </th>
                    {showTrace && <th scope="col">Trace</th>}
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
                      {showCost && <td className="num">{money(r.cost)}</td>}
                      <td className="num">{pct(r.pass_rate)}</td>
                      {showTrace && (
                        <td>
                          <TraceLink run={r} status={tracing} />
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {data && (
              <div className="recent-more">
                <span className="hint" aria-live="polite">
                  Showing {data.recent.length} of {data.recent_total} runs
                </span>
                {data.recent.length < data.recent_total && (
                  <>
                    <button type="button" className="btn btn-secondary btn-sm" onClick={() => setRecentCount((n) => n + RECENT_STEP)}>
                      Show more
                    </button>
                    <button type="button" className="btn btn-ghost btn-sm" onClick={() => setRecentCount(0)}>
                      All
                    </button>
                  </>
                )}
                {data.recent.length > RECENT_STEP && (
                  <button type="button" className="btn btn-ghost btn-sm" onClick={() => setRecentCount(RECENT_STEP)}>
                    Show fewer
                  </button>
                )}
              </div>
            )}
          </Fold>
        </>
      )}
    </div>
  );
}
