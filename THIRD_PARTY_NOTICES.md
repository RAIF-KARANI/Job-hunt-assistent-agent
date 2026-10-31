# Third-party notices

JobLens itself is licensed under the MIT License (see `LICENSE`).

The downloadable JobLens app (`JobLens-Setup-*.exe`) bundles the
open-source components below. Their licenses apply to those components.
Versions are the ones used for the version-2 build (web UI, since step 12h).

Since version 2 the app no longer contains Qt / PySide6 or Matplotlib: the
window is a web page shown by Microsoft Edge WebView2.

## The tray icon: pystray — LGPL-3.0

The tray icon uses **pystray 0.19.5** (Moses Palmér), used under the **GNU
Lesser General Public License v3.0** (LGPL-3.0). The full license texts
(`COPYING` = GPL-3.0, `COPYING.LGPL` = LGPL-3.0) ship with the app in
`_internal\pystray-0.19.5.dist-info\`.

- pystray is shipped **unmodified**, as plain Python source files in the
  app's `_internal\pystray\` folder (not inside the compressed archive), so
  you may replace them with your own compatible version.
- Source code: https://github.com/moses-palmer/pystray
- License text: https://www.gnu.org/licenses/lgpl-3.0.html

pystray needs **Pillow** (MIT-CMU license) and **six** (MIT), both bundled.

## The window: pywebview + Microsoft Edge WebView2

| Component | Version | License |
|---|---|---|
| pywebview | 6.2.1 | BSD-3-Clause |
| pythonnet, clr_loader | 3.2.1 / 0.3.1 | MIT |
| bottle, proxy_tools | 0.13.4 / 0.1.0 | MIT |
| Microsoft.Web.WebView2 SDK DLLs (inside pywebview) | as shipped by pywebview | Microsoft WebView2 SDK license (redistributable): https://www.nuget.org/packages/Microsoft.Web.WebView2 |

**Microsoft Edge WebView2 Runtime** is not part of JobLens. It comes with
Windows 11; on a PC without it, the installer runs Microsoft's WebView2
bootstrapper (`MicrosoftEdgeWebview2Setup.exe`, signed by Microsoft,
distributed under Microsoft's WebView2 distribution terms:
https://developer.microsoft.com/microsoft-edge/webview2/), which downloads
and installs the runtime from Microsoft.

## The user interface (built into `_internal\desktop_web\web\`)

| Component | Version | License |
|---|---|---|
| React, React DOM (incl. `scheduler`) | 19.3.1 | MIT, © Meta Platforms, Inc. and affiliates |
| three.js | 0.186.1 | MIT, © 2010–2026 three.js authors |
| Sora (font, via Fontsource) | 5.3.0 | SIL Open Font License 1.1 |
| IBM Plex Sans, IBM Plex Mono (fonts, via Fontsource) | 5.3.0 | SIL Open Font License 1.1, © IBM Corp. |

The fonts may be used, bundled and redistributed under the SIL Open Font
License 1.1 (https://openfontlicense.org); they are not sold on their own.

## Python

The app embeds the CPython 3.13 interpreter (Python Software Foundation
License). https://docs.python.org/3/license.html

## Other bundled libraries

| Component | Version | License |
|---|---|---|
| LangChain (`langchain`, `langchain-core`) | 1.4.7 / 1.7.0 | MIT |
| LangGraph (`langgraph`, `langgraph-checkpoint-sqlite`) | 1.2.18 / 3.1.2 | MIT |
| `langchain-ollama`, `ollama` | 1.1.0 / 0.6.3 | MIT |
| `langchain-anthropic`, `anthropic` | 1.7.6 / 1.17.0 | MIT |
| `langfuse` | 5.0.4 | MIT |
| Pydantic | 2.14.1 | MIT |
| pandas | 3.1.0 | BSD-3-Clause |
| NumPy | 2.5.4 | BSD-3-Clause (and bundled 0BSD, MIT, Zlib, CC0-1.0 parts) |
| Requests | 2.34.2 | Apache-2.0 |
| HTTPX | 0.28.1 | BSD-3-Clause |
| Beautiful Soup (`beautifulsoup4`) | 4.15.0 | MIT |
| lxml | 6.1.3 | BSD-3-Clause |
| pypdf | 6.21.2 | BSD-3-Clause |
| ReportLab (PDF export) | 5.1.0 | BSD-3-Clause, © ReportLab Europe Ltd. |
| `ddgs` (DuckDuckGo search) | 9.16.1 | MIT |
| `primp` | 2.0.1 | MIT |
| python-dotenv | 1.2.4 | BSD-3-Clause |

Smaller transitive dependencies are included under their own permissive
licenses; their license files are kept in the app's `_internal\*.dist-info`
folders where the package provides them.

## Not bundled

- **Ollama** and the AI models (e.g. Qwen3) are **not** part of JobLens.
  The setup wizard installs Ollama via winget and downloads models from
  Ollama's library; they are governed by their own licenses (Ollama: MIT;
  Qwen3: Apache-2.0).
- The optional **Claude API** is a service under Anthropic's terms.
- **Langfuse** (optional developer tracing) runs separately via Docker.
