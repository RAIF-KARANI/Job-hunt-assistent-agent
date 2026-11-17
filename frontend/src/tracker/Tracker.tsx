// Tracker screen (12e): every analyzed job, as a board or a list, with
// details in a side sheet. Status changes are saved to jobs.db at once.

import { useEffect, useRef, useState } from "react";
import { Exported } from "../app/Exported";
import { Fold } from "../app/Fold";
import { Icon } from "../app/Icon";
import { hashParam } from "../app/routes";
import { errorMessage, getApi } from "../bridge/bridge";
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
  const { jobs, error, load, move, followUp, applyAnswer } = useJobs();
  const [query, setQuery] = useState("");
  const [view, setView] = useState<View>(savedView);
  const [statuses, setStatuses] = useState<JobStatus[]>(savedStatuses); // empty = all
  const [openId, setOpenId] = useState<number | null>(null);
  const [followOnly, setFollowOnly] = useState(false); // 14e: only the jobs due a follow-up
  const [applyOnly, setApplyOnly] = useState(false); // 16i: only the jobs asking "Did you apply?"
  const [exported, setExported] = useState<{ path: string; count: number } | null>(null); // 14i
  const [exportError, setExportError] = useState<string | null>(null);
  const [deleted, setDeleted] = useState<string | null>(null); // 1.0.1

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

  // 16a: #/tracker?job=12 opens that job's details ("Open in the Tracker").
  // The id is then taken out of the address, so a reload after closing the
  // details doesn't open them again.
  useEffect(() => {
    const openFromHash = () => {
      // 17e: #/tracker?show=apply (or =follow) lists the jobs that reminder is about.
      const show = hashParam("show");
      if (show === "apply" || show === "follow") {
        setStatuses([]);
        setApplyOnly(show === "apply");
        setFollowOnly(show === "follow");
        setView("list");
        window.history.replaceState(null, "", "#/tracker");
        return;
      }
      const id = Number(hashParam("job"));
      if (!Number.isInteger(id) || id <= 0) return;
      setOpenId(id);
      window.history.replaceState(null, "", "#/tracker");
    };
    openFromHash();
    window.addEventListener("hashchange", openFromHash);
    return () => window.removeEventListener("hashchange", openFromHash);
  }, []);

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
  const dueCount = jobs?.filter((j) => j.follow_up).length ?? 0;
  // The status filter is for the List; the Board already sorts by status.
  const byStatus = view === "list" && statuses.length ? searched.filter((j) => statuses.includes(j.status)) : searched;
  const askCount = jobs?.filter((j) => j.apply_ask).length ?? 0; // 16i
  const shown = view !== "list" ? byStatus : byStatus.filter((j) => (!followOnly || j.follow_up) && (!applyOnly || j.apply_ask));
  const toggleStatus = (s: JobStatus) => setStatuses((old) => (old.includes(s) ? old.filter((x) => x !== s) : [...old, s]));
  const showStatus = (s: JobStatus) => {
    setStatuses([s]);
    setFollowOnly(false);
    setApplyOnly(false);
    setView("list");
  };
  const showFollowUps = () => {
    setStatuses([]);
    setFollowOnly(true);
    setApplyOnly(false);
    setView("list");
  };
  const showApplyAsks = () => {
    setStatuses([]);
    setFollowOnly(false);
    setApplyOnly(false);
    setApplyOnly(true);
    setView("list");
  };

  const exportCsv = async () => {
    setExportError(null);
    try {
      const result = await (await getApi()).export_tracker();
      if (result) setExported(result);
    } catch (e) {
      setExportError(`Couldn't export: ${errorMessage(e)}`);
    }
  };

  useEffect(() => {
    if (followOnly && dueCount === 0) setFollowOnly(false); // the last one was handled
  }, [followOnly, dueCount]);

  useEffect(() => {
    if (applyOnly && askCount === 0) setApplyOnly(false); // 16i: all answered
  }, [applyOnly, askCount]);

  return (
    <div className="page tracker">
      <header className="tracker-head">
        <div className="page-head">
          <h1>Tracker</h1>
          <p>{view === "board" ? "Left to right in the order a job moves. Drag a card to change its status." : "Change a status right in the list."}</p>
        </div>
        <div className="tracker-tools">
          <div className="field">
            <label htmlFor="job-search">Search jobs</label>
            <input
              id="job-search"
              className="input search"
              type="search"
              placeholder="Company, role, contact or notes"
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
          <button type="button" className="btn btn-secondary" onClick={() => void exportCsv()} disabled={!jobs?.length}>
            Export CSV
          </button>
        </div>
      </header>

      {error && (
        <p className="notice notice-danger" role="alert">
          {error}
        </p>
      )}

      {exported && <Exported what={`${exported.count} job${exported.count === 1 ? "" : "s"}`} path={exported.path} />}
      {exportError && (
        <p className="notice notice-danger" role="alert">
          {exportError}
        </p>
      )}

      {/* 17e: what is waiting for you, in the order you'd do it: confirm, then follow up. */}
      {(askCount > 0 || dueCount > 0) && (
        <Fold
          level={2}
          defaultOpen
          title="Needs you"
          digest={[askCount > 0 && `${askCount} to confirm`, dueCount > 0 && `${dueCount} to follow up`].filter(Boolean).join(" · ")}
        >
          <div className="needs" role="status">
            {askCount > 0 && (
              <div className="need">
                <span className="next-icon ask">
                  <Icon name="question" size={17} />
                </span>
                <span className="next-text">
                  <span className="next-title">Confirm you applied</span>
                  <span className="next-note">
                    {askCount === 1 ? "1 cover note has" : `${askCount} cover notes have`} been ready for over a day. Unanswered for a day, JobLens stops
                    asking.
                  </span>
                </span>
                <button type="button" className="btn btn-secondary btn-sm" onClick={showApplyAsks} disabled={view === "list" && applyOnly}>
                  Show {askCount === 1 ? "it" : "them"}
                </button>
              </div>
            )}
            {dueCount > 0 && (
              <div className="need">
                <span className="next-icon warn">
                  <Icon name="message" size={17} />
                </span>
                <span className="next-text">
                  <span className="next-title">Follow up</span>
                  <span className="next-note">
                    {dueCount === 1 ? "1 application has" : `${dueCount} applications have`} had no news for a while. A short email can help.
                  </span>
                </span>
                <button type="button" className="btn btn-secondary btn-sm" onClick={showFollowUps} disabled={view === "list" && followOnly}>
                  Show {dueCount === 1 ? "it" : "them"}
                </button>
              </div>
            )}
          </div>
        </Fold>
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
              <button
                type="button"
                className="chip-toggle"
                aria-pressed={statuses.length === 0 && !followOnly && !applyOnly}
                onClick={() => {
                  setStatuses([]);
                  setFollowOnly(false);
                  setApplyOnly(false);
                }}
              >
                All <span className="chip-count">{searched.length}</span>
              </button>
              {dueCount > 0 && (
                <button type="button" className="chip-toggle" aria-pressed={followOnly} onClick={() => setFollowOnly((on) => !on)}>
                  Follow up? <span className="chip-count">{searched.filter((j) => j.follow_up).length}</span>
                </button>
              )}
              {askCount > 0 && (
                <button type="button" className="chip-toggle" aria-pressed={applyOnly} onClick={() => setApplyOnly((on) => !on)}>
                  Applied? <span className="chip-count">{searched.filter((j) => j.apply_ask).length}</span>
                </button>
              )}
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
                (view === "list" && statuses.length ? ` · ${statuses.map(statusLabel).join(", ")}` : "") +
                (view === "list" && followOnly ? " · due a follow-up" : "") +
                (view === "list" && applyOnly ? " · cover note ready for a day" : "")}
          </p>
          {view === "board" ? (
            <Board jobs={shown} onOpen={setOpenId} onMove={changeStatus} onShowStatus={showStatus} />
          ) : shown.length ? (
            <JobList jobs={shown} onOpen={setOpenId} onMove={changeStatus} />
          ) : (
            <p className="chart-empty">
              No jobs with this status{query ? " that match your search" : ""}.{" "}
              <button
                type="button"
                className="link-button"
                onClick={() => {
                  setStatuses([]);
                  setFollowOnly(false);
                  setApplyOnly(false);
                }}
              >
                Show all
              </button>
            </p>
          )}
        </>
      )}

      <div className="toast-slot" aria-live="polite">
        {deleted && (
          <div className="toast" role="status">
            <span>
              Deleted <strong>{deleted}</strong>
            </span>
          </div>
        )}
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
          row={jobs?.find((j) => j.id === openId)}
          onMove={changeStatus}
          onFollowUp={followUp}
          onApply={applyAnswer}
          onChanged={load}
          onDeleted={(what) => {
            setDeleted(what);
            setLastMove(null);
            load();
            window.clearTimeout(undoTimer.current);
            undoTimer.current = window.setTimeout(() => setDeleted(null), 6000);
          }}
          onClose={() => setOpenId(null)}
        />
      )}
    </div>
  );
}
