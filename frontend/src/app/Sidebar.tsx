import { useEffect, useState } from "react";
import { getApi, onEvent } from "../bridge/bridge";
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
  const [busy, setBusy] = useState(false);

  useEffect(() => onEvent((e) => e.type === "busy" && setBusy(e.busy)), []);
  useEffect(() => {
    getApi()
      .then((api) => Promise.all([api.llm_status(), api.run_state()]))
      .then(([s, state]) => {
        setStatus(s);
        setBusy(state.busy);
      })
      .catch((e: Error) => setStatus({ ok: false, message: e.message }));
  }, [model]);

  const dot = busy ? "var(--warn)" : status === null ? "var(--text-faint)" : status.ok ? "var(--ok)" : "var(--danger-ink)";
  const label = busy ? "Agent working" : status === null ? "Checking the model..." : status.ok ? "Model ready" : "Model not ready";

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
            </a>
          </li>
        ))}
      </ul>

      <div className="sidebar-foot">
        <div className="model-card" role="status" title={status?.message}>
          <span className="model-card-state">
            <span className="dot" style={{ background: dot }} />
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
