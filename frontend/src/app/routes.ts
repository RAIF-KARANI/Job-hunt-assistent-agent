import { useEffect, useState } from "react";
import type { IconName } from "./Icon";

// Pages live in the URL hash (#/tracker): no router library needed, and the
// page survives a reload (F5) inside the window.
export const PAGES = [
  { id: "dashboard", label: "Dashboard", icon: "dashboard", group: "search" },
  { id: "analyze", label: "Analyze", icon: "analyze", group: "search" },
  { id: "tracker", label: "Tracker", icon: "tracker", group: "search" },
  { id: "insights", label: "Insights", icon: "insights", group: "search" }, // 19c
  { id: "evals", label: "Evals", icon: "evals", group: "agent" },
  { id: "settings", label: "Settings", icon: "settings", group: "agent" },
] as const satisfies readonly { id: string; label: string; icon: IconName; group: string }[];

/** 17c: the sidebar's two groups. "Agent" folds away until you need it. */
export const NAV_GROUPS = [
  { id: "search", label: "Job search", folds: false },
  { id: "agent", label: "Agent", folds: true },
] as const;

export type PageId = (typeof PAGES)[number]["id"];
/** A page, the setup wizard (#/setup: full screen, not in the sidebar), or
 *  the component sheet (#/components: for checking the look, 17b). */
export type Route = PageId | "setup" | "components";

/** 16a: a page may carry values after "?", e.g. #/tracker?job=12. */
function hashParts(): { id: string; query: string } {
  const [id, query = ""] = window.location.hash.replace(/^#\/?/, "").split("?");
  return { id, query };
}

/** The value of `name` in the hash (#/tracker?job=12 -> "12"), or null. */
export function hashParam(name: string): string | null {
  return new URLSearchParams(hashParts().query).get(name);
}

function fromHash(): Route {
  const { id } = hashParts();
  return id === "setup" || id === "components" || PAGES.some((p) => p.id === id) ? (id as Route) : "dashboard";
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
