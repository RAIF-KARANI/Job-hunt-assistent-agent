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

function fromHash(): PageId {
  const id = window.location.hash.replace(/^#\/?/, "");
  return PAGES.some((p) => p.id === id) ? (id as PageId) : "dashboard";
}

export function useRoute(): PageId {
  const [page, setPage] = useState<PageId>(fromHash);
  useEffect(() => {
    const onChange = () => setPage(fromHash());
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  return page;
}
