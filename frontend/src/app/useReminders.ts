import { useEffect, useState } from "react";
import { getApi, onEvent } from "../bridge/bridge";

/**
 * How many jobs are waiting for you: due a follow-up, or asking "Did you
 * apply?". For the number on Tracker in the sidebar (17c).
 *
 * The Tracker changes these without telling anyone else, so the count is
 * read again when a run finishes, when you move to another page, and when
 * the window gets the focus back.
 */
export function useReminders(): number {
  const [count, setCount] = useState(0);

  useEffect(() => {
    let alive = true;
    const load = () =>
      getApi()
        .then((api) => api.list_jobs())
        .then((jobs) => alive && setCount(jobs.filter((j) => j.follow_up || j.apply_ask).length))
        .catch(() => undefined); // the Tracker shows the error; a missing number is enough here
    load();
    const off = onEvent((e) => {
      if (e.type === "finished") load();
    });
    window.addEventListener("hashchange", load);
    window.addEventListener("focus", load);
    return () => {
      alive = false;
      off();
      window.removeEventListener("hashchange", load);
      window.removeEventListener("focus", load);
    };
  }, []);

  return count;
}
