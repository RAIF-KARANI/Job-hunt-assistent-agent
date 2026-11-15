// 16d: three more charts for Evals, all from the run log.
//   RunLine     one number per run, oldest left (tokens; agent time)
//   RunScatter  agent time against tokens: one dot per run
//   ModelTrend  evidence pass rate over time, one line per model (4 at most)
// Drawn in real pixels like PassRateChart (the width is measured), so text
// stays 12 px at any window size. Every chart has one y axis, a hover
// tooltip with a hit area bigger than the mark, and a hidden table that
// gives screen readers the same numbers.

import { useEffect, useRef, useState, type MouseEvent } from "react";
import type { EvalsData } from "../bridge/types";
import { parseUtc } from "../tracker/status";

const HEIGHT = 220;
const PAD = { left: 52, right: 16, top: 16, bottom: 30 };
const day = (s: string) => parseUtc(s).toLocaleDateString(undefined, { day: "numeric", month: "short" });
const moment = (s: string) => parseUtc(s).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });

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

/** A round number at or above `value` for the top of an axis (1, 2, 2.5, 5 x a power of ten). */
export function niceMax(value: number): number {
  if (!(value > 0)) return 1;
  const power = 10 ** Math.floor(Math.log10(value));
  return [1, 2, 2.5, 5, 10].map((step) => step * power).find((top) => top >= value) ?? 10 * power;
}

/** The top of a time axis, in seconds: a round number of minutes ("10 min", not "16m 40s"). */
export function niceMinutes(seconds: number): number {
  const minutes = Math.max(seconds, 1) / 60;
  return 60 * ([1, 2, 5, 10, 15, 20, 30, 45, 60].find((top) => top >= minutes) ?? niceMax(minutes));
}

/** Pearson's r, or null with fewer than 3 points or no spread. */
export function correlation(xs: number[], ys: number[]): number | null {
  const n = xs.length;
  if (n < 3) return null;
  const mean = (v: number[]) => v.reduce((a, b) => a + b, 0) / n;
  const mx = mean(xs);
  const my = mean(ys);
  let sxy = 0;
  let sxx = 0;
  let syy = 0;
  for (let i = 0; i < n; i++) {
    sxy += (xs[i] - mx) * (ys[i] - my);
    sxx += (xs[i] - mx) ** 2;
    syy += (ys[i] - my) ** 2;
  }
  return sxx && syy ? sxy / Math.sqrt(sxx * syy) : null;
}

type Point = EvalsData["run_points"][number];

interface LineProps {
  points: Point[];
  value(p: Point): number;
  format(v: number): string;
  /** The axis labels, if they should be shorter than `format` ("50k", "5 min"). */
  axis?(v: number): string;
  /** The top of the y axis for the largest value (default: a round number above it). */
  top?(max: number): number;
  /** What the number is, for the tooltip and the table ("tokens", "of agent time"). */
  unit: string;
  /** Extra tooltip lines for a run. */
  detail?(p: Point): string;
  caption: string;
}

