import { useEffect, useState } from "react";
import { useRun } from "../analyze/runStore";
import { getApi, onEvent } from "../bridge/bridge";
import type { LlmStatus } from "../bridge/types";
import { Icon, Logo } from "./Icon";
import { NAV_GROUPS, PAGES, type PageId } from "./routes";

interface Props {
  /** null: a screen that isn't in the menu (the component sheet). */
  page: PageId | null;
  model: string;
  /** Jobs waiting for you (follow-ups, "Did you apply?"), shown on Tracker. */
  reminders: number;
}

// 17c: two labelled groups. "Agent" folds away while you work on your job
// search; it opens by itself on its own pages.
export function Sidebar({ page, model, reminders }: Props) {
  const [status, setStatus] = useState<LlmStatus | null>(null);
  const run = useRun();
  const waiting = run.phase === "review" || run.phase === "paste";

  useEffect(() => {
    getApi()
      .then((api) => api.llm_status())
      .then(setStatus)
      .catch((e: Error) => setStatus({ ok: false, message: e.message }));
  }, [model]);

  // 13b: a newer JobLens on GitHub. The check runs in Python a few seconds
  // after start (at most once a day); the last answer is cached, so read it
  // now and also listen for the live result.
  const [update, setUpdate] = useState<{ latest: string; page: string } | null>(null);
  useEffect(() => {
    getApi()
      .then((api) => api.update_status())
      .then((u) => u.newer && u.latest && setUpdate({ latest: u.latest, page: u.page ?? "" }))
      .catch(() => undefined);
    return onEvent((e) => {
      if (e.type === "update_available") setUpdate({ latest: e.latest, page: e.page });
    });
  }, []);

  // A group you opened stays open; the group of the current page is always open.
  const [opened, setOpened] = useState<Record<string, boolean>>({});

  const [dot, label, short] = run.busy
    ? ["var(--purple)", "Agent working", "Working"]
    : waiting
      ? ["var(--warn)", "Waiting for you", "Your turn"]
      : status === null
        ? ["var(--text-faint)", "Checking the model...", "Checking"]
        : status.ok
          ? ["var(--ok)", "Model ready", "Ready"]
          : ["var(--danger-ink)", "Model not ready", "Not ready"];

  return (
    <nav className="sidebar" aria-label="Main">
      <div className="brand">
        <Logo />
        <span>JobLens</span>
      </div>

      <div className="nav-groups">
        {NAV_GROUPS.map((group) => {
          const pages = PAGES.filter((p) => p.group === group.id);
          const current = pages.some((p) => p.id === page);
          const open = !group.folds || current || !!opened[group.id];
          const listId = `nav-${group.id}`;
          return (
            <div key={group.id} className="nav-group">
              {group.folds ? (
                <button
                  type="button"
                  className="nav-label nav-fold"
                  aria-expanded={open}
                  aria-controls={listId}
                  disabled={current}
                  onClick={() => setOpened((o) => ({ ...o, [group.id]: !open }))}
                >
                  {group.label}
                  <Icon name="chevron" size={14} />
                </button>
              ) : (
                <span className="nav-label" id={`${listId}-label`}>
                  {group.label}
                </span>
              )}
              <ul id={listId} className={open ? "nav" : "nav closed"} aria-label={group.label}>
                {pages.map((p) => (
                  <li key={p.id}>
                    <a href={`#/${p.id}`} className="nav-link" aria-current={p.id === page ? "page" : undefined}>
                      <Icon name={p.icon} />
                      {p.label}
                      {p.id === "analyze" && (run.busy || waiting) && (
                        <span className={waiting ? "nav-dot waiting" : "nav-dot"} title={label}>
                          <span className="sr-only">({label})</span>
                        </span>
                      )}
                      {p.id === "tracker" && reminders > 0 && (
                        <span className="nav-count" title="Jobs waiting for you">
                          {reminders}
                          <span className="sr-only"> waiting for you</span>
                        </span>
                      )}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          );
        })}
      </div>

      <div className="sidebar-foot">
        {update && (
          // 13d: to Settings → Updates, where it downloads, verifies and installs.
          <a className="update-link" href="#/settings" title="Download and install it in Settings → Updates">
            Update available: {update.latest}
          </a>
        )}
        <a className="model-row" href="#/settings" role="status" title={status?.message ?? "Change the model in Settings"}>
          <span className={run.busy ? "dot pulse" : "dot"} style={{ background: dot }} />
          <span className="model-row-name">{model}</span>
          <span className="model-row-state">
            <span className="sr-only">{label}</span>
            <span aria-hidden="true">{short}</span>
          </span>
        </a>
      </div>
    </nav>
  );
}
