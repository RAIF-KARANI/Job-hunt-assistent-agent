// "Run the AI on this PC": check the hardware, suggest a model that fits,
// install Ollama and download the model. Ported from the Qt wizard's
// LocalPage; installs and downloads stream progress from Python.

import { useCallback, useEffect, useState } from "react";
import { errorMessage, getApi } from "../bridge/bridge";
import type { OllamaStatus, SystemCheck, Verdict } from "../bridge/types";
import { useSetupProgress } from "./useSetupProgress";

/** Ollama treats "llama3.2" and "llama3.2:latest" as the same model. */
const canonical = (name: string) => (name.includes(":") ? name : `${name}:latest`);
export const hasModel = (name: string, models: string[]) => models.some((m) => canonical(m) === canonical(name));

const VERDICT: Record<Verdict, { label: string; tone: string }> = {
  fast: { label: "Fast", tone: "ok" },
  slower: { label: "Slower", tone: "warn" },
  "too big": { label: "Too big", tone: "danger" },
  "no disk space": { label: "No disk space", tone: "danger" },
};

interface Props {
  model: string | null;
  onModel(name: string): void;
  onReady(ready: boolean): void;
}

export function LocalModelSetup({ model, onModel, onReady }: Props) {
  const [check, setCheck] = useState<SystemCheck | null>(null);
  const [ollama, setOllama] = useState<OllamaStatus | null>(null);
  const [before, setBefore] = useState<OllamaStatus | null>(null); // what was here at the first look
  const [installing, setInstalling] = useState(false);
  const [pulling, setPulling] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [manual, setManual] = useState(false);
  const install = useSetupProgress("install");
  const pull = useSetupProgress("pull");

  const refresh = useCallback(async () => {
    try {
      const status = await (await getApi()).ollama_status();
      setOllama(status);
      setBefore((b) => b ?? status);
    } catch (e) {
      setError(errorMessage(e));
    }
  }, []);

  useEffect(() => {
    void refresh();
    getApi()
      .then((api) => api.system_check("ollama", null))
      .then((c) => {
        setCheck(c);
        const pick = c.advice.find((a) => a.recommended);
        if (pick && !model) onModel(pick.name);
      })
      .catch((e) => setError(`Couldn't check this PC: ${errorMessage(e)}`));
    // Once, when the step opens (not again when the model choice changes).
  }, []);

  const have = Boolean(model && ollama && hasModel(model, ollama.models));
  const ready = Boolean(ollama?.running && have);
  useEffect(() => onReady(ready), [ready, onReady]);

  const doInstall = async () => {
    setInstalling(true);
    setError(null);
    install.reset();
    try {
      const result = await (await getApi()).install_ollama();
      if (result.manual) setManual(true);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      await refresh(); // first, so the page never shows "not installed" in between
      setInstalling(false);
    }
  };

  const doPull = async () => {
    if (!model) return;
    setPulling(true);
    setError(null);
    pull.reset();
    try {
      await (await getApi()).pull_model(model);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      await refresh(); // first, so the page never shows "not downloaded" in between
      setPulling(false);
    }
  };

  const fraction = pull.latest?.fraction ?? null;
  const alreadyHad = Boolean(model && before && hasModel(model, before.models));

  return (
    <div className="local-setup">
      <p className="pc-summary" role="status">
        {check ? check.summary : "Checking this PC…"}
      </p>

      {check && (
        <fieldset className="model-choices">
          <legend className="sr-only">Model</legend>
          {check.advice.map((a) => {
            const usable = a.verdict === "fast" || a.verdict === "slower";
            const onPc = ollama ? hasModel(a.name, ollama.models) : false;
            return (
              <label key={a.name} className={["model-choice", model === a.name && "selected", !usable && "disabled"].filter(Boolean).join(" ")}>
                <input type="radio" name="local-model" value={a.name} checked={model === a.name} disabled={!usable || pulling} onChange={() => onModel(a.name)} />
                <span className="model-head">
                  <span className="mono">{a.name}</span>
                  <span className={`verdict verdict-${VERDICT[a.verdict].tone}`}>{VERDICT[a.verdict].label}</span>
                  {a.recommended && <span className="badge">Recommended</span>}
                  {ollama && <span className="model-size">{onPc ? "already on this PC" : `${a.download_gb.toFixed(1)} GB download`}</span>}
                </span>
                <span className="model-text">
                  {a.description}. <span className="hint">{a.reason.charAt(0).toUpperCase() + a.reason.slice(1)}.</span>
                </span>
              </label>
            );
          })}
        </fieldset>
      )}

      <div className="setup-row">
        <span className={`dot-status ${ollama?.running ? "ok" : ollama?.installed ? "warn" : "off"}`} aria-hidden="true" />
        <span className="setup-row-text">
          {!ollama
            ? "Looking for Ollama…"
            : ollama.running
              ? before?.installed
                ? "Ollama is installed and running. Nothing to install."
                : "Ollama installed and running."
              : ollama.installed
                ? "Ollama is installed but didn't start. Open the Ollama app, then check again."
                : manual
                  ? "Install Ollama from the page that opened in your browser, then check again."
                  : "Ollama isn't installed yet. It runs the AI model on this PC (free)."}
        </span>
        {ollama && !ollama.running && (
          <button type="button" className="btn btn-secondary" disabled={installing} onClick={() => (ollama.installed || manual ? void refresh() : void doInstall())}>
            {installing ? "Installing…" : ollama.installed || manual ? "Check again" : "Install Ollama"}
          </button>
        )}
      </div>
      {(installing || install.lines.length > 0) && (
        <pre className="setup-log" aria-live="polite">
          {install.lines.join("\n") || "Starting winget…"}
        </pre>
      )}

      {ollama?.running && model && (
        <div className="setup-row">
          <span className={`dot-status ${have ? "ok" : "off"}`} aria-hidden="true" />
          <span className="setup-row-text">
            {have
              ? alreadyHad
                ? `${model} is already on this PC. No download needed.`
                : `${model} downloaded.`
              : pulling
                ? (pull.latest?.message ?? "Starting the download…")
                : `${model} isn't downloaded yet.`}
          </span>
          {!have && (
            <button type="button" className="btn btn-primary" disabled={pulling} onClick={() => void doPull()}>
              {pulling ? "Downloading…" : `Download ${model}`}
            </button>
          )}
        </div>
      )}
      {pulling && (
        <div className="progress" role="progressbar" aria-label={`Downloading ${model}`} aria-valuemin={0} aria-valuemax={100} aria-valuenow={fraction === null ? undefined : Math.round(fraction * 100)}>
          <span className={fraction === null ? "progress-fill indeterminate" : "progress-fill"} style={fraction === null ? undefined : { width: `${fraction * 100}%` }} />
        </div>
      )}

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