export function RunLine({ points, value, format, axis = format, top: topOf = niceMax, unit, detail, caption }: LineProps) {
  const [box, width] = useWidth<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);

  const values = points.map(value);
  const top = topOf(Math.max(0, ...values));
  const plotW = Math.max(0, width - PAD.left - PAD.right);
  const plotH = HEIGHT - PAD.top - PAD.bottom;
  const x = (i: number) => PAD.left + (points.length > 1 ? (i / (points.length - 1)) * plotW : plotW / 2);
  const y = (v: number) => PAD.top + (1 - v / top) * plotH;
  const path = values.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  const last = points.length - 1;
  const tip = hover !== null ? points[hover] : null;

  /** The run nearest to the pointer: you aim at a column, not at a 7 px dot. */
  const track = (e: MouseEvent<SVGSVGElement>) => {
    if (!points.length) return;
    const at = e.clientX - e.currentTarget.getBoundingClientRect().left;
    const i = points.length > 1 ? Math.round(((at - PAD.left) / plotW) * last) : 0;
    setHover(Math.min(last, Math.max(0, i)));
  };

  return (
    <div className="line-chart" ref={box}>
      {width > 0 && (
        <svg width={width} height={HEIGHT} aria-hidden="true" onMouseMove={track} onMouseLeave={() => setHover(null)}>
          {[0, 0.5, 1].map((g) => (
            <g key={g}>
              <line className={g === 0 ? "axis" : "grid"} x1={PAD.left} x2={width - PAD.right} y1={y(g * top)} y2={y(g * top)} />
              <text className="tick" x={PAD.left - 8} y={y(g * top) + 4} textAnchor="end">
                {axis(g * top)}
              </text>
            </g>
          ))}
          {hover !== null && <line className="crosshair" x1={x(hover)} x2={x(hover)} y1={PAD.top} y2={y(0)} />}
          <polyline className="line" points={path} />
          {points.map((p, i) => (
            <circle key={p.run_id} className={i === last || i === hover ? "dot active" : "dot"} cx={x(i)} cy={y(values[i])} r={i === last || i === hover ? 5 : 3} />
          ))}
          {last >= 0 && hover === null && (
            <text className="value-label" x={x(last)} y={y(values[last]) - 12} textAnchor={points.length > 1 ? "end" : "middle"}>
              {format(values[last])}
            </text>
          )}
          {points.length > 1 && (
            <>
              <text className="tick" x={PAD.left} y={HEIGHT - 8}>
                {day(points[0].started_at)}
              </text>
              <text className="tick" x={width - PAD.right} y={HEIGHT - 8} textAnchor="end">
                latest
              </text>
            </>
          )}
        </svg>
      )}
      {tip && hover !== null && (
        <div className={x(hover) > width - 130 ? "chart-tip left" : "chart-tip"} style={{ left: x(hover), top: y(values[hover]) }} role="presentation">
          <span>
            <strong>{format(values[hover])}</strong> {unit}
          </span>
          {detail && <span>{detail(tip)}</span>}
          <span>
            {moment(tip.started_at)} · {tip.model}
          </span>
        </div>
      )}
      <table className="sr-only">
        <caption>{caption}, oldest run first</caption>
        <thead>
          <tr>
            <th>Run started</th>
            <th>Model</th>
            <th>{unit}</th>
          </tr>
        </thead>
        <tbody>
          {points.map((p, i) => (
            <tr key={p.run_id}>
              <td>{parseUtc(p.started_at).toLocaleString()}</td>
              <td>{p.model}</td>
              <td>{format(values[i])}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

interface ScatterProps {
  points: Point[];
  formatTokens(v: number): string;
  formatTime(v: number): string;
  /** Shorter labels for the two axes. */
  axisTokens(v: number): string;
  axisTime(v: number): string;
}

export function RunScatter({ points, formatTokens, formatTime, axisTokens, axisTime }: ScatterProps) {
  const [box, width] = useWidth<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);

  const tokens = points.map((p) => p.tokens_in + p.tokens_out);
  const topX = niceMax(Math.max(0, ...tokens));
  const topY = niceMinutes(Math.max(0, ...points.map((p) => p.seconds)));
  const height = HEIGHT + 18; // room for the x axis title
  const plotW = Math.max(0, width - PAD.left - PAD.right);
  const plotH = HEIGHT - PAD.top - PAD.bottom;
  const x = (v: number) => PAD.left + (v / topX) * plotW;
  const y = (v: number) => PAD.top + (1 - v / topY) * plotH;
  const tip = hover !== null ? points[hover] : null;

  return (
    <div className="line-chart" ref={box}>
      {width > 0 && (
        <svg width={width} height={height} aria-hidden="true" onMouseLeave={() => setHover(null)}>
          {[0, 0.5, 1].map((g) => (
            <g key={g}>
              <line className={g === 0 ? "axis" : "grid"} x1={PAD.left} x2={width - PAD.right} y1={y(g * topY)} y2={y(g * topY)} />
              <text className="tick" x={PAD.left - 8} y={y(g * topY) + 4} textAnchor="end">
                {axisTime(g * topY)}
              </text>
              <text className="tick" x={x(g * topX)} y={HEIGHT - 8} textAnchor={g === 0 ? "start" : g === 1 ? "end" : "middle"}>
                {axisTokens(g * topX)}
              </text>
            </g>
          ))}
          <text className="tick axis-title" x={PAD.left + plotW / 2} y={height - 4} textAnchor="middle">
            tokens in the run
          </text>
          {points.map((p, i) => (
            <g key={p.run_id} onMouseEnter={() => setHover(i)}>
              <circle className={i === hover ? "dot active" : "dot"} cx={x(tokens[i])} cy={y(p.seconds)} r={i === hover ? 6 : 4.5} />
              {/* A hit area bigger than the dot. */}
              <circle className="hit" cx={x(tokens[i])} cy={y(p.seconds)} r={12} />
            </g>
          ))}
        </svg>
      )}
      {tip && hover !== null && (
        <div className={x(tokens[hover]) > width - 130 ? "chart-tip left" : "chart-tip"} style={{ left: x(tokens[hover]), top: y(tip.seconds) }} role="presentation">
          <span>
            <strong>{formatTime(tip.seconds)}</strong> for <strong>{formatTokens(tokens[hover])}</strong> tokens
          </span>
          <span>
            {formatTokens(tip.tokens_in)} in · {formatTokens(tip.tokens_out)} out
          </span>
          <span>
            {moment(tip.started_at)} · {tip.model}
          </span>
        </div>
      )}
      <table className="sr-only">
        <caption>Agent time and tokens of each run</caption>
        <thead>
          <tr>
            <th>Run started</th>
            <th>Model</th>
            <th>Tokens</th>
            <th>Agent time</th>
          </tr>
        </thead>
        <tbody>
          {points.map((p, i) => (
            <tr key={p.run_id}>
              <td>{parseUtc(p.started_at).toLocaleString()}</td>
              <td>{p.model}</td>
              <td>{tokens[i]}</td>
              <td>{formatTime(p.seconds)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const pct = (v: number) => `${Math.round(v * 100)}%`;

export function ModelTrend({ series }: { series: EvalsData["model_trend"] }) {
  const [box, width] = useWidth<HTMLDivElement>();
  const [hover, setHover] = useState<{ s: number; i: number } | null>(null);

  // Runs in the order they happened, evenly spaced (like the other charts). A real time
  // axis put ten runs of one evening on top of each other and left a week of nothing.
  const order = series.flatMap((m) => m.points).sort((a, b) => a.started_at.localeCompare(b.started_at));
  const place = new Map(order.map((p, i) => [p.run_id, i]));
  const times = order.map((p) => p.started_at);
  const plotW = Math.max(0, width - PAD.left - PAD.right);
  const plotH = HEIGHT - PAD.top - PAD.bottom;
  const x = (p: { run_id: string }) => PAD.left + (order.length > 1 ? ((place.get(p.run_id) ?? 0) / (order.length - 1)) * plotW : plotW / 2);
  const y = (rate: number) => PAD.top + (1 - rate) * plotH;
  const tip = hover ? series[hover.s].points[hover.i] : null;

  return (
    <div className="line-chart" ref={box}>
      {/* One line needs no legend: the card's text names it. Two or more always get one. */}
      {series.length > 1 && (
        <ul className="chart-legend" aria-label="Models">
          {series.map((m, s) => (
            <li key={m.model}>
              <i className={`legend-swatch series-${s + 1}`} aria-hidden="true" />
              <span className="mono">{m.model}</span>
              <span className="hint">{m.runs} runs</span>
            </li>
          ))}
        </ul>
      )}
      {width > 0 && times.length > 0 && (
        <svg width={width} height={HEIGHT} aria-hidden="true" onMouseLeave={() => setHover(null)}>
          {[0, 0.5, 1].map((g) => (
            <g key={g}>
              <line className={g === 0 ? "axis" : "grid"} x1={PAD.left} x2={width - PAD.right} y1={y(g)} y2={y(g)} />
              <text className="tick" x={PAD.left - 8} y={y(g) + 4} textAnchor="end">
                {pct(g)}
              </text>
            </g>
          ))}
          {series.map((m, s) => (
            <polyline key={m.model} className={`line series-${s + 1}`} points={m.points.map((p) => `${x(p).toFixed(1)},${y(p.rate).toFixed(1)}`).join(" ")} />
          ))}
          {series.map((m, s) =>
            m.points.map((p, i) => {
              const on = hover?.s === s && hover.i === i;
              return (
                <g key={p.run_id} onMouseEnter={() => setHover({ s, i })}>
                  <circle className={`dot series-${s + 1}${on ? " active" : ""}`} cx={x(p)} cy={y(p.rate)} r={on ? 5.5 : 4} />
                  <circle className="hit" cx={x(p)} cy={y(p.rate)} r={12} />
                </g>
              );
            }),
          )}
          {order.length > 1 && (
            <>
              <text className="tick" x={PAD.left} y={HEIGHT - 8}>
                {day(times[0])}
              </text>
              <text className="tick" x={width - PAD.right} y={HEIGHT - 8} textAnchor="end">
                latest
              </text>
            </>
          )}
        </svg>
      )}
      {tip && hover && (
        <div className={x(tip) > width - 130 ? "chart-tip left" : "chart-tip"} style={{ left: x(tip), top: y(tip.rate) }} role="presentation">
          <span>
            <strong>{pct(tip.rate)}</strong> of claims held up
          </span>
          <span className="mono">{series[hover.s].model}</span>
          <span>{moment(tip.started_at)}</span>
        </div>
      )}
      <table className="sr-only">
        <caption>Evidence pass rate per run, by model</caption>
        <thead>
          <tr>
            <th>Model</th>
            <th>Run started</th>
            <th>Pass rate</th>
          </tr>
        </thead>
        <tbody>
          {series.flatMap((m) =>
            m.points.map((p) => (
              <tr key={p.run_id}>
                <td>{m.model}</td>
                <td>{parseUtc(p.started_at).toLocaleString()}</td>
                <td>{pct(p.rate)}</td>
              </tr>
            )),
          )}
        </tbody>
      </table>
    </div>
  );
}
