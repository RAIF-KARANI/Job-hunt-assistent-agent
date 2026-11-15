// 16f: the interview prep sheet. Everything saved about one job on one
// page: what they ask for, what your resume proves (with its exact words),
// what it doesn't, the company, your cover note, your notes and the job
// description. Built from the tracker by plain code: no AI call, so nothing
// here is newly written or guessed.

import { useEffect, useRef, useState } from "react";
import { Exported } from "../app/Exported";
import { copy } from "../app/clipboard";
import { errorMessage, getApi } from "../bridge/bridge";
import type { PrepSheet } from "../bridge/types";

interface Props {
  jobId: number;
  onClose(): void;
}

const FORMATS = [
  { id: "pdf", label: "PDF" },
  { id: "docx", label: "Word (.docx)" },
  { id: "txt", label: "Text (.txt)" },
] as const;

function List({ items }: { items: string[] }) {
  return (
    <ul className="plain-list">
      {items.map((item) => (
        <li key={item}>{item}</li>
      ))}
    </ul>
  );
}

export function InterviewPrep({ jobId, onClose }: Props) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [sheet, setSheet] = useState<PrepSheet | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    const el = dialog.current;
    if (el && !el.open) el.showModal();
  }, []);

  useEffect(() => {
    getApi()
      .then((api) => api.interview_prep(jobId))
      .then(setSheet)
      .catch((e) => setError(errorMessage(e)));
  }, [jobId]);

  const save = async (fmt: "pdf" | "docx" | "txt") => {
    setError(null);
    try {
      const result = await (await getApi()).export_interview_prep(jobId, fmt);
      if (result) setSaved(result.path);
    } catch (e) {
      setError(errorMessage(e));
    }
  };

  const research = sheet?.research;

  return (
    <dialog
      ref={dialog}
      className="prompt-dialog prep-dialog"
      aria-labelledby="prep-title"
      onClose={(e) => {
        e.stopPropagation(); // not the job sheet's close
        onClose();
      }}
      onClick={(e) => e.target === dialog.current && dialog.current?.close()}
    >
      <div className="prompt-body prep-body">
        <header className="prompt-head">
          <div>
            <span className="eyebrow">Interview prep</span>
            {/* Focus starts on the title, not on the close button. */}
            <h2 id="prep-title" tabIndex={-1} autoFocus>
              {sheet ? `${sheet.title} at ${sheet.company}` : "Loading…"}
            </h2>
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

        {sheet && (
          <>
            <p className="hint prep-note">
              Everything here was saved when the job was analyzed, and the quotes are your resume's own words. Nothing is newly written, so nothing
              is guessed.
            </p>
            <div className="export-row" role="group" aria-label="Save the prep sheet as a file">
              <span className="hint">Save as</span>
              {FORMATS.map((f) => (
                <button key={f.id} type="button" className="btn btn-ghost btn-sm" onClick={() => void save(f.id)}>
                  {f.label}
                </button>
              ))}
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => copy(sheet.text).then(() => setCopied(true))} aria-live="polite">
                {copied ? "Copied" : "Copy all"}
              </button>
            </div>
            {saved && <Exported what="Prep sheet" path={saved} />}

            {sheet.facts.length > 0 && (
              <dl className="prep-facts">
                {sheet.facts.map((f) => (
                  <div key={f.label}>
                    <dt>{f.label}</dt>
                    <dd>{f.value}</dd>
                  </div>
                ))}
              </dl>
            )}

            {(sheet.summary || sheet.responsibilities.length > 0) && (
              <section className="prep-section" aria-labelledby="prep-role">
                <h3 id="prep-role">The role</h3>
                {sheet.summary && <p>{sheet.summary}</p>}
                {sheet.responsibilities.length > 0 && (
                  <>
                    <h4>What you would do</h4>
                    <List items={sheet.responsibilities} />
                  </>
                )}
              </section>
            )}

            <section className="prep-section" aria-labelledby="prep-proven">
              <h3 id="prep-proven">What your resume proves</h3>
              <p className="hint">
                {sheet.resume} · fit {sheet.fit_score}. Be ready to tell the story behind each line.
              </p>
              {sheet.proven.length > 0 ? (
                <ul className="prep-claims">
                  {sheet.proven.map((m) => (
                    <li key={m.requirement}>
                      <span className="prep-ask">{m.requirement}</span>
                      <q className="prep-quote">{m.evidence}</q>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="hint">No requirement was proven from this resume.</p>
              )}
              {sheet.partial.length > 0 && (
                <>
                  <h4>Shown only in part</h4>
                  <ul className="prep-claims">
                    {sheet.partial.map((m) => (
                      <li key={m.requirement}>
                        <span className="prep-ask">{m.requirement}</span>
                        <q className="prep-quote">{m.evidence}</q>
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </section>

            {sheet.gaps.length > 0 && (
              <section className="prep-section" aria-labelledby="prep-gaps">
                <h3 id="prep-gaps">Not in your resume</h3>
                <p className="hint">They may ask about these. Decide what you will say: the closest thing you have done, or how you would learn it.</p>
                <ul className="prep-claims">
                  {sheet.gaps.map((g) => (
                    <li key={g.requirement}>
                      <span className="prep-ask">{g.requirement}</span>
                      {g.reason && <span className="hint">{g.reason}</span>}
                    </li>
                  ))}
                </ul>
              </section>
            )}

            {sheet.talking_points.length > 0 && (
              <section className="prep-section" aria-labelledby="prep-points">
                <h3 id="prep-points">Worth bringing up</h3>
                <List items={sheet.talking_points} />
              </section>
            )}

            <section className="prep-section" aria-labelledby="prep-company">
              <h3 id="prep-company">The company</h3>
              {research ? (
                <>
                  {research.what_they_do && <p>{research.what_they_do}</p>}
                  {research.size_and_stage && <p className="hint">{research.size_and_stage}</p>}
                  {research.products.length > 0 && (
                    <>
                      <h4>Products</h4>
                      <List items={research.products} />
                    </>
                  )}
                  {research.recent_news.length > 0 && (
                    <>
                      <h4>Recent news</h4>
                      <List items={research.recent_news} />
                    </>
                  )}
                  {research.culture_and_values.length > 0 && (
                    <>
                      <h4>Culture and values</h4>
                      <List items={research.culture_and_values} />
                    </>
                  )}
                  {research.sources.length > 0 && (
                    <>
                      <h4>Sources</h4>
                      <ul className="plain-list">
                        {research.sources.map((s) => (
                          <li key={s}>
                            <a href={s}>{s.replace(/^https?:\/\/(www\.)?/, "")}</a>
                          </li>
                        ))}
                      </ul>
                    </>
                  )}
                </>
              ) : (
                <p className="hint">No reliable research was found for this employer. Look it up before the interview.</p>
              )}
            </section>

            {sheet.cover_note && (
              <section className="prep-section" aria-labelledby="prep-cover">
                <h3 id="prep-cover">The cover note you approved</h3>
                <p className="note-text">{sheet.cover_note}</p>
              </section>
            )}

            {sheet.notes && (
              <section className="prep-section" aria-labelledby="prep-notes">
                <h3 id="prep-notes">Your notes</h3>
                <p className="note-text">{sheet.notes}</p>
              </section>
            )}

            <section className="prep-section" aria-labelledby="prep-description">
              <h3 id="prep-description">The job description</h3>
              {sheet.description ? (
                <p className="note-text posting-body">{sheet.description}</p>
              ) : (
                <p className="hint">Not saved for this job. Its details offer one more try to fetch it.</p>
              )}
            </section>
          </>
        )}
      </div>
    </dialog>
  );
}
