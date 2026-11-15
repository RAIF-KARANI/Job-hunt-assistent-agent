// 16c: the model for OpenAI or Gemini. No names are built in: they change
// every few months. "Find my models" asks the provider which models your
// key can use (which also checks the key), and you pick one of those.

import { useState } from "react";
import { errorMessage, getApi } from "../bridge/bridge";

interface Props {
  provider: string;
  /** The provider's name as people know it ("OpenAI", "Gemini"). */
  label: string;
  value: string;
  /** A key typed into the form but not saved yet; "" = use the saved one. */
  typedKey: string;
  /** Is a key saved for this provider? */
  keySaved: boolean;
  onChange(model: string): void;
}

export function CloudModelPicker({ provider, label, value, typedKey, keySaved, onChange }: Props) {
  const [models, setModels] = useState<string[] | null>(null);
  const [finding, setFinding] = useState(false);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);
  const canFind = keySaved || typedKey.trim() !== "";

  const find = async () => {
    setFinding(true);
    setMessage(null);
    try {
      const answer = await (await getApi()).list_models(provider, typedKey.trim() || null);
      setMessage({ ok: answer.ok, text: answer.message });
      if (answer.ok) {
        setModels(answer.models);
        if (!answer.models.includes(value)) onChange(""); // a name from before: choose again
      }
    } catch (e) {
      setMessage({ ok: false, text: errorMessage(e) });
    } finally {
      setFinding(false);
    }
  };

  return (
    <>
      {models ? (
        <select className="input mono" aria-label="Model" value={value} onChange={(e) => onChange(e.target.value)}>
          <option value="">Choose a model…</option>
          {models.map((m) => (
            <option key={m} value={m}>
              {m}
            </option>
          ))}
        </select>
      ) : (
        <input
          className="input mono"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={`Find your models below, or type a ${label} model name`}
          spellCheck={false}
          aria-label="Model"
        />
      )}
      <span className="row-actions">
        <button type="button" className="btn btn-secondary btn-sm" disabled={!canFind || finding} onClick={() => void find()}>
          {finding ? "Asking…" : models ? "Refresh the list" : "Find my models"}
        </button>
        {!canFind && <span className="hint">Paste your API key first.</span>}
        {models && (
          <button type="button" className="link-button" onClick={() => setModels(null)}>
            Type a name instead
          </button>
        )}
      </span>
      {message && (
        <span className={message.ok ? "check-status ok" : "check-status bad"} role="status">
          <span aria-hidden="true">{message.ok ? "✓" : "✕"}</span> {message.text}
        </span>
      )}
      <span className="hint">
        The list comes from {label}, for your key. Smaller models are cheaper and faster; JobLens works with any that can call tools.
      </span>
    </>
  );
}
