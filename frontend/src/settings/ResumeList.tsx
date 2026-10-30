// The resumes the agent compares with each job. Adding uses Windows' own
// file dialog and COPIES the PDFs; removing deletes only the app's copy.

import { useCallback, useEffect, useState } from "react";
import { errorMessage, getApi } from "../bridge/bridge";
import type { Resume } from "../bridge/types";

export function ResumeList({ onCount }: { onCount?(count: number): void }) {
  const [resumes, setResumes] = useState<Resume[] | null>(null);
  const [confirm, setConfirm] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const list = await (await getApi()).list_resumes();
      setResumes(list);
      onCount?.(list.length);
    } catch (e) {
      setError(errorMessage(e));
    }
  }, [onCount]);

  useEffect(() => {
    void load();
  }, [load]);

  const add = async () => {
    setBusy(true);
    setError(null);
    try {
      const added = await (await getApi()).add_resumes();
      setMessage(added.length ? `Added ${added.join(", ")}.` : null);
      await load();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  const remove = async (name: string) => {
    setConfirm(null);
    try {
      await (await getApi()).remove_resume(name);
      setMessage(`Removed ${name}. Your original file wasn't touched.`);
      await load();
    } catch (e) {
      setError(errorMessage(e));
    }
  };

  return (
    <div className="resumes">
      {resumes === null ? (
        <p className="hint">Loading…</p>
      ) : resumes.length === 0 ? (
        <p className="resume-empty">No resumes yet. Add at least one PDF: the agent needs something to compare with each job.</p>
      ) : (
        <ul className="resume-list">
          {resumes.map((r) => (
            <li key={r.name} className="resume">
              <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden="true">
                <path d="M4.5 1.8h6l3.7 3.7v10.7H4.5z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
                <path d="M10.3 1.8v3.9h3.9" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
              </svg>
              <span className="resume-name">{r.name}</span>
              <span className="hint">{r.kb} KB</span>
              {confirm === r.name ? (
                <span className="resume-confirm" role="group" aria-label={`Remove ${r.name}?`}>
                  <span className="hint">Remove the app's copy?</span>
                  <button type="button" className="btn btn-danger btn-sm" onClick={() => void remove(r.name)}>
                    Remove
                  </button>
                  <button type="button" className="btn btn-ghost btn-sm" onClick={() => setConfirm(null)}>
                    Keep
                  </button>
                </span>
              ) : (
                <button type="button" className="btn btn-ghost btn-sm" aria-label={`Remove ${r.name}`} onClick={() => setConfirm(r.name)}>
                  Remove
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
      <div className="row-actions">
        <button type="button" className="btn btn-secondary" onClick={() => void add()} disabled={busy}>
          {busy ? "Choosing…" : "Add PDFs…"}
        </button>
        <button type="button" className="btn btn-ghost" onClick={() => void getApi().then((api) => api.open_data_folder())}>
          Open folder
        </button>
      </div>
      {message && (
        <p className="hint" role="status">
          {message}
        </p>
      )}
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      <p className="hint">For each job the agent picks the resume that fits best. Files are copied into JobLens' folder and stay on this PC.</p>
    </div>
  );
}
