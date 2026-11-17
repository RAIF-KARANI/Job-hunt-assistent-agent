// JobLens's window (version 3, decision E6): Rust shows, Python decides.
//
// This program opens the window with the built UI (desktop_web/web) and
// starts the engine beside it (desktop_web/engine.py: the agent and the
// same Api the pywebview window uses). One pipe, one JSON object per line:
//   page -> call(method, args) -> engine -> its answer back to the page
//   engine events (log lines, run steps) -> "joblens-event" -> page
//   engine requests ("do", or "ask" when it needs an answer) -> done here
//   what happens to the window (page loaded, shown, hidden) -> engine
//
// Where the engine is: next to this program in an installed JobLens
// (engine\joblens-engine.exe); from source, the repo's .venv Python running
// `-m desktop_web.engine`. JOBLENS_PYTHON overrides the Python to use.

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::collections::HashMap;
use std::io::{BufRead, BufReader, Write};
use std::path::PathBuf;
use std::process::{Child, ChildStdin, Command, Stdio};
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

use serde_json::{json, Value};
use tauri::{AppHandle, Emitter, Manager, RunEvent, State, WebviewWindow};
use tokio::sync::oneshot;

type Pending = Arc<Mutex<HashMap<u64, oneshot::Sender<Value>>>>;

/// The engine process and the pipe to it.
struct Engine {
    stdin: Mutex<Option<ChildStdin>>,
    pending: Pending,
    next: AtomicU64,
    child: Mutex<Child>,
}

impl Engine {
    fn send(&self, message: &Value) -> Result<(), String> {
        let mut stdin = self.stdin.lock().unwrap();
        let pipe = stdin.as_mut().ok_or("JobLens's engine has stopped.")?;
        writeln!(pipe, "{message}").map_err(|e| format!("JobLens's engine isn't running: {e}"))?;
        pipe.flush().map_err(|e| e.to_string())
    }
}

/// Every call from the page goes through here: the page's bridge turns
/// `api.list_jobs()` into `call("list_jobs", [])`.
#[tauri::command]
async fn call(method: String, args: Vec<Value>, engine: State<'_, Engine>) -> Result<Value, String> {
    let id = engine.next.fetch_add(1, Ordering::SeqCst);
    let (tx, rx) = oneshot::channel();
    engine.pending.lock().unwrap().insert(id, tx);
    if let Err(e) = engine.send(&json!({ "id": id, "method": method, "args": args })) {
        engine.pending.lock().unwrap().remove(&id);
        return Err(e);
    }
    let reply = rx.await.map_err(|_| "JobLens's engine stopped. Restart the app.".to_string())?;
    if let Some(error) = reply.get("error") {
        return Err(error.as_str().unwrap_or("error").to_string());
    }
    Ok(reply.get("result").cloned().unwrap_or(Value::Null))
}

fn main_window(app: &AppHandle) -> Option<WebviewWindow> {
    app.get_webview_window("main")
}

/// Tell the engine what happened to the window.
fn tell_engine(app: &AppHandle, message: Value) {
    if let Some(engine) = app.try_state::<Engine>() {
        let _ = engine.send(&message);
    }
}

fn show(app: &AppHandle) {
    if let Some(window) = main_window(app) {
        let _ = window.unminimize();
        let _ = window.show();
        let _ = window.set_focus();
    }
    tell_engine(app, json!({ "shell": "visibility", "visible": true }));
}

fn hide(app: &AppHandle) {
    if let Some(window) = main_window(app) {
        let _ = window.hide();
    }
    tell_engine(app, json!({ "shell": "visibility", "visible": false }));
}

/// A request from the engine. `Ok` carries the answer for an `ask`.
fn handle_request(app: &AppHandle, action: &str, args: &Value) -> Result<Value, String> {
    match action {
        "show" => {
            show(app);
            Ok(Value::Null)
        }
        "hide" => {
            hide(app);
            Ok(Value::Null)
        }
        "quit" => {
            app.exit(0);
            Ok(Value::Null)
        }
        "navigate" => {
            // Only our own page names (letters and dashes), never a script.
            let page = args.get("page").and_then(Value::as_str).unwrap_or("dashboard");
            if !page.chars().all(|c| c.is_ascii_alphanumeric() || c == '-') {
                return Err(format!("Not a JobLens page: {page}"));
            }
            if let Some(window) = main_window(app) {
                let _ = window.eval(&format!("window.location.hash = '#/{page}'"));
            }
            show(app);
            Ok(Value::Null)
        }
        "is_visible" => Ok(json!(main_window(app).and_then(|w| w.is_visible().ok()).unwrap_or(false))),
        other => Err(format!("The window can't '{other}' yet.")),
    }
}

