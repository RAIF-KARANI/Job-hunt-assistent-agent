// Job details in a side sheet: everything the agent found, the latest
// approved cover note, and the status. A native <dialog> gives focus
// trapping and Esc-to-close for free.

import { useEffect, useRef, useState } from "react";
import { prefill } from "../analyze/runStore";
import { copy } from "../app/clipboard";
import { ResumePrompt } from "../resume/ResumePrompt";
import { errorMessage, getApi } from "../bridge/bridge";
import type { JobDetail, JobRow, JobStatus } from "../bridge/types";
import { FitChip } from "./FitChip";
import { ago, fitLevel, parseUtc, quietDays, STATUSES, statusLabel } from "./status";

interface Props {
  jobId: number;
  status: JobStatus | undefined; // live from the list, so a drag elsewhere shows here
  /** The job's row in the list (14e: is a follow-up due?). */
  row: JobRow | undefined;
  onMove(id: number, to: JobStatus): void;
  onFollowUp(id: number, action: "done" | "snooze"): Promise<void>;
  onClose(): void;
}

const isWebLink = (url: string) => /^https?:\/\//i.test(url);

export function JobSheet({ jobId, status, row, onMove, onFollowUp, onClose }: Props) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [job, setJob] = useState<JobDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [draftProblem, setDraftProblem] = useState<string | null>(null);
  const [following, setFollowing] = useState(false);
  const [promptOpen, setPromptOpen] = useState(false); // 14g

  const followUp = async (action: "done" | "snooze") => {
    setFollowing(true);
    try {
      await onFollowUp(jobId, action);
    } finally {
      setFollowing(false);
    }
  };

  useEffect(() => {
    const el = dialog.current;
    if (el && !el.open) el.showModal();
  }, []);

  useEffect(() => {
    setJob(null);
    setCopied(false);
    getApi()
      .then((api) => api.get_job(jobId))
      .then(setJob)
      .catch((e) => setError(errorMessage(e)));
  }, [jobId]);

  const note = job?.cover_notes[0];
  const current = status ?? job?.status;

  const draft = () => {
    if (!job) return;
    if (prefill(job.url)) {
      onClose();
      window.location.hash = "#/analyze";
    } else {
      setDraftProblem("The agent is busy with another job. Finish that one first.");
    }
  };

  return (
    <dialog
      ref={dialog}
      className="sheet"
      aria-labelledby="sheet-title"
      onClose={onClose}
      onClick={(e) => e.target === dialog.current && dialog.current?.close()} // click on the backdrop
    >
      <div className="sheet-body">
        <header className="sheet-head">
          <div className="sheet-names">
            <span className="eyebrow">{job?.company ?? "Loading..."}</span>
            {/* Focus starts on the title (read first by screen readers), not on the close button. */}
            <h2 id="sheet-title" tabIndex={-1} autoFocus>
              {job?.title ?? ""}
            </h2>
            {job && (
              <span className="sheet-meta">
                {[job.job.location, job.job.seniority, job.job.employment_type, job.job.salary !== "Not specified" ? job.job.salary : null]
                  .filter(Boolean)
                  .join(" · ")}
              </span>
            )}
          </div>
          <button type="button" className="btn btn-ghost icon-btn" aria-label="Close" onClick={() => dialog.current?.close()}>
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
              <path d="M3.5 3.5l9 9M12.5 3.5l-9 9" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
            </svg>
          </button>
        </header>

        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}

        {job && (
          <>
            <div className="sheet-actions">
              <label className="field status-field">
                <span>Status</span>
                <select className="input" value={current} onChange={(e) => onMove(job.id, e.target.value as JobStatus)}>
                  {STATUSES.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.label}
                    </option>
                  ))}
                </select>
              </label>
              {isWebLink(job.url) && (
                <a className="btn btn-secondary" href={job.url}>
                  Open posting
                </a>
              )}
              <button type="button" className="btn btn-secondary" onClick={draft}>
                {note ? "Draft another cover note" : "Draft a cover note"}
              </button>
              <button type="button" className="btn btn-ghost" onClick={() => setPromptOpen(true)}>
                Resume prompt
              </button>
            </div>
            {promptOpen && <ResumePrompt jobId={job.id} onClose={() => setPromptOpen(false)} />}
            {draftProblem && (
              <p className="hint" role="status">
                {draftProblem}
              </p>
            )}

            {row?.follow_up && (
              <section className="follow-up" aria-labelledby="follow-title">
                <div>
                  <h3 id="follow-title">Time to follow up?</h3>
                  <p className="hint">
                    {statusLabel(row.status)} with no news for {quietDays(row)} days. A short, polite email asking about next steps often gets an
                    answer.
                  </p>
                </div>
                <div className="follow-up-actions">
                  <button type="button" className="btn btn-primary btn-sm" disabled={following} onClick={() => void followUp("done")}>
                    I followed up
                  </button>
                  <button type="button" className="btn btn-ghost btn-sm" disabled={following} onClick={() => void followUp("snooze")}>
                    Remind me in 3 days
                  </button>
                </div>
              </section>
            )}

            <section className="sheet-section" aria-labelledby="fit-title">
              <div className="fit-head">
                <FitChip score={job.best_match.fit_score} large />
                <div>
                  <h3 id="fit-title">Fit with {job.best_match.resume_name}</h3>
                  <span className="mono-sm">{job.best_match.score_breakdown}</span>
                </div>
              </div>
              <span className="fit-bar" aria-hidden="true">
                <span className={`fit-bar-fill fit-${fitLevel(job.best_match.fit_score)}`} style={{ width: `${job.best_match.fit_score}%` }} />
              </span>
              {job.best_match.analysis.verdict && <p className="sheet-text">{job.best_match.analysis.verdict}</p>}
              <div className="evidence">
                <div>
                  <h4>Proven by your resume</h4>
                  {job.best_match.analysis.matching_skills.length ? (
                    <ul>
                      {job.best_match.analysis.matching_skills.map((m) => (
                        <li key={m.requirement}>
                          <strong>{m.requirement}</strong>
                          {m.resume_evidence && <q>{m.resume_evidence}</q>}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="hint">Nothing proven by a quote.</p>
                  )}
                </div>
                <div>
                  <h4>Gaps</h4>
                  {job.best_match.analysis.missing_skills.length ? (
                    <ul>
                      {job.best_match.analysis.missing_skills.map((g) => (
                        <li key={g}>{g}</li>
                      ))}
                    </ul>
                  ) : (
                    <p className="hint">No gaps found.</p>
                  )}
                </div>
              </div>
            </section>

            <section className="sheet-section" aria-labelledby="note-title">
              <div className="section-head">
                <h3 id="note-title">Cover note</h3>
                {note && (
                  <button
                    type="button"
                    className="btn btn-secondary btn-sm"
                    onClick={() => copy(note.text).then(() => setCopied(true))}
                    aria-live="polite"
                  >
                    {copied ? "Copied" : "Copy"}
                  </button>
                )}
              </div>
              {note ? (
                <>
                  <p className="note-text">{note.text}</p>
                  <span className="hint">
                    Approved {ago(note.approved_at)}
                    {job.cover_notes.length > 1 && ` · ${job.cover_notes.length - 1} earlier version${job.cover_notes.length > 2 ? "s" : ""}`}
                  </span>
                </>
              ) : (
                <p className="hint">No approved cover note yet.</p>
              )}
            </section>

            {job.company_brief && (
              <section className="sheet-section" aria-labelledby="company-title">
                <h3 id="company-title">About {job.company}</h3>
                <p className="sheet-text">{job.company_brief.what_they_do}</p>
                {job.company_brief.size_and_stage && job.company_brief.size_and_stage !== "Unknown" && (
                  <p className="hint">{job.company_brief.size_and_stage}</p>
                )}
                {job.company_brief.recent_news.length > 0 && (
                  <>
                    <h4>Recent news</h4>
                    <ul className="plain-list">
                      {job.company_brief.recent_news.map((n) => (
                        <li key={n}>{n}</li>
                      ))}
                    </ul>
                  </>
                )}
                {job.company_brief.sources.length > 0 && (
                  <>
                    <h4>Sources (checked against the search results)</h4>
                    <ul className="plain-list sources">
                      {job.company_brief.sources.filter(isWebLink).map((url) => (
                        <li key={url}>
                          <a href={url}>{url.replace(/^https?:\/\/(www\.)?/, "")}</a>
                        </li>
                      ))}
                    </ul>
                  </>
                )}
              </section>
            )}

            <p className="hint sheet-foot">
              Added {parseUtc(job.created_at).toLocaleDateString()} · status changed {ago(job.updated_at)} · job #{job.id}
            </p>
          </>
        )}
      </div>
    </dialog>
  );
}
