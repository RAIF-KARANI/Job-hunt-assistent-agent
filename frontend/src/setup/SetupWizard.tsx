// First-run Setup wizard (12g), ported from the Qt wizard plus the new
// "Look and feel" step (D14):
//   Welcome -> where the AI runs -> (this PC | Claude API) -> resumes
//           -> look and feel -> done
// Nothing is saved until Finish, like the Qt wizard (resumes you add and
// models you download stay, of course).

import { useCallback, useEffect, useState } from "react";
import { errorMessage, getApi } from "../bridge/bridge";
import type { LlmStatus, Settings, Ui3D } from "../bridge/types";
import { advise, LevelPicker } from "../settings/LevelPicker";
import { LocalModelSetup } from "../settings/LocalModelSetup";
import { ModelPicker } from "../settings/ModelPicker";
import { ResumeList } from "../settings/ResumeList";

type Step = "welcome" | "choice" | "local" | "api" | "resumes" | "look" | "done";
const ORDER: Step[] = ["welcome", "choice", "local", "resumes", "look", "done"];
const TITLES: Record<Step, string> = {
  welcome: "Welcome to JobLens",
  choice: "Where should the AI run?",
  local: "Run the AI on this PC",
  api: "Use the Claude API",
  resumes: "Add your resumes",
  look: "Look and feel",
  done: "All set",
};
const API_MODEL = "claude-haiku-5-5";

interface Props {
  onFinish(settings: Settings): void;
  onSkip(): void;
}

