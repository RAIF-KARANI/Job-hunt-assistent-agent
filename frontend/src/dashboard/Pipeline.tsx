// 17d: the lead card of the Dashboard. Every tracked job, as one bar split
// by status, with the count for each status written out (feature F15).

import type { JobRow } from "../bridge/types";
import { Icon } from "../app/Icon";
import { STATUSES } from "../tracker/status";

const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? "" : "s"}`;

export function Pipeline({ jobs }: { jobs: JobRow[] | null }) {
  const counts = STATUSES.map((s) => ({ ...s, count: jobs?.filter((j) => j.status === s.id).length ?? 0 }));
  const total = jobs?.length ?? 0;
  const of = (id: string) => counts.find((c) => c.id === id)?.count ?? 0;
  const applied = of("applied") + of("interviewing") + of("offer");
  const interviewing = of("interviewing");

  return (
    <section className="kpi kpi-blue pipeline" aria-labelledby="pipeline-title">
      <div className="pipeline-lead">
        <h3 id="pipeline-title" className="kpi-label">
          <span className="kpi-icon">
            <Icon name="briefcase" size={16} />
          </span>
          Jobs tracked
        </h3>
        <p className="pipeline-figure">
          <span className="pipeline-total">{jobs ? total : "–"}</span>
          {jobs && total > 0 && (
            <span className="kpi-note">
              {applied} applied, {interviewing ? `${interviewing} interviewing` : "none interviewing yet"}
            </span>
          )}
        </p>
      </div>

      {jobs && total === 0 && <p className="kpi-note pipeline-empty">No jobs yet. Analyze a posting and it shows up here.</p>}

      {total > 0 && (
        <div className="pipeline-detail">
          <div className="pipeline-bar" role="img" aria-label={counts.map((c) => `${c.label} ${c.count}`).join(", ")}>
            {counts
              .filter((c) => c.count > 0)
              .map((c) => (
                <span key={c.id} style={{ flexGrow: c.count, background: c.color }} title={`${plural(c.count, "job")}: ${c.label.toLowerCase()}`} />
              ))}
          </div>
          <ul className="pipeline-legend">
            {counts.map((c) => (
              <li key={c.id} className={c.count ? undefined : "none"}>
                <i className="dot" style={{ background: c.color }} />
                {c.label}
                <b>{c.count}</b>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
