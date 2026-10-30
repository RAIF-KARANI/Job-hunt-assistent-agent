// The job picked in the galaxy: fit, proven skills, gaps, what the company
// does. Full details open in the same sheet as on the Tracker.

import { useEffect, useState } from "react";
import { prefill } from "../analyze/runStore";
import { errorMessage, getApi } from "../bridge/bridge";
import type { JobDetail, JobRow } from "../bridge/types";
import { FitChip } from "../tracker/FitChip";
import { statusLabel } from "../tracker/status";

const MAX_CHIPS = 4;

export function SelectedJob({ job, onOpen }: { job: JobRow; onOpen(id: number): void }) {
  const [detail, setDetail] = useState<JobDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [problem, setProblem] = useState<string | null>(null);

  useEffect(() => {
    let current = true;
    setDetail(null);
    setError(null);
    setProblem(null);
    getApi()
      .then((api) => api.get_job(job.id))
      .then((d) => current && setDetail(d))
      .catch((e) => current && setError(errorMessage(e)));
    return () => {
      current = false; // a quick click on another job: ignore the slower answer
    };
  }, [job.id]);

  const skills = detail?.best_match.analysis.matching_skills.map((m) => m.requirement) ?? [];
  const gaps = detail?.best_match.analysis.missing_skills ?? [];

  const draft = () => {
    if (!detail) return;
    if (prefill(detail.url)) window.location.hash = "#/analyze";
    else setProblem("The agent is busy with another job. Finish that one first.");
  };

  return (
    <aside className="card selected-job" aria-labelledby="selected-title">
      <header className="selected-head">
        <div className="selected-names">
          <span className="eyebrow">{job.company}</span>
          <h2 id="selected-title" title={job.title}>
            {job.title}
          </h2>
          <span className="badge">{statusLabel(job.status)}</span>
        </div>
        <FitChip score={job.fit_score} large />
      </header>

      {error && <p className="error">{error}</p>}

      {detail && (
        <>
          <div className="chip-group">
            <h3>Proven by your resume</h3>
            {skills.length ? (
              <ul className="chips">
                {skills.slice(0, MAX_CHIPS).map((s) => (
                  <li key={s} className="chip chip-ok" title={s}>
                    {s}
                  </li>
                ))}
                {skills.length > MAX_CHIPS && <li className="chip">+{skills.length - MAX_CHIPS} more</li>}
              </ul>
            ) : (
              <p className="hint">Nothing proven by a quote.</p>
            )}
          </div>
          <div className="chip-group">
            <h3>Gaps</h3>
            {gaps.length ? (
              <ul className="chips">
                {gaps.slice(0, MAX_CHIPS).map((g) => (
                  <li key={g} className="chip chip-gap" title={g}>
                    {g}
                  </li>
                ))}
                {gaps.length > MAX_CHIPS && <li className="chip">+{gaps.length - MAX_CHIPS} more</li>}
              </ul>
            ) : (
              <p className="hint">No gaps found.</p>
            )}
          </div>
          {detail.company_brief?.what_they_do && <p className="selected-brief">{detail.company_brief.what_they_do}</p>}
        </>
      )}

      <div className="selected-actions">
        <button type="button" className="btn btn-secondary" onClick={() => onOpen(job.id)}>
          Open details
        </button>
        <button type="button" className="btn btn-ghost" onClick={draft} disabled={!detail}>
          Draft a cover note
        </button>
      </div>
      {problem && (
        <p className="hint" role="status">
          {problem}
        </p>
      )}
    </aside>
  );
}