export function SetupWizard({ onFinish, onSkip }: Props) {
  const [step, setStep] = useState<Step>("welcome");
  const [useLocal, setUseLocal] = useState(true);
  const [localModel, setLocalModel] = useState<string | null>(null);
  const [localReady, setLocalReady] = useState(false);
  const [key, setKey] = useState("");
  const [apiModel, setApiModel] = useState(API_MODEL);
  const [keyCheck, setKeyCheck] = useState<LlmStatus | "checking" | null>(null);
  const [resumes, setResumes] = useState(0);
  const [level, setLevel] = useState<Ui3D | null>(null);
  const [levelAdvice, setLevelAdvice] = useState<{ level: Ui3D; reason: string } | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const provider = useLocal ? "ollama" : "anthropic";
  const model = useLocal ? localModel : apiModel.trim();
  const path: Step[] = ORDER.map((s) => (s === "local" && !useLocal ? "api" : s));
  const index = path.indexOf(step);

  // Look and feel: ask Python which level suits this PC with the chosen model.
  useEffect(() => {
    if (step !== "look") return;
    setLevelAdvice(null);
    getApi()
      .then((api) => api.system_check(provider, model))
      .then((c) => {
        const advice = advise(c.ui3d);
        setLevelAdvice(advice);
        setLevel((l) => l ?? advice?.level ?? "still");
      })
      .catch(() => setLevel((l) => l ?? "still"));
  }, [step, provider, model]);

  // Move focus to the new step's heading (keyboard and screen reader users).
  useEffect(() => {
    document.getElementById("wizard-title")?.focus();
  }, [step]);

  const canGoOn =
    step === "local" ? localReady : step === "api" ? key.trim() !== "" && apiModel.trim() !== "" : step === "resumes" ? resumes > 0 : step === "look" ? level !== null : true;

  const testKey = async () => {
    setKeyCheck("checking");
    try {
      setKeyCheck(await (await getApi()).test_api_key(key.trim(), apiModel.trim()));
    } catch (e) {
      setKeyCheck({ ok: false, message: errorMessage(e) });
    }
  };

  const finish = async () => {
    setSaving(true);
    setError(null);
    try {
      const api = await getApi();
      let next = await api.save_settings({ LLM_PROVIDER: provider, LLM_MODEL: model ?? "", UI_3D: level ?? "still" });
      if (!useLocal) next = await api.set_api_key(key.trim());
      next = await api.save_settings({ SETUP_DONE: "true" });
      onFinish(next);
    } catch (e) {
      setError(errorMessage(e));
      setSaving(false);
    }
  };

  const onResumeCount = useCallback((n: number) => setResumes(n), []);

  return (
    <div className="wizard-backdrop">
      <main className="wizard" aria-labelledby="wizard-title">
        <ol className="wizard-steps" aria-label="Setup steps">
          {path.map((s, i) => (
            <li key={s} className={i < index ? "done" : i === index ? "current" : undefined} aria-current={i === index ? "step" : undefined}>
              <span className="sr-only">{i < index ? "Done: " : i === index ? "Current: " : ""}</span>
              {TITLES[s]}
            </li>
          ))}
        </ol>

        <h1 id="wizard-title" tabIndex={-1}>
          {TITLES[step]}
        </h1>

        <div className="wizard-body">
          {step === "welcome" && (
            <>
              <p>
                JobLens reads a job posting, compares it with your resumes, researches the company and drafts a cover note that you approve before anything is
                saved.
              </p>
              <p className="hint">Setup takes a few minutes: choose where the AI runs, add your resumes, pick how the app looks. Your files stay on this PC.</p>
            </>
          )}

          {step === "choice" && (
            <div className="choice-cards" role="radiogroup" aria-label="Where the AI runs">
              <label className={useLocal ? "choice selected" : "choice"}>
                <input type="radio" name="where" checked={useLocal} onChange={() => setUseLocal(true)} />
                <span className="choice-title">On this PC with Ollama</span>
                <span className="choice-text">Free and private: nothing leaves your computer. Needs about 8–16 GB of RAM; the next step checks your PC.</span>
              </label>
              <label className={!useLocal ? "choice selected" : "choice"}>
                <input type="radio" name="where" checked={!useLocal} onChange={() => setUseLocal(false)} />
                <span className="choice-title">Claude API</span>
                <span className="choice-text">Fast on any PC. Needs an API key (about $0.01 per job with Claude Haiku). Job text and your resume are sent to Anthropic.</span>
              </label>
            </div>
          )}

          {step === "local" && <LocalModelSetup model={localModel} onModel={setLocalModel} onReady={setLocalReady} />}

          {step === "api" && (
            <div className="settings-form">
              <label className="field">
                <span>API key</span>
                <input className="input mono" type="password" value={key} onChange={(e) => setKey(e.target.value)} placeholder="sk-ant-…" autoComplete="off" spellCheck={false} />
                <span className="hint">
                  Create one at <a href="https://console.anthropic.com/settings/keys">console.anthropic.com</a> (Settings → API keys) and paste it here.
                </span>
              </label>
              <div className="field">
                <span>Model</span>
                <ModelPicker cloud value={apiModel} installed={null} onChange={setApiModel} />
              </div>
              <div className="row-actions">
                <button type="button" className="btn btn-secondary" disabled={!key.trim() || keyCheck === "checking"} onClick={() => void testKey()}>
                  {keyCheck === "checking" ? "Testing…" : "Test key"}
                </button>
                {keyCheck && keyCheck !== "checking" && (
                  <span className={keyCheck.ok ? "check-status ok" : "check-status bad"} role="status">
                    <span aria-hidden="true">{keyCheck.ok ? "✓" : "✕"}</span> {keyCheck.message}
                  </span>
                )}
              </div>
            </div>
          )}

          {step === "resumes" && (
            <>
              <p className="hint">Add one or more PDF resumes. For each job, JobLens picks the one that fits best.</p>
              <ResumeList onCount={onResumeCount} />
            </>
          )}

          {step === "look" && (
            <>
              <p className="hint">
                The Dashboard shows your jobs as a 3D galaxy. 3D shares the graphics card with {useLocal ? "the AI model" : "nothing else here"}, so pick what
                suits this PC. You can change it any time in Settings.
              </p>
              {level === null ? <p className="hint">Checking this PC…</p> : <LevelPicker value={level} onChange={setLevel} recommended={levelAdvice} name="wizard-3d" />}
            </>
          )}

          {step === "done" && (
            <>
              <p>
                JobLens will run the AI {useLocal ? <>on this PC with <strong className="mono">{model}</strong></> : <>with Claude (<strong className="mono">{model}</strong>)</>}, compare jobs
                with {resumes} {resumes === 1 ? "resume" : "resumes"}, and show the Dashboard {level === "off" ? "as a flat map" : level === "still" ? "in still 3D" : "in animated 3D"}.
              </p>
              <p className="hint">Click Finish, then paste a job link on the Analyze screen. Everything can be changed later in Settings.</p>
            </>
          )}
        </div>

        {error && (
          <p className="notice notice-danger" role="alert">
            {error}
          </p>
        )}

        <footer className="wizard-nav">
          {step === "welcome" ? (
            <button type="button" className="btn btn-ghost" onClick={onSkip}>
              Skip for now
            </button>
          ) : (
            <button type="button" className="btn btn-ghost" onClick={() => setStep(path[index - 1])} disabled={saving}>
              Back
            </button>
          )}
          <span className="wizard-count hint">
            Step {index + 1} of {path.length}
          </span>
          {step === "done" ? (
            <button type="button" className="btn btn-primary" onClick={() => void finish()} disabled={saving}>
              {saving ? "Saving…" : "Finish"}
            </button>
          ) : (
            <button type="button" className="btn btn-primary" onClick={() => setStep(path[index + 1])} disabled={!canGoOn}>
              {step === "welcome" ? "Start" : "Next"}
            </button>
          )}
        </footer>
        {!canGoOn && step === "local" && <p className="hint wizard-why">Next unlocks when Ollama is running and the model is on this PC.</p>}
        {!canGoOn && step === "resumes" && <p className="hint wizard-why">Add at least one resume to go on.</p>}
      </main>
    </div>
  );
}
