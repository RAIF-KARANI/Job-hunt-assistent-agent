# Third-party notices

JobLens itself is licensed under the MIT License (see `LICENSE`).

The downloadable JobLens app (`JobLens-Setup-*.exe` / the portable zip)
bundles the open-source components below. Their licenses apply to those
components. Versions are the ones used to build JobLens 0.3.0.

## Qt for Python (PySide6) — LGPL-3.0

JobLens' window uses **PySide6-Essentials 6.12.0** and **shiboken6 6.12.0**
(The Qt Company Ltd.), used under the **GNU Lesser General Public License
v3.0** (LGPL-3.0-only).

- Qt and PySide6 are shipped **unmodified**, as separate dynamic libraries
  (the `Qt6*.dll`, `PySide6\*.pyd` and `shiboken6` files inside the app's
  `_internal` folder). You may replace them with your own compatible build.
- Source code: https://code.qt.io/cgit/pyside/pyside-setup.git and
  https://download.qt.io/official_releases/QtForPython/
- License text: https://www.gnu.org/licenses/lgpl-3.0.html

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
| Matplotlib | 3.11.2 | Matplotlib License (PSF-based) |
| Pillow | 13.0.0 | MIT-CMU |
| Requests | 2.34.2 | Apache-2.0 |
| HTTPX | 0.28.1 | BSD-3-Clause |
| Beautiful Soup (`beautifulsoup4`) | 4.15.0 | MIT |
| lxml | 6.1.3 | BSD-3-Clause |
| pypdf | 6.21.2 | BSD-3-Clause |
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
