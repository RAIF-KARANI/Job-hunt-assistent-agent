// List view: a sortable table. The status can be changed right in the row,
// which is also the keyboard-friendly way to move a job.

import { useState } from "react";
import type { JobRow, JobStatus } from "../bridge/types";
import { FitChip } from "./FitChip";
import { ago, parseUtc, STATUSES, statusLabel } from "./status";

type SortKey = "company" | "title" | "fit_score" | "status" | "updated_at";

const COLUMNS: { key: SortKey; label: string }[] = [
  { key: "company", label: "Company" },
  { key: "title", label: "Role" },
  { key: "fit_score", label: "Fit" },
  { key: "status", label: "Status" },
  { key: "updated_at", label: "Updated" },
];

const ORDER = STATUSES.map((s) => s.id);

function compare(a: JobRow, b: JobRow, key: SortKey): number {
  switch (key) {
    case "fit_score":
      return a.fit_score - b.fit_score;
    case "status":
      return ORDER.indexOf(a.status) - ORDER.indexOf(b.status);
    case "updated_at":
      return parseUtc(a.updated_at).getTime() - parseUtc(b.updated_at).getTime();
    default:
      return a[key].localeCompare(b[key]);
  }
}

interface Props {
  jobs: JobRow[];
  onOpen(id: number): void;
  onMove(id: number, to: JobStatus): void;
}

export function JobList({ jobs, onOpen, onMove }: Props) {
  const [sort, setSort] = useState<{ key: SortKey; desc: boolean }>({ key: "fit_score", desc: true });
  const rows = [...jobs].sort((a, b) => compare(a, b, sort.key) * (sort.desc ? -1 : 1));

  const sortBy = (key: SortKey) =>
    setSort((s) => (s.key === key ? { key, desc: !s.desc } : { key, desc: key === "fit_score" || key === "updated_at" }));

  return (
    <div className="table-wrap">
      <table className="job-table">
        <thead>
          <tr>
            {COLUMNS.map((c) => (
              <th key={c.key} scope="col" aria-sort={sort.key === c.key ? (sort.desc ? "descending" : "ascending") : "none"}>
                <button type="button" className="th-sort" onClick={() => sortBy(c.key)}>
                  {c.label}
                  <span className="sort-mark" aria-hidden="true">
                    {sort.key === c.key ? (sort.desc ? "↓" : "↑") : ""}
                  </span>
                </button>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((job) => (
            <tr key={job.id}>
              <td>
                <button type="button" className="row-open" onClick={() => onOpen(job.id)}>
                  {job.company}
                </button>
              </td>
              <td className="cell-title">{job.title}</td>
              <td>
                <FitChip score={job.fit_score} />
              </td>
              <td>
                <select
                  className="input select-sm"
                  value={job.status}
                  aria-label={`Status of ${job.company}, ${job.title}`}
                  onChange={(e) => onMove(job.id, e.target.value as JobStatus)}
                >
                  {STATUSES.map((s) => (
                    <option key={s.id} value={s.id}>
                      {statusLabel(s.id)}
                    </option>
                  ))}
                </select>
              </td>
              <td className="cell-muted" title={`${job.updated_at} UTC`}>
                {ago(job.updated_at)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
