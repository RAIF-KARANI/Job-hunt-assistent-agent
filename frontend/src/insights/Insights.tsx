// Insights (19c, E7): what your own tracker says about your search. Plain
// counts, no AI, nothing leaves the PC. Every bar has its numbers written
// next to it; a group under the minimum shows its counts but no rate, so
// "1 of 2" never reads as "50 %".

import { useEffect, useState } from "react";
import { errorMessage, getApi } from "../bridge/bridge";
import type { InsightGroup, InsightsData, JobStatus } from "../bridge/types";
import { parseUtc, statusLabel } from "../tracker/status";

const pct = (rate: number) => `${Math.round(rate * 100)}%`;
const plural = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;
const days = (d: number) => (d < 1 ? "under a day" : `${Math.round(d)} day${Math.round(d) === 1 ? "" : "s"}`);
const ORDER: JobStatus[] = ["researched", "cover_note_ready", "applied", "interviewing", "offer", "rejected"];

function Tile({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <div className="tile">
      <span className="tile-label">{label}</span>
      <span className="tile-value">{value}</span>
      <span className="tile-note">{note}</span>
    </div>
  );
}

/** One group: interviews out of applications, the bar is the rate. */
function GroupBars({ groups, min }: { groups: InsightGroup[]; min: number }) {
  return (
    <ul className="bars insight-bars">
      {groups.map((g) => {
        const counts = `${g.interviews} of ${g.applications}`;
        const value = g.rate === null ? `${counts} · too few to say` : `${counts} · ${pct(g.rate)}`;
        const title =
          g.rate === null
            ? `${g.name}: ${plural(g.applications, "application")}, ${plural(g.interviews, "interview")}. Fewer than ${min} applications: no rate yet.`
            : `${g.name}: ${pct(g.rate)} of ${plural(g.applications, "application")} reached an interview${g.offers ? `, ${plural(g.offers, "offer")}` : ""}.`;
        return (
          <li key={g.name} className={g.rate === null ? "bar-row few" : "bar-row"} title={title}>
            <span className="bar-label">{g.name}</span>
            <span className="bar-track" aria-hidden="true">
              {g.rate !== null && <span className="bar-fill" style={{ width: g.rate > 0 ? `max(${(g.rate * 100).toFixed(1)}%, 4px)` : 0 }} />}
            </span>
            <span className="bar-value">{value}</span>
          </li>
        );
      })}
    </ul>
  );
}

function GroupCard({ id, title, hint, groups, min }: { id: string; title: string; hint: string; groups: InsightGroup[]; min: number }) {
  return (
    <section className="card chart-card" aria-labelledby={id}>
      <h3 id={id}>{title}</h3>
      <p className="hint">{hint}</p>
      {groups.length ? <GroupBars groups={groups} min={min} /> : <p className="chart-empty">No applications yet.</p>}
    </section>
  );
}

export function Insights() {
  const [data, setData] = useState<InsightsData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getApi()
      .then((api) => api.insights())
      .then(setData)
      .catch((e) => setError(errorMessage(e)));
  }, []);

  const most = data ? Math.max(1, ...Object.values(data.stages)) : 1;
  const since = data?.recorded_since ? parseUtc(data.recorded_since).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" }) : null;
  const rejected = data ? Object.entries(data.rejected).filter(([, n]) => n > 0) : [];

  return (
    <div className="page insights">
      <header className="page-head">
        <h1>Insights</h1>
        <p>What your tracker says about your search. Plain counts from your own data, worked out on this PC.</p>
      </header>

      {error && (
        <p className="notice notice-danger" role="alert">
          Couldn't read the tracker: {error}
        </p>
      )}
      {!data && !error && <p className="hint">Counting…</p>}

      {data && (
        <>
          <div className="tiles">
            <Tile label="Applications" value={String(data.applications)} note={`of ${plural(data.jobs, "job")} in the tracker`} />
            <Tile
              label="Reached an interview"
              value={data.rate === null ? String(data.interviews) : pct(data.rate)}
              note={data.rate === null ? `of ${data.applications}: a rate needs ${data.min_group} applications` : `${data.interviews} of ${data.applications} applications`}
            />
            <Tile label="Offers" value={String(data.offers)} note={data.offers ? "jobs that reached Offer" : "none yet"} />
            <Tile
              label="Typical wait for an answer"
              value={data.answer_days.median === null ? "–" : days(data.answer_days.median)}
              note={
                data.answer_days.count
                  ? `median of ${plural(data.answer_days.count, "answer")}, ${days(data.answer_days.fastest!)} to ${days(data.answer_days.slowest!)}`
                  : "known once a job you mark Applied gets an answer"
              }
            />
          </div>

          {(data.unknown > 0 || data.waiting.count > 0) && (
            <div className="insight-notes">
              {data.waiting.count > 0 && (
                <p className="hint">
                  {plural(data.waiting.count, "application")} still waiting for an answer, the longest for {days(data.waiting.longest_days!)}.
                </p>
              )}
              {data.unknown > 0 && (
                <p className="hint">
                  {plural(data.unknown, "rejected job")} from before JobLens kept a history can't be placed: rejected by them, or dropped by you before
                  applying. {data.unknown === 1 ? "It is" : "They are"} left out of the rates rather than guessed.
                </p>
              )}
            </div>
          )}

          {data.applications === 0 ? (
            <section className="card review empty">
              <h2>Nothing to count yet</h2>
              <p className="lead">
                Insights starts with your applications. Mark a job as Applied in the <a href="#/tracker">Tracker</a> (or answer "Did you
                apply?") and it shows up here.
              </p>
            </section>
          ) : (
            <div className="insight-grid">
              <GroupCard
                id="by-resume"
                title="Which resume gets interviews"
                hint="Interviews out of applications, by the resume JobLens picked as the best fit."
                groups={data.by_resume}
                min={data.min_group}
              />
              <GroupCard
                id="by-site"
                title="Where the jobs came from"
                hint="By the site of the posting's link. Company career pages are named after the system they run on (Greenhouse, Lever, Workday…)."
                groups={data.by_site}
                min={data.min_group}
              />
              <GroupCard
                id="by-fit"
                title="Does the fit score predict it?"
                hint="If higher fits get more interviews, the score is worth sorting by."
                groups={data.by_fit}
                min={data.min_group}
              />
              <section className="card chart-card" aria-labelledby="stages-title">
                <h3 id="stages-title">Where your jobs are now</h3>
                <p className="hint">Every job in the tracker, by its status today.</p>
                <ul className="bars">
                  {ORDER.map((s) => (
                    <li key={s} className="bar-row" title={`${statusLabel(s)}: ${plural(data.stages[s] ?? 0, "job")}`}>
                      <span className="bar-label">{statusLabel(s)}</span>
                      <span className="bar-track" aria-hidden="true">
                        <span className="bar-fill" style={{ width: data.stages[s] ? `max(${(((data.stages[s] ?? 0) / most) * 100).toFixed(1)}%, 4px)` : 0 }} />
                      </span>
                      <span className="bar-value">{data.stages[s] ?? 0}</span>
                    </li>
                  ))}
                </ul>
                {rejected.length > 0 && (
                  <p className="hint insight-rejected">Rejected: {rejected.map(([where, n]) => `${n} ${where}`).join(", ")}.</p>
                )}
              </section>
            </div>
          )}

          <p className="hint insight-foot">
            {since ? `Status changes recorded since ${since}.` : "Status changes are recorded from now on."} A rate shows once a group has{" "}
            {data.min_group} applications.
          </p>
        </>
      )}
    </div>
  );
}
