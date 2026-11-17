// How the Evals screen writes its numbers.

export const pct = (v: number | null) => (v === null ? "–" : `${Math.round(v * 100)}%`);
export const kilo = (n: number | null) => (n === null ? "–" : n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(Math.round(n)));
export const share = (part: number, whole: number) => (whole ? part / whole : null);
/** 16d: a cost in dollars: enough digits to tell a tenth of a cent from a cent. */
export const money = (v: number | null | undefined) =>
  v === null || v === undefined ? "–" : v >= 100 ? `$${Math.round(v)}` : v >= 0.1 ? `$${v.toFixed(2)}` : v >= 0.01 ? `$${v.toFixed(3)}` : `$${v.toFixed(4)}`;
export const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? "" : "s"}`;
