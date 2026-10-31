// 1.0.1: Langfuse's address and keys, shown when Tracing = Langfuse. Before
// this the installed app had no way to get the keys (they were only in the
// developer's .env), so Evals said "not reachable" although Langfuse ran.
// The secret key is write-only, like the Claude key.

import { useState } from "react";
import { errorMessage, getApi } from "../bridge/bridge";
import type { LlmStatus, Settings } from "../bridge/types";

interface Props {
  settings: Settings;
  onSettings(settings: Settings): void;
}

export function LangfuseFields({ settings, onSettings }: Props) {
  const [host, setHost] = useState(String(settings.LANGFUSE_HOST || "http://localhost:3000"));
  const [publicKey, setPublicKey] = useState(String(settings.LANGFUSE_PUBLIC_KEY ?? ""));
  const [secret, setSecret] = useState("");
  const [state, setState] = useState<"idle" | "saving" | "testing">("idle");
  const [result, setResult] = useState<LlmStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  const dirty = host.trim() !== String(settings.LANGFUSE_HOST || "http://localhost:3000") ||
    publicKey.trim() !== String(settings.LANGFUSE_PUBLIC_KEY ?? "") || secret.trim() !== "";

  const test = async () => {
    setState("testing");
    setError(null);
    try {
      setResult(await (await getApi()).test_langfuse(host.trim(), publicKey.trim(), secret.trim() || null));
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setState("idle");
    }
  };

  const save = async () => {
    setState("saving");
    setError(null);
    try {
      const api = await getApi();
      let next = await api.save_settings({ LANGFUSE_HOST: host.trim(), LANGFUSE_PUBLIC_KEY: publicKey.trim() });
      if (secret.trim()) next = await api.set_langfuse_secret(secret.trim());
      setSecret("");
      onSettings(next);
      setState("idle");
      await test(); // say at once whether it works
    } catch (e) {
      setError(errorMessage(e));
      setState("idle");
    }
  };

  return (
    <div className="langfuse-fields">
      <label className="field">
        <span>Langfuse address</span>
        <input className="input" type="url" value={host} onChange={(e) => setHost(e.target.value)} spellCheck={false} />
      </label>
      <div className="notes-row">
        <label className="field">
          <span>Public key</span>
          <input className="input" value={publicKey} placeholder="pk-lf-…" onChange={(e) => setPublicKey(e.target.value)} spellCheck={false} autoComplete="off" />
        </label>
        <label className="field">
          <span>Secret key</span>
          <input
            className="input"
            type="password"
            value={secret}
            placeholder={settings.LANGFUSE_SECRET_KEY_SET ? "Saved (type to replace)" : "sk-lf-…"}
            onChange={(e) => setSecret(e.target.value)}
            autoComplete="off"
          />
        </label>
      </div>
      <p className="hint">From Langfuse → Settings → API Keys. Kept in JobLens' own folder on this PC; the secret key is never shown again.</p>
      <div className="notes-actions">
        <button type="button" className="btn btn-secondary btn-sm" onClick={() => void save()} disabled={!dirty || state !== "idle"}>
          {state === "saving" ? "Saving…" : "Save keys"}
        </button>
        <button type="button" className="btn btn-ghost btn-sm" onClick={() => void test()} disabled={state !== "idle"}>
          {state === "testing" ? "Testing…" : "Test"}
        </button>
      </div>
      {result && (
        <p className={result.ok ? "check-status ok" : "check-status bad"} role="status">
          <span aria-hidden="true">{result.ok ? "✓" : "✕"}</span> {result.message}
        </p>
      )}
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
