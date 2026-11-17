// Job details in a side sheet: everything the agent found, the latest
// approved cover note, and the status. A native <dialog> gives focus
// trapping and Esc-to-close for free.

import { useEffect, useRef, useState, type ReactNode } from "react";
import { prefill } from "../analyze/runStore";
import { copy } from "../app/clipboard";
import { ResumePrompt } from "../resume/ResumePrompt";
import { Fold } from "../app/Fold";
import { NotesSection } from "./NotesSection";
import { Exported } from "../app/Exported";
import { errorMessage, getApi } from "../bridge/bridge";
import type { ApplyAnswer, JobDetail, JobRow, JobStatus } from "../bridge/types";
import { FitChip } from "./FitChip";
import { ago, fitLevel, interviewLabel, parseUtc, quietDays, STATUSES, statusLabel } from "./status";
import { FollowUpEmail } from "./FollowUpEmail";
import { InterviewPrep } from "./InterviewPrep";
import { PostingText } from "./PostingText";
import type { FollowUpAction } from "./useJobs";

interface Props {
  jobId: number;
  status: JobStatus | undefined; // live from the list, so a drag elsewhere shows here
  /** The job's row in the list (14e: is a follow-up due?). */
  row: JobRow | undefined;
  onMove(id: number, to: JobStatus): void;
  onFollowUp(id: number, action: FollowUpAction): Promise<void>;
  /** 16i: the answer to "Did you apply?". */
  onApply(id: number, answer: ApplyAnswer): Promise<void>;
  /** 14h: notes saved: refresh the cards. */
  onChanged(): void;
  /** 1.0.1: the job was deleted. */
  onDeleted(what: string): void;
  onClose(): void;
}

const isWebLink = (url: string) => /^https?:\/\//i.test(url);

