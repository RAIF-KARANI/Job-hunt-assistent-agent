# JobLens — Handover

Everything needed to **run, change, build, release and continue** JobLens.
For *what* it is and the results, see `report.md`; for *how each part was
built and why*, see `progress.md`; for the design, `architecture.md`.

**State at handover (29 Oct 2026):** version **0.3.0**, all phases 0–11
done, 92 tests passing, working tree clean, latest release **v0.3.0**,
repository **private**.

---

## 1. Prerequisites (developer machine)

| Tool | Why | Install |
|---|---|---|
| Windows 10/11 64-bit | target platform | — |
| Python 3.11+ (built with 3.13) | the app | python.org |
| Ollama + `qwen3:8b` | local LLM | ollama.com · `ollama pull qwen3:8b` |
| Git + GitHub CLI (`gh`) | code + releases | `gh auth login` |
| Inno Setup 6 | build the installer | `winget install JRSoftware.InnoSetup` |
| Docker Desktop *(optional)* | Langfuse tracing only | docker.com |

---

## 2. Setup from a fresh clone

```powershell
git clone https://github.com/RAIF-KARANI/Job-hunt-assistent-agent
cd Job-hunt-assistent-agent
python -m venv .venv
.venv\Scripts\activate          # EVERY new terminal (cmd: .venv\Scripts\activate.bat)
pip install -r requirements.txt
copy .env.example .env          # then edit if needed
mkdir data                      # put resume PDFs here
python -m pytest                # expect: 92 passed
```

> Without the venv activated you'll see `No module named 'langgraph'`.

---

## 3. Running it

| What | Command |
|---|---|
| Desktop app (from source) | `python desktop_app.py` |
| CLI | `python main.py <job-url>` · `list` · `show <id>` · `status <id> applied` · `rescore` · `graph` |
| Web UI | `streamlit run app.py` (port 8501) |
| Monitoring dashboard (Langfuse) | `streamlit run monitor.py --server.port 8502` |
| Compare models | `python compare_models.py <job-id> qwen3:8b qwen3:14b` |
| Self-test a build | `dist\JobLens\JobLens.exe --self-test report.txt` |

---

## 4. Configuration (`.env`)

| Key | Default | Meaning |
|---|---|---|
| `LLM_PROVIDER` | `ollama` | `ollama` · `anthropic` · `openai` · `google` |
| `LLM_MODEL` | `qwen3:8b` | e.g. `qwen3:14b`, `claude-haiku-5-5` |
| `LLM_TEMPERATURE` | `0.2` | |
| `OLLAMA_NUM_CTX` | `16384` | too small silently truncates text |
| `OLLAMA_REASONING` | `false` | Qwen3 thinking mode |
| `JUDGE_EVIDENCE` | `true` | LLM-as-judge on skill evidence |
| `TRACING` | `off` | `off` · `langfuse` · `langsmith` (read at startup: restart after changing) |
| `ANTHROPIC_API_KEY` | — | only for the Claude provider |
| `LANGFUSE_HOST/PUBLIC_KEY/SECRET_KEY` | — | only for `TRACING=langfuse` |
| `SETUP_DONE` | — | set by the setup wizard |

The developer `.env` currently has `TRACING=langfuse` while Langfuse is
stopped; set it to `off` (Settings tab or `.env`) unless Langfuse is running.

---

## 5. Where data lives

| Mode | Settings | Data (resumes, `jobs.db`, `checkpoints.db`, `cover_notes/`) |
|---|---|---|
| Developer (from source) | `<repo>\.env` | `<repo>\data\` |
| Installed app | `%LOCALAPPDATA%\JobLens\.env` | `%LOCALAPPDATA%\JobLens\data\` |
| Override (tests, 2nd profile) | `JOB_HUNT_HOME=<folder>` | `<folder>\data\` |

`jobs.db` holds the tracker **and** the run log tables (`runs`, `run_steps`,
`run_llm_calls`, `run_quality`, `run_feedback`). Decided in `job_agent/paths.py`.

**Never committed (git-ignored):** `.env`, `data/`, `infra/langfuse/.env`,
`build/`, `dist/`, `.venv/`.

---

## 6. Codebase map

```
job_agent/        the agent (no UI code)
  graph.py          main LangGraph workflow (+ cover-note subgraph)
  posting.py fit.py research.py cover_note.py tracker.py   the steps
  models.py         Pydantic schemas      llm.py      model factory, retries, llm_status()
  paths.py settings.py                    file locations, .env read/write
  runlog.py         built-in run log, quality checks, feedback (Phase 11)
  tracing.py        Langfuse/LangSmith switch + always-on run log
  monitoring.py     data layer for both dashboards
  system_check.py ollama_setup.py         PC check, model advice, Ollama install/pull
