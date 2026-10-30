import { useEffect, useState } from "react";
import { useRun } from "../analyze/runStore";
import { getApi } from "../bridge/bridge";
import type { LlmStatus, Theme } from "../bridge/types";
import { Icon, Logo, type IconName } from "./Icon";
import { PAGES, type PageId } from "./routes";

const THEMES: { id: Theme; label: string; icon: IconName }[] = [
  { id: "system", label: "Match Windows", icon: "monitor" },
  { id: "dark", label: "Dark", icon: "moon" },
  { id: "light", label: "Light", icon: "sun" },
];

interface Props {
  page: PageId;
  model: string;
  theme: Theme;
  onTheme(theme: Theme): void;
}

export function Sidebar({ page, model, theme, onTheme }: Props) {
  const [status, setStatus] = useState<LlmStatus | null>(null);
  const run = useRun();
  const waiting = run.phase === "review" || run.phase === "paste";

  useEffect(() => {
    getApi()
      .then((api) => api.llm_status())
      .then(setStatus)
      .catch((e: Error) => setStatus({ ok: false, message: e.message }));
  }, [model]);

  const [dot, label] = run.busy
    ? ["var(--accent)", "Agent working"]
    : waiting
      ? ["var(--warn)", "Waiting for you"]
      : status === null
        ? ["var(--text-faint)", "Checking the model..."]
        : status.ok
          ? ["var(--ok)", "Model ready"]
          : ["var(--danger-ink)", "Model not ready"];

  return (
    <nav className="sidebar" aria-label="Main">
      <div className="brand">
        <Logo />
        <span>JobLens</span>
      </div>

      <ul className="nav">
        {PAGES.map((p) => (
          <li key={p.id}>
            <a href={`#/${p.id}`} className="nav-link" aria-current={p.id === page ? "page" : undefined}>
              <Icon name={p.icon} />
              {p.label}
              {p.id === "analyze" && (run.busy || waiting) && (
                <span className={waiting ? "nav-dot waiting" : "nav-dot"} title={label}>
                  <span className="sr-only">({label})</span>
                </span>
              )}
            </a>
          </li>
        ))}
      </ul>

      <div className="sidebar-foot">
        <div className="model-card" role="status" title={status?.message}>
          <span className="model-card-state">
            <span className={run.busy ? "dot pulse" : "dot"} style={{ background: dot }} />
            {label}
          </span>
          <span className="model-card-name">{model}</span>
        </div>

        <div className="theme-switch" role="group" aria-label="Theme">
          {THEMES.map((t) => (
            <button
              key={t.id}
              type="button"
              aria-pressed={theme === t.id}
              aria-label={t.label}
              title={t.label}
              onClick={() => onTheme(t.id)}
            >
              <Icon name={t.icon} size={16} />
            </button>
          ))}
        </div>
      </div>
    </nav>
  );
}