export function JobSheet({ jobId, status, row, onMove, onFollowUp, onApply, onChanged, onDeleted, onClose }: Props) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [job, setJob] = useState<JobDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [draftProblem, setDraftProblem] = useState<string | null>(null);
  const [following, setFollowing] = useState(false);
  const [promptOpen, setPromptOpen] = useState(false); // 14g
  const [prepOpen, setPrepOpen] = useState(false); // 16f
  const [emailOpen, setEmailOpen] = useState(false); // 16g: only when you ask
  const [confirmDelete, setConfirmDelete] = useState(false); // 1.0.1
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [savedNote, setSavedNote] = useState<string | null>(null); // 14i: where the export went
  const [exportError, setExportError] = useState<string | null>(null);

  const deleteJob = async () => {
    setDeleteError(null);
    try {
      const removed = await (await getApi()).delete_job(jobId);
      onDeleted(`${removed.company} · ${removed.title}`);
      dialog.current?.close();
    } catch (e) {
      setDeleteError(errorMessage(e));
    }
  };

  const exportNote = async (fmt: "txt" | "docx" | "pdf") => {
    setExportError(null);
    try {
      const result = await (await getApi()).export_cover_note(jobId, fmt);
      if (result) setSavedNote(result.path);
    } catch (e) {
      setExportError(errorMessage(e));
    }
  };

  const applyAnswer = async (answer: ApplyAnswer) => {
    setFollowing(true);
    try {
      await onApply(jobId, answer);
    } finally {
      setFollowing(false);
    }
  };

  const followUp = async (action: FollowUpAction) => {
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

  // 17e: what comes next for a job at this stage (shown when no reminder is open).
  const next: { title: string; text: string; actions: ReactNode } | null = !job
    ? null
    : current === "researched"
      ? {
          title: "Next: a cover note",
          text: "There is no approved cover note yet. JobLens drafts one from the achievements that fit this job, and you approve it.",
          actions: (
            <button type="button" className="btn btn-primary btn-sm" onClick={draft}>
              Draft a cover note
            </button>
          ),
        }
      : current === "cover_note_ready"
        ? {
            title: "Next: apply",
            text: "Your cover note is approved. Copy it from below, apply on the posting, then tell JobLens.",
            actions: (
              <>
                {isWebLink(job.url) && (
                  <a className="btn btn-primary btn-sm" href={job.url}>
                    Open posting
                  </a>
                )}
                <button type="button" className="btn btn-secondary btn-sm" onClick={() => onMove(job.id, "applied")}>
                  I applied
                </button>
              </>
            ),
          }
        : current === "applied"
          ? {
              title: "Waiting to hear back",
              text: "JobLens reminds you here if there is no news for a while.",
              actions: (
                <button type="button" className="btn btn-secondary btn-sm" onClick={() => setEmailOpen(true)}>
                  Write a follow-up email
                </button>
              ),
            }
          : current === "interviewing"
            ? {
                title: "Next: prepare for the interview",
                text: "A prep sheet for this job, from the posting and your resume.",
                actions: (
                  <button type="button" className="btn btn-primary btn-sm" onClick={() => setPrepOpen(true)}>
                    Interview prep
                  </button>
                ),
              }
            : null;

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
            <span className="sheet-company">{job?.company ?? "Loading..."}</span>
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
            {row?.apply_ask && (
              <section className="follow-up" aria-labelledby="apply-title">
                <div>
                  <h3 id="apply-title">Did you apply?</h3>
                  <p className="hint">
                    The cover note has been ready for a day, and postings close. With no answer for a day, JobLens stops asking about this job.
                  </p>
                </div>
                <div className="follow-up-actions">
                  <button type="button" className="btn btn-primary btn-sm" disabled={following} onClick={() => void applyAnswer("yes")}>
                    Yes, I applied
                  </button>
                  <button
                    type="button"
                    className="btn btn-ghost btn-sm"
                    disabled={following}
                    title="Ask again in 24 hours"
                    onClick={() => void applyAnswer("not_yet")}
                  >
                    Not yet
                  </button>
                  <button
                    type="button"
                    className="btn btn-ghost btn-sm"
                    disabled={following}
                    title="Never ask again about this job"
                    onClick={() => void applyAnswer("ignore")}
                  >
                    Stop asking
                  </button>
                </div>
              </section>
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
                  <button type="button" className="btn btn-primary btn-sm" disabled={following} onClick={() => setEmailOpen(true)}>
                    Draft a follow-up email
                  </button>
                  <button type="button" className="btn btn-secondary btn-sm" disabled={following} onClick={() => void followUp("done")}>
                    I followed up
                  </button>
                  <button type="button" className="btn btn-ghost btn-sm" disabled={following} onClick={() => void followUp("snooze")}>
                    Remind me in 3 days
                  </button>
                  <button
                    type="button"
                    className="btn btn-ghost btn-sm"
                    disabled={following}
                    title="No more reminders for this job until its status changes"
                    onClick={() => void followUp("ignore")}
                  >
                    Ignore
                  </button>
                </div>
              </section>
            )}

            {/* 17e: when nothing is asking for an answer, say what comes next for a job at this stage. */}
            {!row?.apply_ask && !row?.follow_up && next && (
              <section className="next-step" aria-labelledby="next-step-title">
                <div>
                  <h3 id="next-step-title">{next.title}</h3>
                  <p className="hint">{next.text}</p>
                </div>
                <div className="follow-up-actions">{next.actions}</div>
              </section>
            )}

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
            </div>
            {promptOpen && <ResumePrompt jobId={job.id} onClose={() => setPromptOpen(false)} />}
            {prepOpen && <InterviewPrep jobId={job.id} onClose={() => setPrepOpen(false)} />}
            {emailOpen && <FollowUpEmail jobId={job.id} onSent={() => onFollowUp(job.id, "done")} onClose={() => setEmailOpen(false)} />}
            {draftProblem && (
              <p className="hint" role="status">
                {draftProblem}
              </p>
            )}

            <div className="sheet-folds">
            <Fold flat defaultOpen title="Fit" digest={`${job.best_match.fit_score} with ${job.best_match.resume_name}`}>
              <div className="fit-head">
                <FitChip score={job.best_match.fit_score} large />
                <div>
                  <strong className="fit-with">Fit with {job.best_match.resume_name}</strong>
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
                  {!!job.best_match.analysis.partial_skills?.length && (
                    <>
                      <h4>Partly shown</h4>
                      <ul>
                        {job.best_match.analysis.partial_skills.map((m) => (
                          <li key={m.requirement}>
                            <strong>{m.requirement}</strong>
                            {m.resume_evidence && <q>{m.resume_evidence}</q>}
                            {job.best_match.analysis.gap_reasons?.[m.requirement] && (
                              <span className="hint">{job.best_match.analysis.gap_reasons[m.requirement]}</span>
                            )}
                          </li>
                        ))}
                      </ul>
                    </>
                  )}
                </div>
                <div>
                  <h4>Gaps</h4>
                  {job.best_match.analysis.missing_skills.length ? (
                    <ul>
                      {job.best_match.analysis.missing_skills.map((g) => (
                        <li key={g}>
                          {g}
                          {job.best_match.analysis.gap_reasons?.[g] && (
                            <span className="hint">{job.best_match.analysis.gap_reasons[g]}</span>
                          )}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="hint">No gaps found.</p>
                  )}
                </div>
              </div>
            </Fold>

            <Fold
              flat
              defaultOpen={current === "cover_note_ready"}
              title="Cover note"
              digest={note ? `Approved ${ago(note.approved_at)}` : "None approved yet"}
            >
              <div className="section-head">
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
                  <div className="export-row" role="group" aria-label="Save the cover note as a file">
                    <span className="hint">Save as</span>
                    {(["docx", "pdf", "txt"] as const).map((fmt) => (
                      <button key={fmt} type="button" className="btn btn-ghost btn-sm" onClick={() => void exportNote(fmt)}>
                        {fmt === "docx" ? "Word (.docx)" : fmt === "pdf" ? "PDF" : "Text (.txt)"}
                      </button>
                    ))}
                  </div>
                  {savedNote && <Exported what="Cover note" path={savedNote} />}
                  {exportError && (
                    <p className="error" role="alert">
                      {exportError}
                    </p>
                  )}
                </>
              ) : (
                <p className="hint">No approved cover note yet.</p>
              )}
            </Fold>

            <Fold
              flat
              defaultOpen={!!(job.notes || job.contact || job.interview_at)}
              title="Your notes"
              digest={job.interview_at ? `Interview ${interviewLabel(job.interview_at)}` : job.contact || (job.notes ? "Saved" : "Interview date, contact, notes")}
            >
              <NotesSection key={job.id} jobId={job.id} initial={job} onSaved={onChanged} />
            </Fold>

            <Fold flat title="More tools" digest="Drafts, resume prompt, interview prep">
              <div className="tool-row">
                <button type="button" className="btn btn-secondary btn-sm" onClick={draft}>
                  {note ? "Draft another cover note" : "Draft a cover note"}
                </button>
                <button type="button" className="btn btn-secondary btn-sm" onClick={() => setPromptOpen(true)}>
                  Resume prompt
                </button>
                {(current === "applied" || current === "interviewing") && (
                  <button type="button" className="btn btn-secondary btn-sm" onClick={() => setEmailOpen(true)}>
                    Follow-up email
                  </button>
                )}
                <button type="button" className="btn btn-secondary btn-sm" onClick={() => setPrepOpen(true)}>
                  Interview prep
                </button>
              </div>
            </Fold>

            {job.company_brief && (
              <Fold
                flat
                title={`About ${job.company}`}
                digest={job.company_brief.size_and_stage && job.company_brief.size_and_stage !== "Unknown" ? job.company_brief.size_and_stage : "What they do, recent news"}
              >
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
              </Fold>
            )}

            </div>

            {/* its own key: the same key as NotesSection above made React draw the notes twice */}
            <PostingText key={`posting-${job.id}`} jobId={job.id} text={job.posting_text} readable={job.posting_readable} canFetch={isWebLink(job.url)} />

            <p className="hint sheet-foot">
              Added {parseUtc(job.created_at).toLocaleDateString()} · status changed {ago(job.updated_at)} · job #{job.id}
            </p>

            <section className="delete-job" aria-labelledby="delete-title">
              {!confirmDelete ? (
                <button type="button" className="btn btn-ghost btn-sm btn-danger-text" onClick={() => setConfirmDelete(true)}>
                  Delete this job…
                </button>
              ) : (
                <div className="delete-confirm" role="alertdialog" aria-labelledby="delete-title" aria-describedby="delete-text">
                  <h3 id="delete-title">Delete {job.company}?</h3>
                  <p id="delete-text" className="hint">
                    This removes the job, its analysis, {job.cover_notes.length ? `its ${job.cover_notes.length} approved cover note${job.cover_notes.length > 1 ? "s" : ""}` : "its cover notes"}{" "}
                    and your notes from this PC. It can't be undone. Evals keeps its numbers.
                  </p>
                  <div className="notes-actions">
                    <button type="button" className="btn btn-danger btn-sm" onClick={() => void deleteJob()}>
                      Delete
                    </button>
                    <button type="button" className="btn btn-ghost btn-sm" onClick={() => setConfirmDelete(false)} autoFocus>
                      Cancel
                    </button>
                  </div>
                  {deleteError && (
                    <p className="error" role="alert">
                      {deleteError}
                    </p>
                  )}
                </div>
              )}
            </section>
          </>
        )}
      </div>
    </dialog>
  );
}
