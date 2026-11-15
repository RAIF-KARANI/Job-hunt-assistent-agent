// 16i: the best-fit jobs (75+) that have an approved cover note but aren't
// applied yet, oldest first: postings close, so these shouldn't wait. A job
// you answered "Ignore" on isn't listed. Nothing is shown when the list is empty.

import type { JobRow } from "../bridge/types";
import { FitChip } from "../tracker/FitChip";
import { ago } from "../tracker/status";

const MAX_SHOWN = 6;

/** When the cover note was approved (a job moved by hand has no note: its last change). */
const readySince = (job: JobRow) => job.note_approved_at ?? job.updated_at;

export function ReadyToApply({ jobs, onOpen }: { jobs: JobRow[]; onOpen(id: number): void }) {
  const ready = jobs.filter((j) => j.ready_to_apply).sort((a, b) => readySince(a).localeCompare(readySince(b)));
  if (ready.length === 0) return null;
  const more = ready.length - MAX_SHOWN;

  return (
    <section className="card ready-card" aria-labelledby="ready-title">
      <header className="section-head">
        <h2 id="ready-title">Ready to apply</h2>
        <span className="hint">
          {ready.length === 1 ? "1 strong fit has" : `${ready.length} strong fits have`} a cover note and no application yet. Oldest first.
        </span>
      </header>
      <ul className="ready-list">
        {ready.slice(0, MAX_SHOWN).map((job) => (
          <li key={job.id}>
            <button type="button" className="ready-job" onClick={() => onOpen(job.id)} aria-label={`${job.company}, ${job.title}, fit ${job.fit_score}. Open details`}>
              <span className="ready-names">
                <span className="ready-company">{job.company}</span>
                <span className="ready-title">{job.title}</span>
                <span className="ready-when">
                  Note approved {ago(readySince(job))}
                  {job.apply_ask && <span className="follow-badge">Applied?</span>}
                </span>
              </span>
              <FitChip score={job.fit_score} />
            </button>
          </li>
        ))}
      </ul>
      {more > 0 && (
        <a className="link-sm" href="#/tracker">
          {more} more in the Tracker
        </a>
      )}
    </section>
  );
}
