import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

// Fonts are bundled (the app works offline): only the weights we use.
import "@fontsource/sora/600.css";
import "@fontsource/sora/700.css";
import "@fontsource/ibm-plex-sans/400.css";
import "@fontsource/ibm-plex-sans/500.css";
import "@fontsource/ibm-plex-sans/600.css";
import "@fontsource/ibm-plex-mono/400.css";

import "./styles/tokens.css";
import "./styles/base.css";
import "./styles/app.css";
import "./styles/controls.css";
import "./styles/analyze.css";
import { App } from "./app/App";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
