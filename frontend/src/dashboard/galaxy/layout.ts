// Where each job sits in the galaxy. One function for all three levels
// (animated, still, flat map), so they always show the same thing:
// distance from the center = how far the job is from a perfect fit.

import type { JobRow } from "../../bridge/types";
import { fitLevel, type FitLevel } from "../../tracker/status";

export interface Placed {
  job: JobRow;
  level: FitLevel;
  /** Position in a unit disc seen from above: x right, z down (towards you). */
  x: number;
  z: number;
  /** Small height above/below the disc, 3D only (spreads labels apart). */
  y: number;
  r: number;
}

/** A fit of 100 sits on the inner edge, 20 or less on the outer ring. Real
 *  scores are rarely under 20, and a 0-100 scale crowded the good jobs
 *  into the middle (seen with real data in 12f). */
export const INNER = 0.32;
const FLOOR = 20;
export const radius = (fit: number) =>
  INNER + ((1 - INNER) * (100 - Math.min(100, Math.max(FLOOR, fit)))) / (100 - FLOOR);

/** The two boundaries between fit levels (75 and 55), plus the outer edge. */
export const RINGS = [radius(75), radius(55), radius(FLOOR)];

const GOLDEN_ANGLE = Math.PI * (3 - Math.sqrt(5));

/** The angle depends on the job id only, so a job stays put when others are added. */
export function placeJobs(jobs: JobRow[]): Placed[] {
  return jobs.map((job) => {
    const r = radius(job.fit_score);
    const angle = job.id * GOLDEN_ANGLE;
    return {
      job,
      level: fitLevel(job.fit_score),
      r,
      x: Math.cos(angle) * r,
      z: Math.sin(angle) * r,
      y: (((job.id * 7919) % 100) / 100 - 0.5) * 0.22,
    };
  });
}

/** Tab order: best fit first. */
export const byFit = (a: Placed, b: Placed) => b.job.fit_score - a.job.fit_score || a.job.id - b.job.id;
