// Board view: one column per status. Drag a card to another column to
// change its status (keyboard: open the card, change it in the details).

import { useState, type DragEvent } from "react";
import type { JobRow, JobStatus } from "../bridge/types";
import { FitChip } from "./FitChip";
import { cardNote, fitLevel, interviewAhead, interviewLabel, STATUSES } from "./status";

interface Props {
  jobs: JobRow[];
  onOpen(id: number): void;
  onMove(id: number, to: JobStatus): void;
  /** A column's title was clicked: show that status as a filtered list. */
  onShowStatus(status: JobStatus): void;
}

const DRAG_TYPE = "application/x-joblens-job";

export function Board({ jobs, onOpen, onMove, onShowStatus }: Props) {
  const [dragging, setDragging] = useState<number | null>(null);
  const [over, setOver] = useState<JobStatus | null>(null);

  const drop = (e: DragEvent, status: JobStatus) => {
    e.preventDefault();
    const id = Number(e.dataTransfer.getData(DRAG_TYPE));
    setOver(null);
    setDragging(null);
    if (id) onMove(id, status);
  };

  return (
    <div className="board-scroll">
      <div className="board">
        {STATUSES.map((status) => {
          const cards = jobs.filter((j) => j.status === status.id);
          return (
            <section
              key={status.id}
              className={["column", cards.length === 0 && "empty", over === status.id && "drop-target"].filter(Boolean).join(" ")}
              aria-labelledby={`col-${status.id}`}
              onDragOver={(e) => {
                if (dragging === null) return;
                e.preventDefault(); // allows the drop
                e.dataTransfer.dropEffect = "move";
                if (over !== status.id) setOver(status.id);
              }}
              onDragLeave={(e) => {
                if (!e.currentTarget.contains(e.relatedTarget as Node)) setOver(null);
              }}
              onDrop={(e) => drop(e, status.id)}
            >
              <header className="column-head">
                <span className="dot" style={{ background: status.color }} />
                <h2 id={`col-${status.id}`}>
                  {/* 14a: the title opens the List, filtered to this status. */}
                  <button type="button" className="column-title" onClick={() => onShowStatus(status.id)} title={`Show the ${status.label.toLowerCase()} jobs as a list`}>
                    {status.label}
                  </button>
                </h2>
                <span className="column-count">{cards.length}</span>
              </header>
              {cards.map((job) => (
                <button
                  key={job.id}
                  type="button"
                  className={dragging === job.id ? "job-card dragging" : "job-card"}
                  draggable
                  onDragStart={(e) => {
                    e.dataTransfer.setData(DRAG_TYPE, String(job.id));
                    e.dataTransfer.effectAllowed = "move";
                    setDragging(job.id);
                  }}
                  onDragEnd={() => {
                    setDragging(null);
                    setOver(null);
                  }}
                  onClick={() => onOpen(job.id)}
                  aria-label={`${job.company}, ${job.title}, fit ${job.fit_score}. Open details`}
                >
                  <span className="job-card-top">
                    <span className="job-card-names">
                      <span className="job-card-company">{job.company}</span>
                      <span className="job-card-title">{job.title}</span>
                    </span>
                    <FitChip score={job.fit_score} />
                  </span>
                  <span className="fit-bar" aria-hidden="true">
                    <span className={`fit-bar-fill fit-${fitLevel(job.fit_score)}`} style={{ width: `${job.fit_score}%` }} />
                  </span>
                  {job.interview_at && (
                    <span className={interviewAhead(job.interview_at) ? "interview-chip" : "interview-chip past"}>
                      Interview {interviewLabel(job.interview_at)}
                    </span>
                  )}
                  {job.contact && <span className="job-card-contact">{job.contact}</span>}
                  <span className="job-card-note">
                    {cardNote(job)}
                    {job.follow_up && <span className="follow-badge">Follow up?</span>}
                  </span>
                </button>
              ))}
              {cards.length === 0 && <p className="column-empty">{dragging !== null ? "Drop here" : "No jobs"}</p>}
            </section>
          );
        })}
      </div>
    </div>
  );
}
