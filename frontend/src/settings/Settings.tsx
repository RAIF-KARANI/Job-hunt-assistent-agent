// Settings (12g): the AI model, your resumes, how the app looks, and two
// options. The model card saves with a button (typing a model name
// shouldn't save every letter); everything else saves as you change it.

import { useCallback, useEffect, useState, type FormEvent } from "react";
import { errorMessage, getApi } from "../bridge/bridge";
import type { Autostart, LlmStatus, Settings as SettingsData, SystemCheck, Theme, Ui3D } from "../bridge/types";
import { LevelPicker } from "./LevelPicker";
import { ModelPicker } from "./ModelPicker";
import { ResumeList } from "./ResumeList";
import { ShortcutField } from "./ShortcutField";
import { UpdatesCard } from "./UpdatesCard";

const DEFAULT_MODELS: Record<string, string> = { ollama: "qwen3:8b", anthropic: "claude-haiku-5-5" };
const THEMES: { id: Theme; label: string }[] = [
  { id: "system", label: "Like Windows" },
  { id: "dark", label: "Dark" },
  { id: "light", label: "Light" },
];
const FOLLOW_UP_DAYS = [
  { id: "off", label: "Off" },
  { id: "3", label: "After 3 days" },
  { id: "5", label: "After 5 days" },
  { id: "7", label: "After a week" },
  { id: "14", label: "After 2 weeks" },
];
const FIT_DETAIL = [
  { id: "short", label: "Short" },
  { id: "detailed", label: "Detailed" },
];

interface Props {
  settings: SettingsData;
  theme: Theme;
  onTheme(theme: Theme): void;
  onSettings(settings: SettingsData): void;
}

function Status({ status }: { status: LlmStatus | "checking" | null }) {
  if (!status) return null;
  if (status === "checking") return <p className="check-status" role="status">Checking the connection…</p>;
  return (
    <p className={status.ok ? "check-status ok" : "check-status bad"} role="status">
      <span aria-hidden="true">{status.ok ? "✓" : "✕"}</span> {status.message}
    </p>
  );
}

