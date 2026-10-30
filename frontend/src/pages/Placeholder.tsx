// Stand-in screens for 12c: the shell is real, the pages arrive in 12d-12g.

import { useEffect, useState } from "react";
import { getApi } from "../bridge/bridge";
import type { JobRow } from "../bridge/types";
import type { PageId } from "../app/routes";

const COPY: Record<PageId, { title: string; lead: string; step: string }> = {
  dashboard: { title: "Dashboard", lead: "Every job you analyzed, and how well JobLens did.", step: "12f" },
  analyze: { title: "Analyze a job", lead: "Paste a posting link and watch the agent work.", step: "12d" },
  tracker: { title: "Tracker", lead: "Your applications, from researched to offer.", step: "12e" },
  evals: { title: "Agent evals", lead: "How well the agent did, measured on your PC.", step: "12f2" },
  settings: { title: "Settings", lead: "Model, API key, resumes and appearance.", step: "12g" },
};

export function Placeholder({ page }: { page: PageId }) {
  const copy = COPY[page];
  return (
    <div className="page">
      <header className="page-head">
        <h1>{copy.title}</h1>
        <p>{copy.lead}</p>
      </header>
      {page === "dashboard" && <TrackedJobs />}
      <section className="card placeholder">
        <h2>Coming in step {copy.step}</h2>
        <p>This screen is built next. The window, navigation and theme around it are ready.</p>
      </section>
    </div>
  );
}

/** Real data through the bridge: proves page -> Python -> tracker works. */
function TrackedJobs() {
  const [jobs, setJobs] = useState<JobRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getApi()
      .then((api) => api.list_jobs())
      .then(setJobs)
      .catch((e: Error) => setError(e.message));
  }, []);

  if (error) return <p className="card error">{error}</p>;
  return (
    <section className="tiles" aria-label="Key numbers">
      <div className="tile">
        <span className="tile-label">Jobs tracked</span>
        <span className="tile-value">{jobs ? jobs.length : "–"}</span>
      </div>
      <div className="tile">
        <span className="tile-label">Best fit</span>
        <span className="tile-value">{jobs?.length ? Math.max(...jobs.map((j) => j.fit_score)) : "–"}</span>
      </div>
      <div className="tile">
        <span className="tile-label">Applied or further</span>
        <span className="tile-value">
          {jobs ? jobs.filter((j) => ["applied", "interviewing", "offer"].includes(j.status)).length : "–"}
        </span>
      </div>
    </section>
  );
}
