// The agent is paused on interrupt(): you approve (maybe after editing),
// ask for a rewrite, or reject. Nothing is saved until you approve.

import { useState, type FormEvent } from "react";
import type { Answer, ReviewPayload, RunSummary } from "../bridge/types";

interface Props {
  payload: ReviewPayload;
  summary: RunSummary;
  busy: boolean; // your answer was sent; the agent is working on it
  onAnswer(answer: Answer): void;
}

const words = (text: string) => (text.trim() ? text.trim().split(/\s+/).length : 0);

export function ReviewPanel({ payload, summary, busy, onAnswer }: Props) {
  const [text, setText] = useState(payload.draft);
  const [feedback, setFeedback] = useState("");
  const [confirmReject, setConfirmReject] = useState(false);
  const [sent, setSent] = useState<Answer["decision"] | null>(null);
  const edited = text.trim() !== payload.draft.trim();
  const locked = busy || sent !== null;

  const send = (answer: Answer) => {
    setSent(answer.decision);
    onAnswer(answer);
  };

  const rewrite = (e: FormEvent) => {
    e.preventDefault();
    if (feedback.trim() && !locked) send({ decision: "edit", feedback: feedback.trim() });
  };

  const where = [summary.company, summary.title, summary.fit_score !== undefined ? `fit ${summary.fit_score}` : null]
    .filter(Boolean)
    .join(" · ");

  return (
    <section className="card review" aria-labelledby="review-title">
      <header className="panel-head">
        <h2 id="review-title">Cover note draft</h2>
        {payload.revision > 1 && <span className="badge">Draft {payload.revision}</span>}
        <span className="panel-meta">{where}</span>
      </header>

      {payload.warnings.length > 0 && (
        <div className="notice notice-warn" role="status">
          <WarnIcon />
          <span>
            {payload.warnings.map((w) => `“${w}”`).join(", ")} {payload.warnings.length === 1 ? "is" : "are"} not in your resume, the
            posting or the research. Check {payload.warnings.length === 1 ? "it" : "them"} before approving.
          </span>
        </div>
      )}

      {summary.fit_score !== undefined && (
        <details className="why">
          <summary>
            Why fit {summary.fit_score}
            {summary.resume && <span className="why-resume"> with {summary.resume}</span>}
          </summary>
          {summary.breakdown && <p className="why-breakdown">{summary.breakdown}</p>}
          <div className="why-cols">
            <div>
              <h3>Proven by your resume</h3>
              {summary.matches?.length ? (
                <ul>
                  {summary.matches.map((m) => (
                    <li key={m.requirement}>
                      <strong>{m.requirement}</strong>
                      {m.evidence && <q>{m.evidence}</q>}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="hint">No requirement was proven by a quote.</p>
              )}
            </div>
            <div>
              <h3>Gaps</h3>
              {summary.gaps?.length ? (
                <ul>
                  {summary.gaps.map((g) => (
                    <li key={g}>{g}</li>
                  ))}
                </ul>
              ) : (
                <p className="hint">No gaps found.</p>
              )}
            </div>
          </div>
        </details>
      )}

      <div className="field">
        <label htmlFor="note">Edit the text directly, then approve</label>
        <textarea id="note" className="input note" rows={13} value={text} onChange={(e) => setText(e.target.value)} disabled={locked} />
        <span className="hint">
          {words(text)} words{edited && " · edited by you"}
        </span>
      </div>

      <form className="field" onSubmit={rewrite}>
        <label htmlFor="feedback">Or tell the agent what to change</label>
        <input
          id="feedback"
          className="input"
          type="text"
          placeholder="e.g. shorter, mention my Azure experience"
          value={feedback}
          onChange={(e) => setFeedback(e.target.value)}
          disabled={locked}
        />
        {edited && feedback.trim() && <span className="hint">A rewrite starts from the agent's draft, so your edits above will be replaced.</span>}
      </form>

      <div className="actions">
        <button
          type="button"
          className="btn btn-primary"
          disabled={locked || !text.trim()}
          onClick={() => send({ decision: "approve", text: text.trim() })}
        >
          {sent === "approve" ? "Saving..." : "Approve and save"}
        </button>
        <button type="button" className="btn btn-secondary" disabled={locked || !feedback.trim()} onClick={rewrite}>
          {sent === "edit" ? "Sending your notes..." : "Rewrite with my notes"}
        </button>
        {confirmReject ? (
          <span className="confirm" role="group" aria-label="Confirm reject">
            <span>Reject this draft? Nothing is saved.</span>
            <button type="button" className="btn btn-danger" disabled={locked} onClick={() => send({ decision: "reject" })}>
              Reject
            </button>
            <button type="button" className="btn btn-ghost" disabled={locked} onClick={() => setConfirmReject(false)}>
              Keep it
            </button>
          </span>
        ) : (
          <button type="button" className="btn btn-ghost btn-danger-text push" disabled={locked} onClick={() => setConfirmReject(true)}>
            Reject
          </button>
        )}
      </div>
    </section>
  );
}

export function WarnIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true" className="notice-icon">
      <path d="M8 1.8l6.5 11.4H1.5z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
      <path d="M8 6.2v3.2M8 11.4v.2" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
}
