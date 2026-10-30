import { useEffect, useState } from "react";

/** "8s", "1m 19s", "12m" */
export function formatDuration(ms: number): string {
  const s = Math.max(0, Math.round(ms / 1000));
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  return m >= 10 ? `${m}m` : `${m}m ${s % 60}s`;
}

/** Date.now(), refreshed every second while `active` (for live timers). */
export function useNow(active: boolean): number {
  const [now, setNow] = useState(Date.now);
  useEffect(() => {
    if (!active) return;
    setNow(Date.now());
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [active]);
  return now;
}
