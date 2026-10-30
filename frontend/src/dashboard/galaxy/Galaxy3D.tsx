// 3D levels "animated" and "still" (D14). Loaded on demand (React.lazy),
// so with 3D off three.js is never even downloaded into the page.

import { useEffect, useLayoutEffect, useRef } from "react";
import type { Placed } from "./layout";
import { NodeButton } from "./NodeButton";
import { CORE_ID, GalaxyScene } from "./scene";

interface Props {
  nodes: Placed[]; // already in Tab order
  selectedId: number | null;
  labeled(node: Placed): boolean;
  onSelect(id: number): void;
  /** False = draw only when something changes (still level, agent running, reduced motion). */
  animate: boolean;
  onFail(message: string): void;
}

export default function Galaxy3D({ nodes, selectedId, labeled, onSelect, animate, onFail }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const scene = useRef<GalaxyScene | null>(null);
  const buttons = useRef(new Map<number, HTMLElement>());
  const latest = useRef({ nodes, selectedId, onFail });
  latest.current = { nodes, selectedId, onFail };

  useLayoutEffect(() => {
    const place = (id: number, x: number, y: number, near: number) => {
      const el = buttons.current.get(id);
      if (!el) return;
      el.style.transform = `translate(${x.toFixed(1)}px, ${y.toFixed(1)}px)`;
      el.style.setProperty("--near", near.toFixed(2));
      el.style.zIndex = String(10 + Math.round(near * 50));
      el.style.visibility = "visible";
    };
    try {
      scene.current = new GalaxyScene(host.current!, place, () =>
        latest.current.onFail("3D stopped working (the graphics driver was reset). Showing the flat map instead."),
      );
    } catch {
      latest.current.onFail("3D isn't available on this PC. Showing the flat map instead.");
      return;
    }
    const s = scene.current;
    s.setJobs(latest.current.nodes, latest.current.selectedId);

    // A theme switch changes the CSS colors the scene was built with.
    const observer = new MutationObserver(() => s.recolor(latest.current.nodes, latest.current.selectedId));
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    return () => {
      observer.disconnect();
      s.dispose();
      scene.current = null;
    };
  }, []);

  useEffect(() => scene.current?.setJobs(nodes, latest.current.selectedId), [nodes]);
  useEffect(() => scene.current?.setSelected(selectedId), [selectedId]);
  useEffect(() => scene.current?.setAnimate(animate), [animate]);

  const keep = (id: number) => (el: HTMLElement | null) => {
    if (el) buttons.current.set(id, el);
    else buttons.current.delete(id);
  };

  return (
    <div className="galaxy-3d" ref={host}>
      <div className="galaxy-overlay">
        <span ref={keep(CORE_ID)} className="galaxy-core floating" aria-hidden="true">
          You
        </span>
        {nodes.map((node) => (
          <NodeButton
            key={node.job.id}
            ref={keep(node.job.id)}
            node={node}
            selected={node.job.id === selectedId}
            labeled={labeled(node)}
            drawDot={false}
            onSelect={onSelect}
          />
        ))}
      </div>
      <div className="galaxy-zoom" role="group" aria-label="View">
        <button type="button" className="btn btn-secondary btn-sm" aria-label="Zoom in" onClick={() => scene.current?.zoom(0.85)}>
          +
        </button>
        <button type="button" className="btn btn-secondary btn-sm" aria-label="Zoom out" onClick={() => scene.current?.zoom(1.18)}>
          −
        </button>
        <button type="button" className="btn btn-secondary btn-sm" onClick={() => scene.current?.resetView()}>
          Reset
        </button>
      </div>
    </div>
  );
}
