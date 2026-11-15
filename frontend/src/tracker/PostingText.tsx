// 16e: the job description, kept with the job. Companies take a posting
// down once applications close; this copy is what you prepare an interview
// from. Jobs saved before 1.2.0 have none: one more try to fetch it is
// offered here (the app already tried once by itself).

import { useState } from "react";
import { copy as copyText } from "../app/clipboard";
import { errorMessage, getApi } from "../bridge/bridge";

const PROBLEMS: Record<string, string> = {
  gone: "The link no longer shows this posting, so there is nothing to save.",
  unreadable: "The page couldn't be read (it needs a login, blocks apps, or you're offline).",
  "not a link": "This job came from pasted text or a file, not a web link.",
};

interface Props {
  jobId: number;
  /** Everything the page said, as saved. */
  text: string | null | undefined;
  /** The same without sign-in forms, buttons and other companies' jobs. */
  readable: string | null | undefined;
  /** A link the page can be fetched from again. */
  canFetch: boolean;
}

export function PostingText({ jobId, text, readable, canFetch }: Props) {
  const [fetched, setFetched] = useState<{ text: string; readable: string | null } | null>(null);
  const [whole, setWhole] = useState(false); // the whole page text, not only the job
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const full = fetched?.text ?? text ?? null;
  const tidy = fetched?.readable ?? readable ?? full;
  const shown = whole ? full : tidy;

  const fetchIt = async () => {
    setBusy(true);
    setProblem(null);
    try {
      const answer = await (await getApi()).fetch_posting_text(jobId);
      if (answer.posting_text) setFetched({ text: answer.posting_text, readable: answer.posting_readable });
      else setProblem(PROBLEMS[answer.result] ?? "The description couldn't be saved.");
    } catch (e) {
      setProblem(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  const copy = async () => {
    if (!shown) return;
    await copyText(shown); // works in WebView2 without the clipboard permission too
    setCopied(true);
    window.setTimeout(() => setCopied(false), 2000);
  };

  return (
    <section className="sheet-section" aria-labelledby="posting-title">
      <h3 id="posting-title">Job description</h3>
      {shown ? (
        <details className="posting-text">
          <summary>
            The posting as JobLens read it <span className="hint">(saved on this PC)</span>
          </summary>
          <div className="notes-actions">
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => void copy()}>
              {copied ? "Copied" : "Copy"}
            </button>
            {full !== tidy && (
              <button type="button" className="btn btn-ghost btn-sm" aria-pressed={whole} onClick={() => setWhole((on) => !on)}>
                {whole ? "Show only the job" : "Show the whole page"}
              </button>
            )}
          </div>
          <p className="note-text posting-body">{shown}</p>
        </details>
      ) : (
        <>
          <p className="hint">Not saved: this job was analyzed before JobLens kept job descriptions.</p>
          {canFetch && (
            <div className="notes-actions">
              <button type="button" className="btn btn-secondary btn-sm" disabled={busy} onClick={() => void fetchIt()}>
                {busy ? "Fetching…" : "Try to fetch it now"}
              </button>
            </div>
          )}
          {problem && (
            <p className="hint" role="status">
              {problem}
            </p>
          )}
        </>
      )}
    </section>
  );
}
