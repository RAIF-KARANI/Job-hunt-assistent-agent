import { useEffect, useState } from "react";
import { Analyze } from "../analyze/Analyze";
import { catchUp } from "../analyze/runStore";
import { bridgeKind, getApi } from "../bridge/bridge";
import type { AppInfo, Theme } from "../bridge/types";
import { Placeholder } from "../pages/Placeholder";
import { useRoute } from "./routes";
import { Sidebar } from "./Sidebar";
import { useTheme } from "./useTheme";

export function App() {
  const page = useRoute();
  const [info, setInfo] = useState<AppInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [theme, setTheme] = useState<Theme>("system");
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

  if (error) {
    return (
      <main className="fatal" role="alert">
        <h1>JobLens couldn't start</h1>
        <p>{error}</p>
      </main>
    );
  }

  return (
    <div className="shell">
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <Sidebar page={page} model={info?.settings.LLM_MODEL ?? "…"} theme={theme} onTheme={changeTheme} />
      <main id="main" className="content" tabIndex={-1}>
        {page === "analyze" ? <Analyze /> : <Placeholder page={page} />}
        {info && <footer className="version">JobLens {info.version}</footer>}
      </main>
    </div>
  );
}
