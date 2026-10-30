import { useEffect, useState } from "react";
import type { IconName } from "./Icon";

// Pages live in the URL hash (#/tracker): no router library needed, and the
// page survives a reload (F5) inside the window.
export const PAGES = [
  { id: "dashboard", label: "Dashboard", icon: "dashboard" },
  { id: "analyze", label: "Analyze", icon: "analyze" },
  { id: "tracker", label: "Tracker", icon: "tracker" },
  { id: "evals", label: "Evals", icon: "evals" },
  { id: "settings", label: "Settings", icon: "settings" },
] as const satisfies readonly { id: string; label: string; icon: IconName }[];

export type PageId = (typeof PAGES)[number]["id"];
/** A page, or the setup wizard (#/setup: full screen, not in the sidebar). */
export type Route = PageId | "setup";

function fromHash(): Route {
  const id = window.location.hash.replace(/^#\/?/, "");
  return id === "setup" || PAGES.some((p) => p.id === id) ? (id as Route) : "dashboard";
}

export function useRoute(): Route {
  const [page, setPage] = useState<Route>(fromHash);
  useEffect(() => {
    const onChange = () => setPage(fromHash());
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  return page;
}
