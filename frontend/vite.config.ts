import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The build is plain static files that the Python app shows in its window
// (desktop_web/app.py). `base: "./"` keeps every path relative, so it works
// from pywebview's local server and from inside the installed app.
export default defineConfig({
  plugins: [react()],
  base: "./",
  build: {
    outDir: "../desktop_web/web",
    emptyOutDir: true,
    target: "es2022", // WebView2 is current Chromium
  },
  server: { port: 5173, strictPort: true },
});
