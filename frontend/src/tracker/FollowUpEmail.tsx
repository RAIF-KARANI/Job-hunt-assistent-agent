// 16g: a follow-up email for one job, written only because you asked
// (opening this dialog is the ask). Code writes the email from the saved
// facts; the model adds one sentence about your work, taken from the cover
// note they already have. You can change every word before you send it.

import { useCallback, useEffect, useRef, useState } from "react";
import { copy } from "../app/clipboard";
import { errorMessage, getApi } from "../bridge/bridge";
import type { FollowUpDraft } from "../bridge/types";

interface Props {
  jobId: number;
  /** "I sent it": the follow-up clock starts again. */
  onSent(): Promise<void>;
  onClose(): void;
}

export function FollowUpEmail({ jobId, onSent, onClose }: Props) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [draft, setDraft] = useState<FollowUpDraft | null>(null);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState<"subject" | "email" | null>(null);

  const write = useCallback(() => {
    setBusy(true);
    setError(null);
    setCopied(null);
    getApi()
      .then((api) => api.draft_follow_up_email(jobId))
      .then((d) => {
        setDraft(d);
        setText(d.text);
      })
      .catch((e) => setError(errorMessage(e)))
      .finally(() => setBusy(false));
  }, [jobId]);

  useEffect(() => {
    const el = dialog.current;
    if (el && !el.open) el.showModal();
    write();
  }, [write]);

  const copyIt = (what: "subject" | "email", value: string) => copy(value).then(() => setCopied(what));

  const sent = async () => {
    await onSent();
    dialog.current?.close();
  };

  return (
    <dialog
      ref={dialog}
      className="prompt-dialog"
      aria-labelledby="follow-email-title"
      onClose={(e) => {
        e.stopPropagation(); // not the job sheet's close
        onClose();
      }}
      onClick={(e) => e.target === dialog.current && dialog.current?.close()}
    >
      <div className="prompt-body">
        <header className="prompt-head">
          {/* Focus starts on the title, not on the close button. */}
          <h2 id="follow-email-title" tabIndex={-1} autoFocus>
            Follow-up email
          </h2>
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

        {busy && !draft && (
          <p className="hint" role="status">
            Writing… this takes a few seconds.
          </p>
        )}

        {draft && (
          <section className="prompt-text" aria-label="The email">
            <p className="hint">
              JobLens doesn't send anything. Change what you like, then copy it into your own email. The role, company and date come from your
              tracker; the sentence about your work comes from your cover note.
            </p>
            <label className="field">
              <span>Subject</span>
              <span className="follow-subject">
                <input className="input" readOnly value={draft.subject} />
                <button type="button" className="btn btn-ghost btn-sm" onClick={() => void copyIt("subject", draft.subject)} aria-live="polite">
                  {copied === "subject" ? "Copied" : "Copy"}
                </button>
              </span>
            </label>
            <label className="field">
              <span>Email</span>
              <textarea className="input follow-email-area" value={text} onChange={(e) => setText(e.target.value)} rows={12} disabled={busy} />
            </label>
            {draft.note && (
              <p className="hint" role="status">
                {draft.note}
              </p>
            )}
            {draft.warnings.map((w) => (
              <p key={w} className="notice notice-warn" role="status">
                {w}
              </p>
            ))}
            <div className="actions">
              <button type="button" className="btn btn-primary" onClick={() => void copyIt("email", text)} aria-live="polite">
                {copied === "email" ? "Copied" : "Copy email"}
              </button>
              <button type="button" className="btn btn-secondary" onClick={() => void sent()} title="Marks the job as followed up: the next reminder starts from today">
                I sent it
              </button>
              <button type="button" className="btn btn-ghost" disabled={busy} onClick={write}>
                {busy ? "Writing…" : "Write again"}
              </button>
            </div>
          </section>
        )}
      </div>
    </dialog>
  );
}
