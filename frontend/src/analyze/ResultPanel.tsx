// The run ended: what happened, then "How did JobLens do?" (Phase 11c).
// Your ratings are the one thing automatic checks can't measure; they're
// saved on this PC and feed the Evals screen.

import { useEffect, useState, type FormEvent } from "react";
import { errorMessage, getApi } from "../bridge/bridge";
import type { FeedbackOptions, FinishedEvent } from "../bridge/types";
import { ResumePrompt } from "../resume/ResumePrompt";

const ASPECTS = [
  { id: "fit_score", label: "The fit score was" },
  { id: "cover_note", label: "The cover note was" },
] as const;

interface Props {
  result: FinishedEvent;
  onAnother(): void;
}

export function ResultPanel({ result, onAnother }: Props) {
  const saved = result.decision === "approve" && result.saved_path;
  const [promptOpen, setPromptOpen] = useState(false); // 14g: only when you ask
  return (
    <section className="card review" aria-labelledby="result-title">
      <header className="panel-head">
        <h2 id="result-title" className={saved ? "ok-ink" : undefined}>
          {saved ? "Approved and saved" : result.decision === "reject" ? "Rejected" : "Done"}
        </h2>
      </header>
      {saved ? (
        <p className="lead">
          The cover note is in your tracker and the job's status is now <strong>cover note ready</strong>.
          <span className="path">{result.saved_path}</span>
        </p>
      ) : (
        <p className="lead">Nothing was saved. The job and its analysis are still in your tracker.</p>
      )}
      <div className="actions">
        <a className="btn btn-secondary" href="#/tracker">
          Open the Tracker
        </a>
        {result.job_id !== null && (
          <button type="button" className="btn btn-secondary" onClick={() => setPromptOpen(true)}>
            Generate resume prompt
          </button>
        )}
        <button type="button" className="btn btn-ghost" onClick={onAnother}>
          Analyze another job
        </button>
      </div>
      {promptOpen && result.job_id !== null && <ResumePrompt jobId={result.job_id} onClose={() => setPromptOpen(false)} />}
      {result.decision && <Feedback result={result} />}
    </section>
  );
}

function Feedback({ result }: { result: FinishedEvent }) {
  const [options, setOptions] = useState<FeedbackOptions | null>(null);
  const [ratings, setRatings] = useState<Record<string, string>>({ cover_note: result.suggested_rating ?? "" });
  const [comment, setComment] = useState("");
  const [state, setState] = useState<"open" | "saving" | "saved" | "skipped">("open");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getApi()
      .then((api) => api.feedback_options())
      .then(setOptions)
      .catch((e) => setError(errorMessage(e)));
  }, []);

  if (state === "skipped") return null;
  if (state === "saved") {
    return (
      <p className="feedback-done" role="status">
        Thanks, your rating is saved. It shows on the Evals screen.
      </p>
    );
  }

  const save = async (e: FormEvent) => {
    e.preventDefault();
    setState("saving");
    setError(null);
    try {
      const api = await getApi();
      await api.save_feedback(result.run_id, result.job_id, ratings, comment.trim());
      setState("saved");
    } catch (err) {
      setError(errorMessage(err));
      setState("open");
    }
  };

  return (
    <form className="feedback" onSubmit={save} aria-labelledby="feedback-title">
      <h3 id="feedback-title">How did JobLens do?</h3>
      <p className="hint">Saved on this PC only. The cover note rating is pre-filled from what you did.</p>
      {options &&
        ASPECTS.map((aspect) => (
          <fieldset key={aspect.id} className="segmented-row">
            <legend>{aspect.label}</legend>
            <div className="segmented">
              {options[aspect.id].map((option) => (
                <label key={option} className="segment">
                  <input
                    type="radio"
                    name={aspect.id}
                    value={option}
                    checked={ratings[aspect.id] === option}
                    onChange={() => setRatings({ ...ratings, [aspect.id]: option })}
                  />
                  <span>{option}</span>
                </label>
              ))}
            </div>
          </fieldset>
        ))}
      <div className="field">
        <label htmlFor="fb-comment">Comment (optional)</label>
        <input
          id="fb-comment"
          className="input"
          type="text"
          placeholder="e.g. it missed my Kubernetes experience"
          value={comment}
          onChange={(e) => setComment(e.target.value)}
        />
      </div>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      <div className="actions">
        <button type="submit" className="btn btn-secondary" disabled={state === "saving" || !Object.values(ratings).some(Boolean)}>
          {state === "saving" ? "Saving..." : "Save rating"}
        </button>
        <button type="button" className="btn btn-ghost" onClick={() => setState("skipped")}>
          Skip
        </button>
      </div>
    </form>
  );
}
