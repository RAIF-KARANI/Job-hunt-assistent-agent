import { useEffect, useState } from "react";
import { Analyze } from "../analyze/Analyze";
import { catchUp } from "../analyze/runStore";
import { bridgeKind, getApi } from "../bridge/bridge";
import { Dashboard } from "../dashboard/Dashboard";
import { Evals } from "../evals/Evals";
import { Settings } from "../settings/Settings";
import { SetupWizard } from "../setup/SetupWizard";
import type { AppInfo, Settings as SettingsData, Theme } from "../bridge/types";
import { useRoute, type PageId } from "./routes";
import { Sidebar } from "./Sidebar";
import { Tracker } from "../tracker/Tracker";
import { useTheme } from "./useTheme";

export function App() {
  const page = useRoute();
  const [info, setInfo] = useState<AppInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [theme, setTheme] = useState<Theme>("system");
  const [skipped, setSkipped] = useState(false); // "Skip for now": this session only
  useTheme(theme);

  useEffect(() => {
    catchUp(); // a run may already be going (page reload)
    getApi()
      .then((api) => api.app_info())
      .then((i) => {
        setInfo(i);
        setTheme(i.settings.UI_THEME ?? "system");
        // Read by `python -m desktop_web --smoke` to confirm the page is alive.
        window.__joblens_ready = { bridge: bridgeKind, version: i.version };
      })
      .catch((e: Error) => setError(e.message));
  }, []);

  const changeTheme = (next: Theme) => {
    setTheme(next); // instant; saved in the background
    getApi()
      .then((api) => api.save_settings({ UI_THEME: next }))
      .catch(() => undefined);
  };

  /** Settings changed (Settings page, wizard): every screen sees it at once. */
  const onSettings = (settings: SettingsData) => setInfo((i) => (i ? { ...i, settings, setup_needed: false } : i));

  if (error) {
    return (
      <main className="fatal" role="alert">
        <h1>JobLens couldn't start</h1>
        <p>{error}</p>
      </main>
    );
  }

  const wizard = info && (page === "setup" || (info.setup_needed && !skipped));
  if (wizard) {
    const leave = () => {
      setSkipped(true);
      window.location.hash = page === "setup" ? "#/settings" : "#/dashboard";
    };
    return (
      <SetupWizard
        onSkip={leave}
        onFinish={(settings) => {
          onSettings(settings);
          setSkipped(true);
          window.location.hash = "#/analyze";
        }}
      />
    );
  }

  const shown: PageId = page === "setup" ? "settings" : page; // #/setup before the settings have loaded

  return (
    <div className="shell">
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <Sidebar page={shown} model={info?.settings.LLM_MODEL ?? "…"} theme={theme} onTheme={changeTheme} />
      <main id="main" className="content" tabIndex={-1}>
        {shown === "dashboard" ? (
          // Wait for the settings: with 3D off, three.js must never even load.
          info && <Dashboard level={info.settings.UI_3D ?? "animated"} />
        ) : shown === "analyze" ? (
          <Analyze />
        ) : shown === "tracker" ? (
          <Tracker />
        ) : shown === "evals" ? (
          <Evals />
        ) : (
          info && <Settings settings={info.settings} theme={theme} onTheme={changeTheme} onSettings={onSettings} />
        )}
        {info && <footer className="version">JobLens {info.version}</footer>}
      </main>
    </div>
  );
}