desktop/          Qt app: main_window, analyze/tracker/dashboard/settings tabs,
                  setup_wizard, agent_worker (QThread), threads (pool helper)
main.py app.py monitor.py desktop_app.py   front ends
joblens.spec  installer/joblens.iss  scripts/build_installer.py   packaging
tests/            92 tests (no LLM, temp databases)
infra/langfuse/   self-hosted Langfuse (official compose + our override)
phaseN_*.py hello_llm.py compare_models.py   learning scripts per phase
```

---

## 7. Making a change (checklist)

1. Change code; keep UI code out of `job_agent/`.
2. `python -m pytest`, all green; add a test for new logic.
3. For UI changes, run `python desktop_app.py` and look at it.
4. If you uninstall a package: `pip check` (Streamlit needs `uvicorn`).
5. Update `progress.md` / `plan.md` (and `architecture.md` if the design changed).
6. Commit and push.

---

## 8. Building and releasing a new version

1. Bump the version in **`job_agent/__init__.py`** (`__version__`), the only place.
2. Build (about 5 min): `python scripts/build_installer.py`
   - PyInstaller → `dist\JobLens\`
   - **self-test gate**: the frozen app runs in installed mode with a temp
     AppData; no installer is made if it fails
   - Inno Setup → `dist\JobLens-Setup-<version>.exe`
3. Portable zip:
   `python -c "import shutil; shutil.make_archive('dist/JobLens-v<version>-windows-x64-portable','zip','dist','JobLens')"`
4. **Secrets scan** before publishing: no `.env`, `jobs.db`, resumes, or key
   strings inside `dist\` (see Phase 9f / v0.3.0 notes in `progress.md`).
5. Publish:
   `gh release create v<version> dist\JobLens-Setup-<version>.exe dist\JobLens-v<version>-windows-x64-portable.zip --latest --title "..." --notes-file notes.md`

The installer's **AppId GUID must never change**, or upgrades install side by
side instead of replacing the old version.

---

## 9. Langfuse (optional, developer tracing)

```powershell
cd infra\langfuse
docker compose up -d      # start (needs Docker Desktop running)
docker compose stop       # stop, keeps traces
```
Dashboard: http://localhost:3000 (login and keys in `infra\langfuse\.env`).
Uses a lot of RAM; currently **stopped**. JobLens works fully without it.

---

## 10. Known gotchas (each cost time once)

| Symptom | Cause / fix |
|---|---|
| `No module named 'langgraph'` | venv not activated |
| `/files/...` or `/DAppVersion` turns into `C:/Program Files/Git/...` | Git Bash path rewriting: use `MSYS_NO_PATHCONV=1`, or run tools from Python |
| `streamlit run` fails: "uvicorn is not installed" | Streamlit needs uvicorn; reinstall, then `pip check` |
| Installer exit code 5, "MoveFile failed; code 3" | path > 260 chars; installer now blocks install folders > 140 chars |
| GPU shows 4 GB in Windows tools | `Win32_VideoController` caps at 4 GB; `nvidia-smi` is used instead |
| Inno compile error "Unknown preprocessor directive" | a line starting with `#` (e.g. `#13#10`) |
| "Signal source has been deleted" at exit | background task outliving the app; fixed (wait + keep references) |
| A model shows as "not installed" | `llama3.2` vs `llama3.2:latest`; use `ollama_setup.has_model()` |
| Changing `TRACING` has no effect | read once at startup: restart the app |

---

## 11. Open items / suggested next steps

1. **Make the repo public** if the releases should be downloadable by others
   (secrets were never committed; `progress.md` names real job applications).
2. **Write the verdict from the final facts** (after the judge) so it never
   mentions removed claims.
3. **Eval suite (option D):** an Evaluate tab that re-runs saved jobs on
   chosen models and compares consistency, evidence quality, speed, tokens.
4. **Shorter LLM outputs** for speed (output tokens dominate latency).
5. **Code signing** (~$100–400/yr) to remove the SmartScreen warning.
6. **Auto-update:** check GitHub Releases on startup.
7. Point the Streamlit monitor at the built-in run log too.

---

## 12. Accounts and secrets

- GitHub: `RAIF-KARANI` (repo owner, release publisher; `gh` logged in via keyring).
- Local secrets only in git-ignored files: `.env` (LLM / Langfuse keys),
  `infra\langfuse\.env` (Langfuse passwords, login, project keys).
- No cloud services are required to run JobLens with Ollama.
