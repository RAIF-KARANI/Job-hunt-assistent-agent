// Resume tailoring (19d, E7): your AI model suggests edits to your own
// resume lines for this job; code drops any that add a number, skill or name
// your resume doesn't show. What's left is shown before -> after, to copy.

import { useState } from "react";
import { copy } from "../app/clipboard";
import { errorMessage, getApi } from "../bridge/bridge";
import type { TailoringResult } from "../bridge/types";

const plural = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;

export function TailorSection({ jobId }: { jobId: number }) {
  const [state, setState] = useState<"idle" | "working" | "done">("idle");
  const [result, setResult] = useState<TailoringResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState<number | "all" | null>(null);

  const run = async () => {
    setState("working");
    setError(null);
    setCopied(null);
    try {
      setResult(await (await getApi()).tailor_resume(jobId));
      setState("done");
    } catch (e) {
      setError(errorMessage(e));
      setState(result ? "done" : "idle");
    }
  };

  const copyText = (text: string, which: number | "all") => void copy(text).then(() => setCopied(which));
  const edits = result?.edits ?? [];
  const dropped = result?.dropped ?? [];

  return (
    <section className="tailor" aria-labelledby="tailor-title">
      <div className="section-head">
        <h3 id="tailor-title">Suggested edits</h3>
        <button type="button" className={result ? "btn btn-secondary btn-sm" : "btn btn-primary btn-sm"} onClick={() => void run()} disabled={state === "working"}>
          {state === "working" ? "Suggesting…" : result ? "Suggest again" : "Suggest edits"}
        </button>
      </div>
      <p className="hint">
        Your AI model rewrites lines of <strong>your own resume</strong> to show this job's requirements. Before you see them, JobLens drops
        any edit that adds a number, skill or name your resume doesn't have, or leaves one of yours out. It can't catch a claim in ordinary words ("led the team"), so read
        each one. Uses the model in Settings: with a cloud model, your resume text goes to it, as it does for the analysis.
      </p>

      {state === "working" && (
        <p className="hint" role="status">
          Asking the model… this takes about a minute on this PC.
        </p>
      )}
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}

      {result && state !== "working" && (
        <div role="status" aria-live="polite">
          <p className="tailor-summary">
            {edits.length ? plural(edits.length, "edit") : "No edits passed the check"} for <strong>{result.resume}</strong>
            {dropped.length > 0 && <span className="hint"> · {plural(dropped.length, "suggestion")} dropped</span>}
            <span className="hint"> · {Math.round(result.seconds)} s</span>
          </p>

          {edits.length > 0 && (
            <ol className="tailor-edits">
              {edits.map((e, i) => (
                <li key={`${i}-${e.before}`} className="tailor-edit">
                  <span className="tailor-req">{e.requirement}</span>
                  <p className="tailor-before">
                    <span className="sr-only">Before: </span>
                    {e.before}
                  </p>
                  <p className="tailor-after">
                    <span className="sr-only">After: </span>
                    {e.after}
                  </p>
                  <div className="tailor-foot">
                    <span className="hint">{e.why}</span>
                    <button type="button" className="btn btn-ghost btn-sm" onClick={() => copyText(e.after, i)}>
                      {copied === i ? "Copied" : "Copy"}
                    </button>
                  </div>
                </li>
              ))}
            </ol>
          )}
          {edits.length > 1 && (
            <button type="button" className="btn btn-secondary btn-sm" onClick={() => copyText(edits.map((e) => e.after).join("\n"), "all")}>
              {copied === "all" ? "Copied" : "Copy all"}
            </button>
          )}

          {dropped.length > 0 && (
            <details className="tailor-dropped">
              <summary>Why {plural(dropped.length, "suggestion was", "suggestions were")} dropped</summary>
              <ul className="plain-list">
                {dropped.map((d, i) => (
                  <li key={`${i}-${d.after}`}>
                    <span className="tailor-after">{d.after}</span>
                    <span className="hint"> · {d.reasons.join("; ")}</span>
                  </li>
                ))}
              </ul>
            </details>
          )}
        </div>
      )}
    </section>
  );
}