export function Settings({ settings, theme, onTheme, onSettings }: Props) {
  const [provider, setProvider] = useState(settings.LLM_PROVIDER);
  const [model, setModel] = useState(settings.LLM_MODEL);
  const [key, setKey] = useState("");
  const [status, setStatus] = useState<LlmStatus | "checking" | null>(null);
  const [saving, setSaving] = useState(false);
  // Installed Ollama models: undefined = still asking, null = Ollama didn't answer.
  const [local, setLocal] = useState<string[] | null | undefined>(undefined);
  const [check, setCheck] = useState<SystemCheck | null>(null);
  const [saved, setSaved] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [autostart, setAutostart] = useState<Autostart | null>(null);

  const dirty = provider !== settings.LLM_PROVIDER || model.trim() !== settings.LLM_MODEL || key.trim() !== "";

  useEffect(() => {
    // Installed local models, for the model dropdown (14a).
    getApi()
      .then((api) => api.ollama_status())
      .then((s) => setLocal(s.running ? s.models : null))
      .catch(() => setLocal(null));
  }, []);

  useEffect(() => {
    getApi()
      .then((api) => api.autostart_status())
      .then(setAutostart)
      .catch(() => setAutostart(null));
  }, []);

  const toggleAutostart = async (on: boolean) => {
    setError(null);
    try {
      setAutostart(await (await getApi()).set_autostart(on));
      setSaved("reminders");
      window.setTimeout(() => setSaved((s) => (s === "reminders" ? null : s)), 2500);
    } catch (e) {
      setError(errorMessage(e));
    }
  };

  useEffect(() => {
    // Which 3D level suits this PC with the saved model (a few seconds).
    setCheck(null);
    getApi()
      .then((api) => api.system_check(settings.LLM_PROVIDER, settings.LLM_MODEL))
      .then(setCheck)
      .catch(() => setCheck(null));
  }, [settings.LLM_PROVIDER, settings.LLM_MODEL]);

  /** For Claude, a real 5-token call: llm_status() only sees that a key exists, not that it works. */
  const checkConnection = useCallback(async (provider: string, model: string) => {
    setStatus("checking");
    try {
      const api = await getApi();
      if (provider !== "anthropic") {
        setStatus(await api.llm_status());
        return;
      }
      const test = await api.test_api_key(null, model);
      setStatus(test.ok ? { ok: true, message: `Claude (${model}) answered with your API key.` } : test);
    } catch (e) {
      setStatus({ ok: false, message: errorMessage(e) });
    }
  }, []);

  const saveModel = async (e: FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const api = await getApi();
      let next = await api.save_settings({ LLM_PROVIDER: provider, LLM_MODEL: model.trim() || DEFAULT_MODELS[provider] });
      if (key.trim()) next = await api.set_api_key(key.trim());
      setKey("");
      onSettings(next);
      await checkConnection(next.LLM_PROVIDER, next.LLM_MODEL);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  /** Appearance and options: saved at once. */
  const saveNow = async (updates: Record<string, string>, label: string) => {
    setError(null);
    try {
      onSettings(await (await getApi()).save_settings(updates));
      setSaved(label);
      window.setTimeout(() => setSaved((s) => (s === label ? null : s)), 2500);
    } catch (e) {
      setError(errorMessage(e));
    }
  };

  /** 14f: errors go to the shortcut field, next to the keys you pressed. */
  const saveShortcut = async (value: string) => {
    onSettings(await (await getApi()).save_settings({ QUICK_KEY: value }));
    setSaved("quick");
    window.setTimeout(() => setSaved((s) => (s === "quick" ? null : s)), 2500);
  };

  const changeProvider = (next: string) => {
    setProvider(next);
    setStatus(null);
    // A model name only makes sense for its own provider.
    setModel(next === settings.LLM_PROVIDER ? settings.LLM_MODEL : DEFAULT_MODELS[next]);
  };

  const cloud = provider === "anthropic";

  return (
    <div className="page settings">
      <header className="page-head">
        <h1>Settings</h1>
        <p>Saved on this PC, in JobLens' own folder.</p>
      </header>

      {error && (
        <p className="notice notice-danger" role="alert">
          {error}
        </p>
      )}

      <section className="card settings-card" aria-labelledby="model-title">
        <div className="section-head">
          <h2 id="model-title">AI model</h2>
          <a className="link-sm" href="#/setup">
            Run setup wizard
          </a>
        </div>
        <form onSubmit={saveModel} className="settings-form">
          <div className="segmented" role="radiogroup" aria-label="Where the AI runs">
            {[
              { id: "ollama", label: "On this PC (Ollama)" },
              { id: "anthropic", label: "Claude API" },
            ].map((p) => (
              <label key={p.id} className="segment">
                <input type="radio" name="provider" checked={provider === p.id} onChange={() => changeProvider(p.id)} />
                <span>{p.label}</span>
              </label>
            ))}
          </div>
          <p className="hint">
            {cloud
              ? "Fast on any PC. Job text and your resume are sent to Anthropic. About $0.01 per job with Claude Haiku."
              : "Free and private: nothing leaves this PC. Needs Ollama and about 8–16 GB of RAM."}
          </p>

          <div className="field">
            <span>Model</span>
            {!cloud && local === undefined ? (
              <select className="input mono" disabled aria-label="Model">
                <option>{model} (checking Ollama…)</option>
              </select>
            ) : (
              <ModelPicker cloud={cloud} value={model} installed={local ?? null} onChange={setModel} />
            )}
          </div>

          {cloud && (
            <label className="field">
              <span>API key {settings.ANTHROPIC_API_KEY_SET && <span className="badge">A key is saved</span>}</span>
              <input
                className="input mono"
                type="password"
                value={key}
                onChange={(e) => setKey(e.target.value)}
                placeholder={settings.ANTHROPIC_API_KEY_SET ? "Paste a new key to replace it" : "sk-ant-…"}
                autoComplete="off"
                spellCheck={false}
              />
              <span className="hint">
                Create one at <a href="https://console.anthropic.com/settings/keys">console.anthropic.com</a>. It's stored only in JobLens' settings file on this PC.
              </span>
            </label>
          )}

          <div className="row-actions">
            <button type="submit" className="btn btn-primary" disabled={!dirty || saving}>
              {saving ? "Saving…" : "Save"}
            </button>
            <button type="button" className="btn btn-secondary" onClick={() => void checkConnection(settings.LLM_PROVIDER, settings.LLM_MODEL)} disabled={status === "checking"}>
              Check connection
            </button>
            {dirty && <span className="hint">Not saved yet</span>}
          </div>
          <Status status={status} />
        </form>
      </section>

      <section className="card settings-card" aria-labelledby="resumes-title">
        <div className="section-head">
          <h2 id="resumes-title">Your resumes</h2>
          {saved === "resumes" && (
            <span className="saved" role="status">
              Saved
            </span>
          )}
        </div>
        <p className="hint">Ticked resumes are compared with each job by default. Fewer resumes make step 2 faster.</p>
        <ResumeList
          defaults={{
            saved: String(settings.RESUMES_DEFAULT ?? ""),
            onChange: (value) => void saveNow({ RESUMES_DEFAULT: value }, "resumes"),
          }}
        />
        <label className="check">
          <input
            type="checkbox"
            checked={settings.RESUMES_ASK === "true"}
            onChange={(e) => void saveNow({ RESUMES_ASK: e.target.checked ? "true" : "false" }, "resumes")}
          />
          <span>
            Ask me which resumes to compare for each job
            <span className="hint">Shows the resumes on the Analyze screen every time, ticked with the defaults.</span>
          </span>
        </label>
      </section>

      <section className="card settings-card" aria-labelledby="look-title">
        <div className="section-head">
          <h2 id="look-title">Appearance</h2>
          {saved === "look" && (
            <span className="saved" role="status">
              Saved
            </span>
          )}
        </div>
        <fieldset className="plain-fieldset">
          <legend>Theme</legend>
          <div className="segmented" role="radiogroup" aria-label="Theme">
            {THEMES.map((t) => (
              <label key={t.id} className="segment">
                <input type="radio" name="theme" checked={theme === t.id} onChange={() => onTheme(t.id)} />
                <span>{t.label}</span>
              </label>
            ))}
          </div>
        </fieldset>
        <fieldset className="plain-fieldset">
          <legend>3D effects on the Dashboard</legend>
          <LevelPicker
            value={(settings.UI_3D ?? "animated") as Ui3D}
            onChange={(level) => void saveNow({ UI_3D: level }, "look")}
            recommended={check?.ui3d ?? null}
          />
          {!check && <p className="hint">Checking which level suits this PC…</p>}
        </fieldset>
      </section>

      <section className="card settings-card" aria-labelledby="options-title">
        <div className="section-head">
          <h2 id="options-title">Options</h2>
          {saved === "options" && (
            <span className="saved" role="status">
              Saved
            </span>
          )}
        </div>
        <label className="check">
          <input
            type="checkbox"
            checked={(settings.JUDGE_EVIDENCE ?? "true") === "true"}
            onChange={(e) => void saveNow({ JUDGE_EVIDENCE: e.target.checked ? "true" : "false" }, "options")}
          />
          <span>
            Double-check skill evidence with a second AI call
            <span className="hint">More accurate fit scores, about 30 s slower per job.</span>
          </span>
        </label>
        <fieldset className="plain-fieldset">
          <legend>Fit answer</legend>
          <div className="segmented" role="radiogroup" aria-label="Fit answer">
            {FIT_DETAIL.map((d) => (
              <label key={d.id} className="segment">
                <input
                  type="radio"
                  name="fit-detail"
                  checked={(settings.FIT_DETAIL ?? "short") === d.id}
                  onChange={() => void saveNow({ FIT_DETAIL: d.id }, "options")}
                />
                <span>{d.label}</span>
              </label>
            ))}
          </div>
          <p className="hint">
            Short: up to 3 talking points, step 2 about 20% faster. Detailed: up to 5, and the verdict may be longer. Either way the
            verdict names your proven skills and the main gap, and the score is worked out the same way.
          </p>
        </fieldset>
        <label className="field narrow">
          <span>Tracing (for developers)</span>
          <select className="input" value={String(settings.TRACING ?? "off")} onChange={(e) => void saveNow({ TRACING: e.target.value }, "options")}>
            <option value="off">Off</option>
            <option value="langfuse">Langfuse (on this PC, needs Docker)</option>
            <option value="langsmith">LangSmith (cloud: uploads your resume text)</option>
          </select>
          <span className="hint">Applies after restarting JobLens. The run log behind Evals is always on.</span>
        </label>
      </section>

      <section className="card settings-card" aria-labelledby="reminders-title">
        <div className="section-head">
          <h2 id="reminders-title">Reminders</h2>
          {saved === "reminders" && (
            <span className="saved" role="status">
              Saved
            </span>
          )}
        </div>
        <label className="field narrow">
          <span>Remind me to follow up</span>
          <select
            className="input"
            value={String(settings.FOLLOW_UP_DAYS ?? "7")}
            onChange={(e) => void saveNow({ FOLLOW_UP_DAYS: e.target.value }, "reminders")}
          >
            {FOLLOW_UP_DAYS.map((d) => (
              <option key={d.id} value={d.id}>
                {d.label}
              </option>
            ))}
          </select>
          <span className="hint">
            For jobs in Applied or Interviewing with no change since. They get a “Follow up?” badge in the Tracker, and one tray notification a
            day while the window is closed.
          </span>
        </label>
        <label className="check">
          <input
            type="checkbox"
            checked={autostart?.enabled ?? false}
            disabled={!autostart?.supported}
            onChange={(e) => void toggleAutostart(e.target.checked)}
          />
          <span>
            Start JobLens with Windows, in the tray
            <span className="hint">
              {autostart?.supported === false
                ? "Works in the installed JobLens only."
                : "It opens hidden when you sign in, so reminders reach you. Closing the window then keeps it in the tray; quit from the tray icon."}
            </span>
          </span>
        </label>
      </section>

      <section className="card settings-card" aria-labelledby="quick-title">
        <div className="section-head">
          <h2 id="quick-title">Quick analyze</h2>
          {saved === "quick" && (
            <span className="saved" role="status">
              Saved
            </span>
          )}
        </div>
        <p className="hint">
          Press the shortcut anywhere in Windows, even with JobLens in the tray: a small box opens with the link you copied. Analyze runs in the
          background, and a notification (with a sound) tells you when the cover note is ready.
        </p>
        <ShortcutField saved={String(settings.QUICK_KEY ?? "Ctrl+Alt+J")} onSave={saveShortcut} />
      </section>

      <section className="card settings-card" aria-labelledby="updates-title">
        <div className="section-head">
          <h2 id="updates-title">Updates</h2>
          {saved === "updates" && (
            <span className="saved" role="status">
              Saved
            </span>
          )}
        </div>
        <UpdatesCard
          enabled={(settings.UPDATE_CHECK ?? "true") !== "false"}
          onToggle={(on) => void saveNow({ UPDATE_CHECK: on ? "true" : "false" }, "updates")}
        />
      </section>
    </div>
  );
}
