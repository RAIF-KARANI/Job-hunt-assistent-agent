// Every line the agent prints, as it prints it.

import { useLayoutEffect, useRef } from "react";

function kind(line: string): string {
  const t = line.trim();
  if (/^\[\d\/5\]/.test(t)) return "log-step";
  if (t.startsWith("!") || t.startsWith("ERROR")) return "log-warn";
  return "";
}

export function LiveLog({ lines }: { lines: string[] }) {
  const box = useRef<HTMLDivElement>(null);
  const stick = useRef(true); // follow new lines unless you scrolled up to read

  useLayoutEffect(() => {
    const el = box.current;
    if (el && stick.current) el.scrollTop = el.scrollHeight;
  }, [lines]);

  const onScroll = () => {
    const el = box.current;
    if (el) stick.current = el.scrollHeight - el.scrollTop - el.clientHeight < 32;
  };

  return (
    <section className="log-card" aria-labelledby="log-title">
      <h2 id="log-title" className="eyebrow">
        Live log
      </h2>
      {/* aria-live off: a screen reader would read every line; the steps carry the news. */}
      <div ref={box} className="log" role="log" aria-live="off" tabIndex={0} onScroll={onScroll}>
        {lines.length === 0 ? (
          <span className="log-empty">The agent's log appears here while it works.</span>
        ) : (
          lines.map((line, i) => (
            <span key={i} className={kind(line)}>
              {line}
            </span>
          ))
        )}
      </div>
    </section>
  );
}
