// Tracker screen (12e): every analyzed job, as a board or a list, with
// details in a side sheet. Status changes are saved to jobs.db at once.

import { useEffect, useRef, useState } from "react";
import type { JobStatus } from "../bridge/types";
import { Board } from "./Board";
import { JobList } from "./JobList";
import { JobSheet } from "./JobSheet";
import { matches, STATUSES, statusLabel } from "./status";
import { useJobs, type Move } from "./useJobs";

type View = "board" | "list";
const VIEW_KEY = "joblens.tracker.view";
const STATUS_KEY = "joblens.tracker.statuses"; // 14a: the List's status filter

function savedView(): View {
  try {
    return localStorage.getItem(VIEW_KEY) === "list" ? "list" : "board";
  } catch {
    return "board";
  }
}

function savedStatuses(): JobStatus[] {
  try {
    const saved = JSON.parse(localStorage.getItem(STATUS_KEY) ?? "[]");
    return Array.isArray(saved) ? saved.filter((s) => STATUSES.some((x) => x.id === s)) : [];
  } catch {
    return [];
  }
}

export function Tracker() {
  const { jobs, error, move } = useJobs();
  const [query, setQuery] = useState("");
  const [view, setView] = useState<View>(savedView);
  const [statuses, setStatuses] = useState<JobStatus[]>(savedStatuses); // empty = all
  const [openId, setOpenId] = useState<number | null>(null);
  const [lastMove, setLastMove] = useState<Move | null>(null);
  const undoTimer = useRef<number | undefined>(undefined);

  useEffect(() => {
    try {
      localStorage.setItem(VIEW_KEY, view);
    } catch {
      /* private mode: not remembered, still works */
    }
  }, [view]);

  useEffect(() => () => window.clearTimeout(undoTimer.current), []);

  const changeStatus = async (id: number, to: JobStatus) => {
    const done = await move(id, to);
    if (!done) return;
    setLastMove(done);
    window.clearTimeout(undoTimer.current);
    undoTimer.current = window.setTimeout(() => setLastMove(null), 8000);
  };

  const undo = async () => {
    if (!lastMove) return;
    window.clearTimeout(undoTimer.current);
    setLastMove(null);
    await move(lastMove.job.id, lastMove.from);
  };

  useEffect(() => {
    try {
      localStorage.setItem(STATUS_KEY, JSON.stringify(statuses));
    } catch {
      /* not remembered, still works */
    }
  }, [statuses]);

  const searched = jobs?.filter((j) => matches(j, query)) ?? [];
  // The status filter is for the List; the Board already sorts by status.
  const shown = view === "list" && statuses.length ? searched.filter((j) => statuses.includes(j.status)) : searched;
  const toggleStatus = (s: JobStatus) => setStatuses((old) => (old.includes(s) ? old.filter((x) => x !== s) : [...old, s]));
  const showStatus = (s: JobStatus) => {
    setStatuses([s]);
    setView("list");
  };

  return (
    <div className="page tracker">
      <header className="tracker-head">
        <div className="page-head">
          <h1>Tracker</h1>
          <p>{view === "board" ? "Drag a card to change its status. Click it for the details." : "Change a status right in the list."}</p>
        </div>
        <div className="tracker-tools">
          <div className="field">
            <label htmlFor="job-search">Search jobs</label>
            <input
              id="job-search"
              className="input search"
              type="search"
              placeholder="Company, role or status"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>
          <div className="segmented" role="group" aria-label="View">
            {(["board", "list"] as const).map((v) => (
              <label key={v} className="segment">
                <input type="radio" name="tracker-view" checked={view === v} onChange={() => setView(v)} />
                <span>{v === "board" ? "Board" : "List"}</span>
              </label>
            ))}
          </div>
        </div>
      </header>

      {error && (
        <p className="notice notice-danger" role="alert">
          {error}
        </p>
      )}

      {jobs === null ? (
        !error && <p className="hint">Loading your jobs...</p>
      ) : jobs.length === 0 ? (
        <section className="card review empty">
          <h2>No jobs yet</h2>
          <p className="lead">
            Every posting you analyze lands here. <a href="#/analyze">Analyze your first job</a>.
          </p>
        </section>
      ) : (
        <>
          {view === "list" && (
            <div className="status-filter" role="group" aria-label="Show only these statuses">
              <button type="button" className="chip-toggle" aria-pressed={statuses.length === 0} onClick={() => setStatuses([])}>
                All <span className="chip-count">{searched.length}</span>
              </button>
              {STATUSES.map((s) => {
                const n = searched.filter((j) => j.status === s.id).length;
                return (
                  <button key={s.id} type="button" className="chip-toggle" aria-pressed={statuses.includes(s.id)} onClick={() => toggleStatus(s.id)}>
                    <span className="dot" style={{ background: s.color }} aria-hidden="true" />
                    {s.label} <span className="chip-count">{n}</span>
                  </button>
                );
              })}
            </div>
          )}
          <p className="hint count" aria-live="polite">
            {shown.length === jobs.length
              ? `${jobs.length} jobs`
              : `${shown.length} of ${jobs.length} jobs` +
                (query ? ` match “${query.trim()}”` : "") +
                (view === "list" && statuses.length ? ` · ${statuses.map(statusLabel).join(", ")}` : "")}
          </p>
          {view === "board" ? (
            <Board jobs={shown} onOpen={setOpenId} onMove={changeStatus} onShowStatus={showStatus} />
          ) : shown.length ? (
            <JobList jobs={shown} onOpen={setOpenId} onMove={changeStatus} />
          ) : (
            <p className="chart-empty">
              No jobs with this status{query ? " that match your search" : ""}.{" "}
              <button type="button" className="link-button" onClick={() => setStatuses([])}>
                Show all
              </button>
            </p>
          )}
        </>
      )}

      <div className="toast-slot" aria-live="polite">
        {lastMove && (
          <div className="toast" role="status">
            <span>
              {lastMove.job.company} moved to <strong>{statusLabel(lastMove.to)}</strong>
            </span>
            <button type="button" className="btn btn-ghost btn-sm" onClick={undo}>
              Undo
            </button>
          </div>
        )}
      </div>

      {openId !== null && (
        <JobSheet
          jobId={openId}
          status={jobs?.find((j) => j.id === openId)?.status}
          onMove={changeStatus}
          onClose={() => setOpenId(null)}
        />
      )}
    </div>
  );
}
