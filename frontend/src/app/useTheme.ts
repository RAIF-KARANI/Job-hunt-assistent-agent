import { useEffect, useState } from "react";
import type { Theme } from "../bridge/types";

const darkQuery = () => window.matchMedia("(prefers-color-scheme: dark)");

/** Applies the theme to <html data-theme>; "system" follows Windows and updates live. */
export function useTheme(theme: Theme): "dark" | "light" {
  const [systemDark, setSystemDark] = useState(() => darkQuery().matches);

  useEffect(() => {
    const query = darkQuery();
    const onChange = () => setSystemDark(query.matches);
    query.addEventListener("change", onChange);
    return () => query.removeEventListener("change", onChange);
  }, []);

  const resolved = theme === "system" ? (systemDark ? "dark" : "light") : theme;
  useEffect(() => {
    document.documentElement.dataset.theme = resolved;
  }, [resolved]);
  return resolved;
}
