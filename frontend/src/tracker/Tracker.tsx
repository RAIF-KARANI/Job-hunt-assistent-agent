// Tracker screen (12e): every analyzed job, as a board or a list, with
// details in a side sheet. Status changes are saved to jobs.db at once.

import { useEffect, useRef, useState } from "react";
import type { JobStatus } from "../bridge/types";
import { Board } from "./Board";
import { JobList } from "./JobList";
import { JobSheet } from "./JobSheet";
import { matches, statusLabel } from "./status";
import { useJobs, type Move } from "./useJobs";

type View = "board" | "list";
const VIEW_KEY = "joblens.tracker.view";

function savedView(): View {
  try {
    return localStorage.getItem(VIEW_KEY) === "list" ? "list" : "board";
  } catch {
    return "board";
  }
}

export function Tracker() {
  const { jobs, error, move } = useJobs();
  const [query, setQuery] = useState("");
  const [view, setView] = useState<View>(savedView);
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

  const shown = jobs?.filter((j) => matches(j, query)) ?? [];

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
          <p className="hint count" aria-live="polite">
            {query ? `${shown.length} of ${jobs.length} jobs match “${query.trim()}”` : `${jobs.length} jobs`}
          </p>
          {view === "board" ? (
            <Board jobs={shown} onOpen={setOpenId} onMove={changeStatus} />
          ) : (
            <JobList jobs={shown} onOpen={setOpenId} onMove={changeStatus} />
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
