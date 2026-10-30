// Follows Ollama's install and model downloads: Python streams
// `setup_progress` events while the (minutes-long) bridge call is running.

import { useEffect, useState } from "react";
import { onEvent } from "../bridge/bridge";
import type { SetupProgress } from "../bridge/types";

const MAX_LINES = 200;

export function useSetupProgress(what: SetupProgress["what"]) {
  const [latest, setLatest] = useState<SetupProgress | null>(null);
  const [lines, setLines] = useState<string[]>([]);

  useEffect(
    () =>
      onEvent((e) => {
        if (e.type !== "setup_progress" || e.what !== what) return;
        setLatest(e);
        // Download updates repeat the same message with new numbers: keep one line per message kind.
        setLines((old) => {
          const kind = e.message.split(":")[0];
          const next = old.length && old[old.length - 1].split(":")[0] === kind ? old.slice(0, -1) : old.slice(-MAX_LINES + 1);
          return [...next, e.message];
        });
      }),
    [what],
  );

  const reset = () => {
    setLatest(null);
    setLines([]);
  };
  return { latest, lines, reset };
}
