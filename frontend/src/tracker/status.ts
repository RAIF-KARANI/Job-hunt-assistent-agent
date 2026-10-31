import type { JobRow, JobStatus } from "../bridge/types";

// Same order as job_agent.tracker.STATUSES: one board column each.
export const STATUSES: { id: JobStatus; label: string; color: string }[] = [
  { id: "researched", label: "Researched", color: "var(--st-researched)" },
  { id: "cover_note_ready", label: "Cover note ready", color: "var(--st-cover)" },
  { id: "applied", label: "Applied", color: "var(--st-applied)" },
  { id: "interviewing", label: "Interviewing", color: "var(--st-interviewing)" },
  { id: "offer", label: "Offer", color: "var(--st-offer)" },
  { id: "rejected", label: "Rejected", color: "var(--st-rejected)" },
];

export const statusLabel = (id: string) => STATUSES.find((s) => s.id === id)?.label ?? id;

export type FitLevel = "high" | "mid" | "low";
export const fitLevel = (score: number): FitLevel => (score >= 75 ? "high" : score >= 55 ? "mid" : "low");

/** The tracker stores UTC "YYYY-MM-DD HH:MM:SS". */
export function parseUtc(value: string): Date {
  return new Date(value.replace(" ", "T") + "Z");
}

export function ago(value: string, now = Date.now()): string {
  const days = Math.floor((now - parseUtc(value).getTime()) / 86_400_000);
  if (Number.isNaN(days)) return value;
  if (days <= 0) return "today";
  if (days === 1) return "yesterday";
  if (days < 14) return `${days} days ago`;
  if (days < 60) return `${Math.floor(days / 7)} weeks ago`;
  return parseUtc(value).toLocaleDateString();
}

/** The small line on each card. `updated_at` is when the status last changed. */
export function cardNote(job: JobRow): string {
  const when = ago(job.updated_at);
  switch (job.status) {
    case "researched":
      return `Analyzed ${ago(job.created_at)}`;
    case "cover_note_ready":
      return `Note approved ${when}`;
    case "applied":
      return `Applied ${when}`;
    default:
      return `Updated ${when}`;
  }
}

/** 14e: days since the follow-up clock started (status change or "I followed up"). */
export function quietDays(job: JobRow, now = Date.now()): number {
  const since = Math.max(...[job.updated_at, job.followed_up_at].filter((v): v is string => !!v).map((v) => parseUtc(v).getTime()));
  return Math.floor((now - since) / 86_400_000);
}

export function matches(job: JobRow, query: string): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return true;
  return [job.company, job.title, job.best_resume, statusLabel(job.status)].some((v) => v?.toLowerCase().includes(q));
}