/// How to start the engine: the installed one, or Python from the repo.
fn engine_command() -> Command {
    let exe_dir = std::env::current_exe().ok().and_then(|p| p.parent().map(PathBuf::from));
    if let Some(installed) = exe_dir.map(|d| d.join("engine").join("joblens-engine.exe")) {
        if installed.exists() && std::env::var("JOBLENS_PYTHON").is_err() {
            return Command::new(installed);
        }
    }
    // From source: the repo this program was built in.
    let repo = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("..");
    let python = std::env::var("JOBLENS_PYTHON")
        .map(PathBuf::from)
        .unwrap_or_else(|_| repo.join(".venv").join("Scripts").join("python.exe"));
    let mut command = Command::new(python);
    command.args(["-u", "-m", "desktop_web.engine"]).current_dir(repo);
    command
}

fn start_engine(app: &AppHandle) -> std::io::Result<Engine> {
    let mut command = engine_command();
    command.stdin(Stdio::piped()).stdout(Stdio::piped()).stderr(Stdio::inherit());
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        command.creation_flags(0x0800_0000); // CREATE_NO_WINDOW: no black console box
    }
    let mut child = command.spawn()?;
    let stdin = child.stdin.take().expect("piped stdin");
    let stdout = child.stdout.take().expect("piped stdout");
    let pending: Pending = Arc::new(Mutex::new(HashMap::new()));

    // The engine's lines, as they come.
    let waiting = pending.clone();
    let handle = app.clone();
    std::thread::spawn(move || {
        for line in BufReader::new(stdout).lines() {
            let Ok(line) = line else { break };
            let Ok(message) = serde_json::from_str::<Value>(&line) else { continue };
            if let Some(event) = message.get("event") {
                let _ = handle.emit("joblens-event", event.clone());
            } else if let Some(action) = message.get("do").and_then(Value::as_str) {
                let args = message.get("args").cloned().unwrap_or(Value::Null);
                let ask = message.get("ask").cloned();
                let action = action.to_string();
                // Window work belongs on the main thread; the answer goes back to the engine.
                let app = handle.clone();
                let _ = handle.run_on_main_thread(move || {
                    let result = handle_request(&app, &action, &args);
                    if let Some(number) = ask {
                        let reply = match result {
                            Ok(value) => json!({ "answer": number, "result": value }),
                            Err(error) => json!({ "answer": number, "error": error }),
                        };
                        tell_engine(&app, reply);
                    } else if let Err(error) = result {
                        eprintln!("[window] {error}");
                    }
                });
            } else if let Some(id) = message.get("id").and_then(Value::as_u64) {
                if let Some(tx) = waiting.lock().unwrap().remove(&id) {
                    let _ = tx.send(message);
                }
            }
        }
        // The engine stopped: every call still waiting gets an error instead of hanging.
        waiting.lock().unwrap().clear();
    });

    Ok(Engine { stdin: Mutex::new(Some(stdin)), pending, next: AtomicU64::new(1), child: Mutex::new(child) })
}

/// On the way out: close the pipe so the engine ends a running step and
/// frees the model (like Quit today), then give it a few seconds.
fn stop_engine(app: &AppHandle) {
    let Some(engine) = app.try_state::<Engine>() else { return };
    engine.stdin.lock().unwrap().take(); // closing our end tells the engine to stop
    let mut child = engine.child.lock().unwrap();
    let deadline = Instant::now() + Duration::from_secs(8);
    while Instant::now() < deadline {
        if let Ok(Some(_)) = child.try_wait() {
            return;
        }
        std::thread::sleep(Duration::from_millis(100));
    }
    let _ = child.kill();
}

fn main() {
    let app = tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![call])
        .on_page_load(|webview, _payload| {
            tell_engine(webview.app_handle(), json!({ "shell": "page_loaded" }));
        })
        .setup(|app| {
            let engine = start_engine(app.handle())?;
            app.manage(engine);
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("couldn't start the JobLens window");

    app.run(|handle, event| {
        if let RunEvent::Exit = event {
            stop_engine(handle);
        }
    });
}
