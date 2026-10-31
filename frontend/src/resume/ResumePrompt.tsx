// The resume-improvement prompt (14g): how much of the job your resume
// visibly covers, and a prompt to paste into another AI with your resume.
// Built from the saved analysis by plain code: no AI call, nothing is sent.

import { useEffect, useRef, useState } from "react";
import { copy } from "../app/clipboard";
import { errorMessage, getApi } from "../bridge/bridge";
import type { ResumePromptData } from "../bridge/types";

interface Props {
  jobId: number;
  onClose(): void;
}

const percent = (ratio: number) => `${Math.round(ratio * 100)}%`;

export function ResumePrompt({ jobId, onClose }: Props) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [data, setData] = useState<ResumePromptData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [anyway, setAnyway] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    const el = dialog.current;
    if (el && !el.open) el.showModal();
  }, []);

  useEffect(() => {
    getApi()
      .then((api) => api.resume_prompt(jobId))
      .then(setData)
      .catch((e) => setError(errorMessage(e)));
  }, [jobId]);

  const cov = data?.coverage;
  const showPrompt = data && (!cov?.fits || anyway);

  return (
    <dialog
      ref={dialog}
      className="prompt-dialog"
      aria-labelledby="prompt-title"
      onClose={(e) => {
        e.stopPropagation(); // not the job sheet's close
        onClose();
      }}
      onClick={(e) => e.target === dialog.current && dialog.current?.close()}
    >
      <div className="prompt-body">
        <header className="prompt-head">
          {/* Focus starts on the title, not on the close button. */}
          <h2 id="prompt-title" tabIndex={-1} autoFocus>
            Improve your resume for this job
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

        {cov && data && (
          <section className="coverage" aria-label="Keyword coverage">
            <p className="coverage-line">
              <strong>{data.resume}</strong> shows{" "}
              <strong>
                {cov.required_shown} of {cov.required_total}
              </strong>{" "}
              required skills ({percent(cov.ratio)})
              {cov.nice_total > 0 && (
                <span className="hint">
                  {" "}
                  · {cov.nice_shown} of {cov.nice_total} nice-to-haves
                </span>
              )}
            </p>
            <span className="fit-bar" aria-hidden="true">
              <span className={`fit-bar-fill fit-${cov.ratio >= 0.75 ? "high" : cov.ratio >= 0.55 ? "mid" : "low"}`} style={{ width: percent(cov.ratio) }} />
            </span>
            <p className="hint">
              Keyword coverage: the job's required skills your resume visibly proves, checked against quotes from it. Not an "ATS score":
              every applicant tracking system is different.
            </p>
            {cov.missing.length > 0 && (
              <>
                <h3>Not shown yet</h3>
                <ul className="plain-list">
                  {cov.missing.map((m) => (
                    <li key={m}>{m}</li>
                  ))}
                </ul>
              </>
            )}
          </section>
        )}

        {cov?.fits && !anyway && (
          <section className="prompt-fits" role="status">
            <h3>Your resume already fits this job</h3>
            <p>
              It shows every required skill. Rewording it is unlikely to help much: your time is better spent applying.
            </p>
            <button type="button" className="link-button" onClick={() => setAnyway(true)}>
              Generate the prompt anyway
            </button>
          </section>
        )}

        {showPrompt && (
          <section className="prompt-text" aria-labelledby="prompt-text-title">
            <div className="section-head">
              <h3 id="prompt-text-title">The prompt</h3>
              <button type="button" className="btn btn-primary btn-sm" onClick={() => copy(data.prompt).then(() => setCopied(true))} aria-live="polite">
                {copied ? "Copied" : "Copy prompt"}
              </button>
            </div>
            <p className="hint">
              Paste it into another AI (ChatGPT, Claude…), then paste your resume at the end. Your resume isn't in it: you choose what you share.
              It tells the AI to reword only experience you really have, never to invent any.
            </p>
            <textarea className="input prompt-area" readOnly value={data.prompt} aria-label="Resume prompt" rows={14} />
          </section>
        )}
      </div>
    </dialog>
  );
}
