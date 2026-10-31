// 14f: the quick-analyze shortcut. "Change", then press the new keys; Python
// checks them (Ctrl or Alt + a letter, digit or F-key) and registers them.

import { useEffect, useState, type KeyboardEvent } from "react";
import { errorMessage, getApi } from "../bridge/bridge";
import type { QuickKeyStatus } from "../bridge/types";

interface Props {
  saved: string; // the QUICK_KEY setting
  onSave(value: string): Promise<void>;
}

/** A key press -> "Ctrl+Alt+J", or null while only modifiers are down. */
export function comboOf(e: Pick<KeyboardEvent, "ctrlKey" | "altKey" | "shiftKey" | "metaKey" | "key">): string | null {
  const key = e.key.length === 1 ? e.key.toUpperCase() : /^F([1-9]|1[0-2])$/.test(e.key) ? e.key : null;
  if (!key) return null;
  return [e.ctrlKey && "Ctrl", e.altKey && "Alt", e.shiftKey && "Shift", e.metaKey && "Win", key].filter(Boolean).join("+");
}

export function ShortcutField({ saved, onSave }: Props) {
  const [status, setStatus] = useState<QuickKeyStatus | null>(null);
  const [listening, setListening] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = () =>
    getApi()
      .then((api) => api.quick_key_status())
      .then(setStatus)
      .catch(() => setStatus(null));

  useEffect(() => {
    // The listener re-registers on its own thread: ask again a moment after a change.
    const timer = window.setTimeout(() => void refresh(), 400);
    return () => window.clearTimeout(timer);
  }, [saved]);

  const save = async (value: string) => {
    setError(null);
    try {
      await onSave(value);
    } catch (e) {
      setError(errorMessage(e));
    }
  };

  const onKeyDown = (e: KeyboardEvent<HTMLButtonElement>) => {
    if (!listening) return;
    e.preventDefault();
    if (e.key === "Escape") return setListening(false);
    const combo = comboOf(e);
    if (!combo) return; // only Ctrl/Alt so far: wait for the key
    setListening(false);
    void save(combo);
  };

  const off = saved.toLowerCase() === "off";
  return (
    <div className="shortcut">
      <div className="shortcut-row">
        <button
          type="button"
          className={listening ? "input shortcut-key listening" : "input shortcut-key"}
          onClick={() => setListening(true)}
          onKeyDown={onKeyDown}
          onBlur={() => setListening(false)}
          aria-label={listening ? "Press the new shortcut" : `Shortcut: ${off ? "off" : saved}. Click to change`}
        >
          {listening ? "Press the keys…" : off ? "Off" : saved}
        </button>
        {!off && (
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => void save("off")}>
            Turn off
          </button>
        )}
        {off && (
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => void save("Ctrl+Alt+J")}>
            Use Ctrl+Alt+J
          </button>
        )}
      </div>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {!error && status?.error && !off && (
        <p className="hint warn-ink" role="status">
          {status.error}
        </p>
      )}
    </div>
  );
}
