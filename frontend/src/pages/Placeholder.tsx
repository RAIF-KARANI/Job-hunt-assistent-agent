// Stand-in screens: the shell is real, the remaining pages arrive in 12f2-12g.

import type { PageId } from "../app/routes";

const COPY: Partial<Record<PageId, { title: string; lead: string; step: string }>> = {
  evals: { title: "Agent evals", lead: "How well the agent did, measured on your PC.", step: "12f2" },
  settings: { title: "Settings", lead: "Model, API key, resumes and appearance.", step: "12g" },
};

export function Placeholder({ page }: { page: PageId }) {
  const copy = COPY[page] ?? { title: page, lead: "", step: "a later step" };
  return (
    <div className="page">
      <header className="page-head">
        <h1>{copy.title}</h1>
        <p>{copy.lead}</p>
      </header>
      <section className="card placeholder">
        <h2>Coming in step {copy.step}</h2>
        <p>This screen is built next. The window, navigation and theme around it are ready.</p>
      </section>
    </div>
  );
}
