// 17d: one list of what is waiting for you (feature F16). It joins the two
// reminders the Tracker shows (14e: no news for a while; 16i: "Did you
// apply?") with the best-fit jobs that are ready to apply to (16i: fit 75+,
// an approved cover note, no application yet; oldest first, because
// postings close).

import type { JobRow } from "../bridge/types";
import { Icon, type IconName } from "../app/Icon";
import { FitChip } from "../tracker/FitChip";
import { ago, interviewAhead, interviewDate, interviewLabel, quietDays } from "../tracker/status";

const MAX_READY = 5;
const INTERVIEW_DAYS = 7; // 19b: interviews this close show here

/** 19b: still ahead and within a week, not rejected, soonest first. */
function upcoming(jobs: JobRow[], now = Date.now()): JobRow[] {
  return jobs
    .filter((j) => j.interview_at && j.status !== "rejected" && interviewAhead(j.interview_at, now))
    .filter((j) => interviewDate(j.interview_at!).getTime() - now < INTERVIEW_DAYS * 86_400_000)
    .sort((a, b) => interviewDate(a.interview_at!).getTime() - interviewDate(b.interview_at!).getTime());
}

/** When the cover note was approved (a job moved by hand has no note: its last change). */
const readySince = (job: JobRow) => job.note_approved_at ?? job.updated_at;

interface ReminderProps {
  icon: IconName;
  tone: "warn" | "ask";
  title: string;
  note: string;
  /** One job: open its details. Several: the Tracker lists them. */
  job?: JobRow;
  show: "apply" | "follow";
  onOpen(id: number): void;
}

function Reminder({ icon, tone, title, note, job, show, onOpen }: ReminderProps) {
  const body = (
    <>
      <span className={`next-icon ${tone}`}>
        <Icon name={icon} size={17} />
      </span>
      <span className="next-text">
        <span className="next-title">{title}</span>
        <span className="next-note">{note}</span>
      </span>
      <Icon name="chevron-right" size={16} />
    </>
  );
  return job ? (
    <button type="button" className="next-row" onClick={() => onOpen(job.id)}>
      {body}
    </button>
  ) : (
    <a className="next-row" href={`#/tracker?show=${show}`}>
      {body}
    </a>
  );
}

export function DoNext({ jobs, onOpen }: { jobs: JobRow[]; onOpen(id: number): void }) {
  const due = jobs.filter((j) => j.follow_up);
  const asks = jobs.filter((j) => j.apply_ask);
  const interviews = upcoming(jobs);
  const ready = jobs.filter((j) => j.ready_to_apply).sort((a, b) => readySince(a).localeCompare(readySince(b)));
  // A ready job that is also asking "Did you apply?" is one thing to do, not two.
  const total = interviews.length + due.length + asks.length + ready.filter((j) => !j.apply_ask).length;
  const more = ready.length - MAX_READY;

  return (
    <section className="card do-next" aria-labelledby="next-title">
      <header className="next-head">
        <h3 id="next-title">Do next</h3>
        {total > 0 && (
          <span className="badge next-count" title="Things waiting for you">
            {total}
          </span>
        )}
      </header>

      {total === 0 && (
        <p className="next-empty">
          Nothing is waiting for you.
          {jobs.length === 0 ? " Analyze a job and what to do about it shows up here." : " Strong fits and reminders show up here."}
        </p>
      )}

      {interviews.length > 0 && (
        <>
          <div className="next-sub">
            <h4>Interviews</h4>
            <span className="hint">The next {INTERVIEW_DAYS} days</span>
          </div>
          <ul className="next-list">
            {interviews.map((job) => (
              <li key={job.id}>
                <button
                  type="button"
                  className="next-row"
                  onClick={() => onOpen(job.id)}
                  aria-label={`Interview with ${job.company}, ${job.title}, ${interviewLabel(job.interview_at!)}. Open details`}
                >
                  <span className="next-icon ask">
                    <Icon name="calendar" size={17} />
                  </span>
                  <span className="next-text">
                    <span className="next-title">{job.company}</span>
                    <span className="next-note">{job.title}</span>
                  </span>
                  <span className="next-when">{interviewLabel(job.interview_at!)}</span>
                </button>
              </li>
            ))}
          </ul>
        </>
      )}

      {(due.length > 0 || asks.length > 0) && (
        <div className="next-list">
          {due.length > 0 && (
            <Reminder
              icon="message"
              tone="warn"
              title={due.length === 1 ? `Follow up with ${due[0].company}` : `Follow up on ${due.length} applications`}
              note={due.length === 1 ? `No news for ${quietDays(due[0])} days. A short email can help.` : "No news for a while. A short email can help."}
              job={due.length === 1 ? due[0] : undefined}
              show="follow"
              onOpen={onOpen}
            />
          )}
          {asks.length > 0 && (
            <Reminder
              icon="question"
              tone="ask"
              title={asks.length === 1 ? `Did you apply to ${asks[0].company}?` : "Did you apply?"}
              note={asks.length === 1 ? "The cover note has been ready for over a day." : `${asks.length} cover notes have been ready for over a day.`}
              job={asks.length === 1 ? asks[0] : undefined}
              show="apply"
              onOpen={onOpen}
            />
          )}
        </div>
      )}

      {ready.length > 0 && (
        <>
          <div className="next-sub">
            <h4>Ready to apply</h4>
            <span className="hint">Strong fits with an approved note, oldest first</span>
          </div>
          <ul className="next-list">
            {ready.slice(0, MAX_READY).map((job) => (
              <li key={job.id}>
                <button
                  type="button"
                  className="next-row ready"
                  onClick={() => onOpen(job.id)}
                  aria-label={`${job.company}, ${job.title}, fit ${job.fit_score}, note approved ${ago(readySince(job))}. Open details`}
                >
                  <FitChip score={job.fit_score} />
                  <span className="next-text">
                    <span className="next-title">{job.company}</span>
                    <span className="next-note">{job.title}</span>
                  </span>
                  <span className="next-when">{ago(readySince(job))}</span>
                </button>
              </li>
            ))}
          </ul>
          {more > 0 && (
            <a className="link-sm" href="#/tracker">
              {more} more in the Tracker
            </a>
          )}
        </>
      )}
    </section>
  );
}
