import { useCallback, useEffect, useState } from "react";
import { Analyze } from "../analyze/Analyze";
import { catchUp } from "../analyze/runStore";
import { Components } from "./Components";
import { bridgeKind, getApi } from "../bridge/bridge";
import { Dashboard } from "../dashboard/Dashboard";
import { Evals } from "../evals/Evals";
import { Insights } from "../insights/Insights";
import { Settings } from "../settings/Settings";
import { SetupWizard } from "../setup/SetupWizard";
import type { AppInfo, Settings as SettingsData, Theme } from "../bridge/types";
import { QuickActions } from "./QuickActions";
import { useRoute, type PageId } from "./routes";
import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";
import { useReminders } from "./useReminders";
import { Tracker } from "../tracker/Tracker";
import { useTheme } from "./useTheme";

export function App() {
  const page = useRoute();
  const [info, setInfo] = useState<AppInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [theme, setTheme] = useState<Theme>("system");
  const [skipped, setSkipped] = useState(false); // "Skip for now": this session only
  const resolved = useTheme(theme); // what is on screen: never "system"
  const reminders = useReminders();
  const [quick, setQuick] = useState(false); // 17c: quick actions (Ctrl K)

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

  // 17c: the top-bar switch flips what you see now. "Match Windows" is still
  // a choice in Settings; using the switch replaces it with dark or light.
  const toggleTheme = useCallback(() => changeTheme(resolved === "dark" ? "light" : "dark"), [resolved]);
  const closeQuick = useCallback(() => setQuick(false), []);

  // Ctrl K, from anywhere in the window. (The quick-analyze box has its own,
  // system-wide shortcut: a different one.)
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && !e.altKey && !e.shiftKey && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setQuick((open) => !open);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

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

  const sheet = page === "components";
  // #/setup before the settings have loaded shows Settings
  const shown: PageId = page === "setup" ? "settings" : sheet ? "dashboard" : page;

  return (
    <div className="shell">
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <Sidebar page={sheet ? null : shown} model={info?.settings.LLM_MODEL ?? "…"} reminders={reminders} />
      <main id="main" className="content" tabIndex={-1}>
        <TopBar theme={resolved} onToggleTheme={toggleTheme} onSearch={() => setQuick(true)} showNew={sheet || shown !== "analyze"} />
        {sheet ? (
          <Components />
        ) : shown === "dashboard" ? (
          // Wait for the settings: with 3D off, three.js must never even load.
          info && <Dashboard level={info.settings.UI_3D ?? "animated"} />
        ) : shown === "analyze" ? (
          <Analyze />
        ) : shown === "tracker" ? (
          <Tracker />
        ) : shown === "insights" ? (
          <Insights />
        ) : shown === "evals" ? (
          <Evals />
        ) : (
          info && <Settings settings={info.settings} theme={theme} onTheme={changeTheme} onSettings={onSettings} />
        )}
        {info && <footer className="version">JobLens {info.version}</footer>}
      </main>
      <QuickActions open={quick} onClose={closeQuick} theme={resolved} onToggleTheme={toggleTheme} />
    </div>
  );
}
