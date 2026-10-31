// The model as a dropdown (14a): your installed Ollama models, or the known
// Claude models, plus "Other…" to type a name. A saved model that isn't
// installed is shown as such instead of hiding the problem.

import { useState } from "react";
import { hasModel } from "./LocalModelSetup";

export const CLAUDE_MODELS = [
  { id: "claude-haiku-5-5", label: "Claude Haiku 5.5: fast, about $0.01 per job" },
  { id: "claude-sonnet-5-5", label: "Claude Sonnet 5.5: better answers, costs more" },
  { id: "claude-opus-5-5", label: "Claude Opus 5.5: the best, the most expensive" },
];

const OTHER = "__other__";

/** Embedding models can't chat (e.g. qwen3-embedding): not choices for the agent. */
const chatModels = (installed: string[]) => installed.filter((m) => !/embed/i.test(m));

interface Props {
  cloud: boolean;
  value: string;
  /** Installed Ollama models; null = Ollama didn't answer (can't list them). */
  installed: string[] | null;
  onChange(model: string): void;
}

export function ModelPicker({ cloud, value, installed, onChange }: Props) {
  const choices = cloud ? CLAUDE_MODELS.map((m) => ({ id: m.id, label: m.label })) : chatModels(installed ?? []).map((m) => ({ id: m, label: m }));
  const known = cloud ? choices.find((c) => c.id === value) : choices.find((c) => hasModel(value, [c.id]));
  const [typing, setTyping] = useState(false);

  // Ollama isn't running: nothing to list, so type the name.
  if (!cloud && installed === null) {
    return (
      <>
        <input className="input mono" value={value} onChange={(e) => onChange(e.target.value)} spellCheck={false} aria-label="Model" />
        <span className="hint">Ollama isn't running, so your installed models can't be listed. Start Ollama, or type the model's name.</span>
      </>
    );
  }

  const showInput = typing || (!known && value !== "" && cloud);
  return (
    <>
      <select
        className="input mono"
        aria-label="Model"
        value={showInput ? OTHER : known ? known.id : value}
        onChange={(e) => {
          if (e.target.value === OTHER) {
            setTyping(true);
          } else {
            setTyping(false);
            onChange(e.target.value);
          }
        }}
      >
        {!known && !showInput && value && (
          // Saved but not installed: say so (e.g. a model removed from Ollama).
          <option value={value}>{value} (not installed)</option>
        )}
        {choices.map((c) => (
          <option key={c.id} value={c.id}>
            {c.label}
          </option>
        ))}
        <option value={OTHER}>Other… (type a name)</option>
      </select>
      {showInput && (
        <input className="input mono" value={value} onChange={(e) => onChange(e.target.value)} placeholder={cloud ? "claude-…" : "e.g. qwen3:4b"} spellCheck={false} aria-label="Model name" autoFocus />
      )}
      {!cloud && !known && value && !showInput && (
        <span className="hint warn-ink">
          {value} isn't installed in Ollama. Choose an installed model, or download it with the setup wizard.
        </span>
      )}
      {!cloud && chatModels(installed ?? []).length === 0 && (
        <span className="hint">No models installed yet. The setup wizard downloads one that fits this PC.</span>
      )}
    </>
  );
}
