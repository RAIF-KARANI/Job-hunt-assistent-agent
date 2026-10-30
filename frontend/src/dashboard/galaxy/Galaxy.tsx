// The "Job galaxy" card. Picks how it's drawn from the 3D level (D14):
//   animated -> 3D, slow spin (30 FPS cap), still while the agent works
//   still    -> 3D, moves only when you drag
//   off      -> flat 2D map, no WebGL at all
// Windows' "reduce motion" turns animated into still; a WebGL failure
// turns 3D into the flat map for this session (the setting isn't changed).

import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import { useRun } from "../../analyze/runStore";
import type { JobRow, Ui3D } from "../../bridge/types";
import { byFit, placeJobs, type Placed } from "./layout";
import { OrbitMap } from "./OrbitMap";

const Galaxy3D = lazy(() => import("./Galaxy3D"));

const reducedQuery = () => window.matchMedia("(prefers-reduced-motion: reduce)");

function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState(() => reducedQuery().matches);
  useEffect(() => {
    const query = reducedQuery();
    const onChange = () => setReduced(query.matches);
    query.addEventListener("change", onChange);
    return () => query.removeEventListener("change", onChange);
  }, []);
  return reduced;
}

interface Props {
  jobs: JobRow[];
  level: Ui3D;
  selectedId: number | null;
  onSelect(id: number): void;
}

export function Galaxy({ jobs, level, selectedId, onSelect }: Props) {
  const busy = useRun().busy;
  const reduced = useReducedMotion();
  const [failed, setFailed] = useState<string | null>(null);
  const nodes = useMemo(() => placeJobs(jobs).sort(byFit), [jobs]);
  const crowded = nodes.length > 14;
  const labeled = (node: Placed) => !crowded || node.level === "high";

  const flat = level === "off" || failed !== null;
  const animate = level === "animated" && !reduced && !busy;

  let caption: string;
  if (flat) caption = "Seen from above. Closer to the center = better fit.";
  else if (level === "animated" && busy) caption = "Paused while the agent works, so the model gets the whole GPU. Drag to turn.";
  else if (level === "animated" && reduced) caption = "Not spinning: Windows is set to reduce motion. Drag to turn.";
  else caption = "Drag to turn. Tab moves through the jobs, best fit first.";

  return (
    <section className="card galaxy-card" aria-labelledby="galaxy-title">
      <header className="galaxy-head">
        <h2 id="galaxy-title">Job galaxy</h2>
        <span className="hint galaxy-hint">Closer to the center = better fit. Pick a job.</span>
        <span className="galaxy-legend">
          <span className="sr-only">Colors by fit:</span>
          <span>
            <i className="legend-dot node-high" />
            75+
          </span>
          <span>
            <i className="legend-dot node-mid" />
            55–74
          </span>
          <span>
            <i className="legend-dot node-low" />
            below 55
          </span>
        </span>
      </header>

      {failed && (
        <p className="notice notice-warn galaxy-notice" role="status">
          {failed}
        </p>
      )}

      <div className={flat ? "galaxy-stage flat" : "galaxy-stage"}>
        {jobs.length === 0 ? (
          <div className="galaxy-empty">
            <p>No jobs yet. Each job you analyze appears here, closer to the center the better it fits.</p>
            <a className="btn btn-primary" href="#/analyze">
              Analyze a job
            </a>
          </div>
        ) : flat ? (
          <OrbitMap nodes={nodes} selectedId={selectedId} labeled={labeled} onSelect={onSelect} />
        ) : (
          <Suspense fallback={<p className="galaxy-loading hint">Loading 3D…</p>}>
            <Galaxy3D
              nodes={nodes}
              selectedId={selectedId}
              labeled={labeled}
              onSelect={onSelect}
              animate={animate}
              onFail={setFailed}
            />
          </Suspense>
        )}
      </div>
      {jobs.length > 0 && <p className="hint galaxy-caption">{caption}</p>}
    </section>
  );
}
