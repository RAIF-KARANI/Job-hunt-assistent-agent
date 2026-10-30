// 3D level "off" (D14): the galaxy seen from above, as flat SVG. Same
// positions, same buttons, no WebGL and no animation, so it costs nothing.

import { RINGS, type Placed } from "./layout";
import { NodeButton } from "./NodeButton";

interface Props {
  nodes: Placed[]; // already in Tab order
  selectedId: number | null;
  labeled(node: Placed): boolean;
  onSelect(id: number): void;
}

const SPREAD = 46; // % of the map's half-width used by the outer ring

export function OrbitMap({ nodes, selectedId, labeled, onSelect }: Props) {
  return (
    <div className="orbit-map">
      <svg className="orbit-rings" viewBox="-50 -50 100 100" aria-hidden="true">
        {RINGS.map((r, i) => (
          <circle key={r} className={`ring ring-${i}`} r={r * SPREAD} />
        ))}
      </svg>
      <span className="galaxy-core" aria-hidden="true">
        You
      </span>
      {nodes.map((node) => (
        <NodeButton
          key={node.job.id}
          node={node}
          selected={node.job.id === selectedId}
          labeled={labeled(node)}
          drawDot
          onSelect={onSelect}
          style={{ left: `${50 + node.x * SPREAD}%`, top: `${50 + node.z * SPREAD}%` }}
        />
      ))}
    </div>
  );
}
