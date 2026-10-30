// The page couldn't be read (login wall, JavaScript-only site): the agent
// paused and asks for the job text instead. You are the fallback tool.

import { useState, type FormEvent } from "react";
import type { PastePayload } from "../bridge/types";
import { WarnIcon } from "./ReviewPanel";

const MIN_CHARS = 200; // less than this is not a job description

interface Props {
  payload: PastePayload;
  busy: boolean;
  onPaste(text: string): void;
  onStop(): void;
}

export function PastePanel({ payload, busy, onPaste, onStop }: Props) {
  const [text, setText] = useState("");
  const short = text.trim().length < MIN_CHARS;

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!short && !busy) onPaste(text.trim());
  };

  return (
    <form className="card review" aria-labelledby="paste-title" onSubmit={submit}>
      <header className="panel-head">
        <h2 id="paste-title">Paste the job description</h2>
      </header>
      <div className="notice notice-warn" role="status">
        <WarnIcon />
        <span>
          I couldn't read that page <span className="notice-reason">({payload.reason})</span>. Open it in your browser, copy the job
          description, and paste it below.
        </span>
      </div>
      <div className="field">
        <label htmlFor="paste">Job description</label>
        <textarea
          id="paste"
          className="input note"
          rows={14}
          value={text}
          onChange={(e) => setText(e.target.value)}
          disabled={busy}
          placeholder="Title, company, requirements, responsibilities..."
        />
        <span className="hint">{short ? `Paste at least ${MIN_CHARS} characters (${text.trim().length} so far).` : `${text.trim().length} characters`}</span>
      </div>
      <div className="actions">
        <button type="submit" className="btn btn-primary" disabled={busy || short}>
          {busy ? "Reading..." : "Continue with this text"}
        </button>
        <button type="button" className="btn btn-ghost push" disabled={busy} onClick={onStop}>
          Stop
        </button>
      </div>
    </form>
  );
}
