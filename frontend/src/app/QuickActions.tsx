import { useEffect, useMemo, useRef, useState, type KeyboardEvent, type MouseEvent } from "react";
import { errorMessage, getApi } from "../bridge/bridge";
import type { JobRow } from "../bridge/types";
import { FitChip } from "../tracker/FitChip";
import { matches, statusLabel } from "../tracker/status";
import { Icon } from "./Icon";
import { PAGES } from "./routes";

// 17c: Ctrl K. One box to search the jobs, jump to a page, or do the next
// thing. Type to filter, Up / Down to move, Enter to open, Esc to close.

interface Props {
  open: boolean;
  onClose(): void;
  theme: "dark" | "light";
  onToggleTheme(): void;
}

interface Item {
  key: string;
  group: "Actions" | "Go to" | "Jobs" | "Recent jobs";
  title: string;
  meta?: string;
  kind: "action" | "nav" | "job";
  fit?: number;
  /** Words that also find this item ("csv" finds Export). */
  words?: string;
  run(): void | Promise<void>;
}

const RECENT = 3; // jobs shown before you type
const MOST = 8; // jobs shown while you type

export function QuickActions({ open, onClose, theme, onToggleTheme }: Props) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const [jobs, setJobs] = useState<JobRow[]>([]);
  const [note, setNote] = useState<string | null>(null); // the result of an action, or why it failed

  // Fresh each time it opens: jobs change while the app is open.
  useEffect(() => {
    const el = dialog.current;
    if (!el) return;
    if (open && !el.open) {
      setQuery("");
      setActive(0);
      setNote(null);
      el.showModal();
      getApi()
        .then((api) => api.list_jobs())
        .then(setJobs)
        .catch((e) => setNote(`Couldn't read your jobs: ${errorMessage(e)}`));
    } else if (!open && el.open) {
      el.close();
    }
  }, [open]);

  const items = useMemo(() => {
    const go = (hash: string) => () => {
      window.location.hash = hash;
      onClose();
    };
    const asks = jobs.filter((j) => j.apply_ask).length;
    const due = jobs.filter((j) => j.follow_up).length;
    const actions: Item[] = [
      { key: "a-new", group: "Actions", kind: "action", title: "Analyze a new job", meta: "Paste a link", words: "new analysis", run: go("#/analyze") },
    ];
    if (asks > 0) {
      actions.push({ key: "a-ask", group: "Actions", kind: "action", title: "Confirm applications", meta: `${asks} waiting`, words: "did you apply", run: go("#/tracker?show=apply") });
    }
    if (due > 0) {
      actions.push({ key: "a-due", group: "Actions", kind: "action", title: "Follow up", meta: `${due} with no news`, words: "email reminder", run: go("#/tracker?show=follow") });
    }
    actions.push(
      {
        key: "a-export",
        group: "Actions",
        kind: "action",
        title: "Export the tracker as CSV",
        words: "save download spreadsheet",
        run: async () => {
          try {
            const result = await (await getApi()).export_tracker();
            if (result) setNote(`${result.count} job${result.count === 1 ? "" : "s"} saved to ${result.path}`);
          } catch (e) {
            setNote(`Couldn't export: ${errorMessage(e)}`);
          }
        },
      },
      {
        key: "a-theme",
        group: "Actions",
        kind: "action",
        title: theme === "dark" ? "Switch to light mode" : "Switch to dark mode",
        words: "theme appearance",
        run: onToggleTheme,
      },
    );
    const pages: Item[] = PAGES.map((p) => ({ key: `p-${p.id}`, group: "Go to", kind: "nav", title: p.label, run: go(`#/${p.id}`) }));

    const text = query.trim();
    const hit = (it: Item) => `${it.title} ${it.meta ?? ""} ${it.words ?? ""} ${it.group}`.toLowerCase().includes(text.toLowerCase());
    const newest = [...jobs].sort((a, b) => b.updated_at.localeCompare(a.updated_at));
    const found = text ? newest.filter((j) => matches(j, text)).slice(0, MOST) : newest.slice(0, RECENT);
    const jobItems: Item[] = found.map((j) => ({
      key: `j-${j.id}`,
      group: text ? "Jobs" : "Recent jobs",
      kind: "job",
      title: `${j.company} · ${j.title}`,
      meta: statusLabel(j.status),
      fit: j.fit_score,
      run: go(`#/tracker?job=${j.id}`),
    }));
    return [...(text ? actions.filter(hit) : actions), ...(text ? pages.filter(hit) : pages), ...jobItems];
  }, [jobs, query, theme, onClose, onToggleTheme]);

  const current = Math.min(active, Math.max(0, items.length - 1));

  // Keep the highlighted row in view while the arrow keys move it.
  useEffect(() => {
    dialog.current?.querySelector('[aria-selected="true"]')?.scrollIntoView({ block: "nearest" });
  }, [current]);

  const onKey = (e: KeyboardEvent) => {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      if (items.length) setActive((current + (e.key === "ArrowDown" ? 1 : items.length - 1)) % items.length);
    } else if (e.key === "Enter") {
      e.preventDefault();
      void items[current]?.run();
    }
  };

  // A click on the dimmed area (the dialog itself, not the box in it) closes.
  const onBackdrop = (e: MouseEvent<HTMLDialogElement>) => {
    if (e.target === e.currentTarget) onClose();
  };

  let lastGroup = "";
  return (
    <dialog ref={dialog} className="quick-actions" aria-label="Quick actions" onClose={onClose} onClick={onBackdrop}>
      <div className="qa-box">
        <label className="qa-search">
          <Icon name="search" />
          <span className="sr-only">Search jobs or run an action</span>
          <input
            type="text"
            role="combobox"
            aria-expanded="true"
            aria-controls="qa-list"
            aria-activedescendant={items[current] ? `qa-${items[current].key}` : undefined}
            placeholder="Search jobs or run an action"
            autoComplete="off"
            spellCheck={false}
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setActive(0);
            }}
            onKeyDown={onKey}
          />
          <kbd className="kbd">Esc</kbd>
        </label>

        <ul id="qa-list" className="qa-list" role="listbox" aria-label="Results">
          {items.map((it, i) => {
            const heading = it.group !== lastGroup ? it.group : null;
            lastGroup = it.group;
            return (
              <li key={it.key} role="presentation">
                {heading && (
                  <span className="qa-label" role="presentation">
                    {heading}
                  </span>
                )}
                <button
                  type="button"
                  id={`qa-${it.key}`}
                  className="qa-item"
                  role="option"
                  aria-selected={i === current}
                  tabIndex={-1}
                  onMouseMove={() => setActive(i)}
                  onClick={() => void it.run()}
                >
                  {it.kind === "job" && it.fit !== undefined ? (
                    <FitChip score={it.fit} />
                  ) : (
                    <span className="qa-ico">
                      <Icon name={it.kind === "nav" ? "arrow" : "bolt"} size={15} />
                    </span>
                  )}
                  <span className="qa-title">{it.title}</span>
                  {it.meta && <span className="qa-meta">{it.meta}</span>}
                </button>
              </li>
            );
          })}
          {items.length === 0 && <li className="qa-empty">Nothing matches. Try a company, a role or a page name.</li>}
        </ul>

        <div className="qa-foot">
          {note ? (
            <span role="status">{note}</span>
          ) : (
            <>
              <span>
                <kbd className="kbd" aria-label="Up">
                  <Icon name="up" size={11} />
                </kbd>
                <kbd className="kbd" aria-label="Down">
                  <Icon name="down" size={11} />
                </kbd>
                Move
              </span>
              <span>
                <kbd className="kbd">Enter</kbd>Open
              </span>
              <span>
                <kbd className="kbd">Esc</kbd>Close
              </span>
            </>
          )}
        </div>
      </div>
    </dialog>
  );
}
