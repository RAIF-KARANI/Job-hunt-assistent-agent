// Your own notes about a job (14h): the interview date, who you're talking
// to, and anything else. Saved in the tracker with "Save notes".

import { useState } from "react";
import { errorMessage, getApi } from "../bridge/bridge";
import type { JobNotes } from "../bridge/types";

interface Props {
  jobId: number;
  initial: JobNotes;
  onSaved(notes: JobNotes): void;
}

const clean = (n: JobNotes) => ({ notes: n.notes ?? "", interview_at: n.interview_at ?? "", contact: n.contact ?? "" });

export function NotesSection({ jobId, initial, onSaved }: Props) {
  const [saved, setSaved] = useState(clean(initial));
  const [draft, setDraft] = useState(clean(initial));
  const [state, setState] = useState<"idle" | "saving" | "saved">("idle");
  const [error, setError] = useState<string | null>(null);

  const dirty = draft.notes !== saved.notes || draft.interview_at !== saved.interview_at || draft.contact !== saved.contact;
  const change = (field: keyof JobNotes, value: string) => {
    setDraft((d) => ({ ...d, [field]: value }));
    setState("idle");
  };

  const save = async () => {
    setState("saving");
    setError(null);
    try {
      const result = await (await getApi()).save_notes(jobId, draft);
      setSaved(clean(result));
      setDraft(clean(result));
      setState("saved");
      onSaved(result);
    } catch (e) {
      setError(errorMessage(e));
      setState("idle");
    }
  };

  return (
    <section className="sheet-section notes-section" aria-labelledby="notes-title">
      <div className="section-head">
        <h3 id="notes-title">Your notes</h3>
        {state === "saved" && !dirty && (
          <span className="saved" role="status">
            Saved
          </span>
        )}
      </div>
      <div className="notes-row">
        <label className="field">
          <span>Interview</span>
          <input
            className="input"
            type="datetime-local"
            value={draft.interview_at.length === 10 ? `${draft.interview_at}T09:00` : draft.interview_at}
            onChange={(e) => change("interview_at", e.target.value)}
          />
        </label>
        <label className="field">
          <span>Contact</span>
          <input
            className="input"
            type="text"
            maxLength={300}
            placeholder="Name, email or LinkedIn"
            value={draft.contact}
            onChange={(e) => change("contact", e.target.value)}
          />
        </label>
      </div>
      <label className="field">
        <span>Notes</span>
        <textarea
          className="input"
          rows={4}
          maxLength={5000}
          placeholder="What they asked, what to prepare, salary talk…"
          value={draft.notes}
          onChange={(e) => change("notes", e.target.value)}
        />
      </label>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      <div className="notes-actions">
        <button type="button" className="btn btn-secondary btn-sm" onClick={() => void save()} disabled={!dirty || state === "saving"}>
          {state === "saving" ? "Saving…" : "Save notes"}
        </button>
        {draft.interview_at && (
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => change("interview_at", "")}>
            Clear the date
          </button>
        )}
      </div>
    </section>
  );
}
