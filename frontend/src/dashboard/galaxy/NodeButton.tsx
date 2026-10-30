// One job in the galaxy, as a real button: clickable, reachable with Tab,
// and read by screen readers, whatever the 3D level. In 3D the scene draws
// the dot and this button only carries the label and the hit area.

import type { CSSProperties, Ref } from "react";
import { statusLabel } from "../../tracker/status";
import type { Placed } from "./layout";

interface Props {
  node: Placed;
  selected: boolean;
  /** Labels for every job get crowded: past ~14 jobs only strong fits keep theirs. */
  labeled: boolean;
  drawDot: boolean;
  onSelect(id: number): void;
  style?: CSSProperties;
  ref?: Ref<HTMLButtonElement>;
}

export function NodeButton({ node, selected, labeled, drawDot, onSelect, style, ref }: Props) {
  const { job } = node;
  const size = Math.round(12 + job.fit_score / 8);
  return (
    <button
      ref={ref}
      type="button"
      className={["galaxy-node", `node-${node.level}`, selected && "selected", (labeled || selected) && "labeled"]
        .filter(Boolean)
        .join(" ")}
      style={style}
      aria-pressed={selected}
      aria-label={`${job.company}, ${job.title}, fit ${job.fit_score}, ${statusLabel(job.status)}`}
      onClick={() => onSelect(job.id)}
    >
      <span className="galaxy-hit" aria-hidden="true">
        {drawDot && <span className="galaxy-dot" style={{ width: size, height: size }} />}
      </span>
      <span className="galaxy-label" aria-hidden="true">
        {job.company}
      </span>
    </button>
  );
}
