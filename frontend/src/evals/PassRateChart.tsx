// Evidence pass rate, one point per run (oldest left). Drawn in real pixels
// (the width is measured), so the text stays 12 px at any window size.
// Hover a point for its run; a hidden table gives screen readers the same.

import { useEffect, useRef, useState } from "react";
import type { EvalsData } from "../bridge/types";
import { parseUtc } from "../tracker/status";

const HEIGHT = 220;
const PAD = { left: 44, right: 16, top: 16, bottom: 30 };
const pct = (v: number) => `${Math.round(v * 100)}%`;
const when = (s: string) => parseUtc(s).toLocaleDateString(undefined, { day: "numeric", month: "short" });

function useWidth<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [width, setWidth] = useState(0);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const observer = new ResizeObserver(() => setWidth(el.clientWidth));
    observer.observe(el);
    return () => observer.disconnect();
  }, []);
  return [ref, width] as const;
}

export function PassRateChart({ trend }: { trend: EvalsData["trend"] }) {
  const [box, width] = useWidth<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);

  const plotW = Math.max(0, width - PAD.left - PAD.right);
  const plotH = HEIGHT - PAD.top - PAD.bottom;
  const x = (i: number) => PAD.left + (trend.length > 1 ? (i / (trend.length - 1)) * plotW : plotW / 2);
  const y = (rate: number) => PAD.top + (1 - rate) * plotH;
  const points = trend.map((t, i) => `${x(i).toFixed(1)},${y(t.rate).toFixed(1)}`).join(" ");
  const last = trend.length - 1;
  const tip = hover !== null ? trend[hover] : null;

  return (
    <div className="line-chart" ref={box}>
      {width > 0 && (
        <svg width={width} height={HEIGHT} aria-hidden="true" onMouseLeave={() => setHover(null)}>
          {[0, 0.5, 1].map((g) => (
            <g key={g}>
              <line className={g === 0 ? "axis" : "grid"} x1={PAD.left} x2={width - PAD.right} y1={y(g)} y2={y(g)} />
              <text className="tick" x={PAD.left - 8} y={y(g) + 4} textAnchor="end">
                {pct(g)}
              </text>
            </g>
          ))}
          {trend.length > 1 && (
            <polygon className="line-area" points={`${x(0)},${y(0)} ${points} ${x(last)},${y(0)}`} />
          )}
          <polyline className="line" points={points} />
          {trend.map((t, i) => (
            <g key={t.run_id} onMouseEnter={() => setHover(i)}>
              <circle className={i === last || i === hover ? "dot active" : "dot"} cx={x(i)} cy={y(t.rate)} r={i === last || i === hover ? 5 : 3.5} />
              {/* A hit area bigger than the dot. */}
              <circle className="hit" cx={x(i)} cy={y(t.rate)} r={12} />
            </g>
          ))}
          {last >= 0 && hover === null && (
            <text className="value-label" x={x(last)} y={y(trend[last].rate) - 12} textAnchor={trend.length > 1 ? "end" : "middle"}>
              {pct(trend[last].rate)}
            </text>
          )}
          {trend.length > 1 && (
            <>
              <text className="tick" x={PAD.left} y={HEIGHT - 8}>
                {when(trend[0].started_at)}
              </text>
              <text className="tick" x={width - PAD.right} y={HEIGHT - 8} textAnchor="end">
                latest
              </text>
            </>
          )}
        </svg>
      )}
      {tip && hover !== null && (
        <div className={x(hover) > width - 120 ? "chart-tip left" : "chart-tip"} style={{ left: x(hover), top: y(tip.rate) }} role="presentation">
          <strong>{pct(tip.rate)}</strong> of claims held up
          <span>{parseUtc(tip.started_at).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })}</span>
        </div>
      )}
      <table className="sr-only">
        <caption>Evidence pass rate per run, oldest first</caption>
        <thead>
          <tr>
            <th>Run started</th>
            <th>Pass rate</th>
          </tr>
        </thead>
        <tbody>
          {trend.map((t) => (
            <tr key={t.run_id}>
              <td>{parseUtc(t.started_at).toLocaleString()}</td>
              <td>{pct(t.rate)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
