// Your ratings (human eval): one stacked bar per question. Each part has
// its name and count written in the legend, so color is never the only cue.

import type { EvalsData } from "../bridge/types";

// Good -> mixed -> bad, in the same three colors for both questions.
const ORDER: Record<string, { title: string; parts: { rating: string; color: string }[] }> = {
  fit_score: {
    title: "Fit score",
    parts: [
      { rating: "about right", color: "var(--rate-good)" },
      { rating: "too high", color: "var(--rate-mixed)" },
      { rating: "too low", color: "var(--rate-bad)" },
    ],
  },
  cover_note: {
    title: "Cover note",
    parts: [
      { rating: "usable as is", color: "var(--rate-good)" },
      { rating: "needed edits", color: "var(--rate-mixed)" },
      { rating: "not usable", color: "var(--rate-bad)" },
    ],
  },
};

export function Ratings({ ratings }: { ratings: EvalsData["ratings"] }) {
  const count = (aspect: string, rating: string) => ratings.find((r) => r.aspect === aspect && r.rating === rating)?.count ?? 0;
  return (
    <div className="ratings">
      {Object.entries(ORDER).map(([aspect, { title, parts }]) => {
        const counts = parts.map((p) => ({ ...p, n: count(aspect, p.rating) }));
        const total = counts.reduce((sum, p) => sum + p.n, 0);
        return (
          <div key={aspect} className="rating">
            <div className="rating-head">
              <h3>{title}</h3>
              <span className="hint">{total ? `${total} rated` : "not rated yet"}</span>
            </div>
            <div className="stack" aria-hidden="true">
              {total ? (
                counts
                  .filter((p) => p.n)
                  .map((p) => (
                    <span key={p.rating} className="stack-part" style={{ flexGrow: p.n, background: p.color }} title={`${p.rating}: ${p.n}`} />
                  ))
              ) : (
                <span className="stack-empty" />
              )}
            </div>
            <ul className="legend">
              {counts.map((p) => (
                <li key={p.rating}>
                  <span className="legend-swatch" style={{ background: p.color }} aria-hidden="true" />
                  {p.rating} · {p.n}
                </li>
              ))}
            </ul>
          </div>
        );
      })}
      <p className="hint">Cover-note ratings are pre-filled from what you did: approved as is, edited, or rejected.</p>
    </div>
  );
}
