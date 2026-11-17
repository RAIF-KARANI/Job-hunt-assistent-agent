// Phase 18 spike: JobLens's window in Rust (Tauri 2).
//
// The window shows the same built UI as the normal app (desktop_web/web).
// The Python agent runs beside it (spikes/18_tauri/sidecar.py), and this
// program passes messages between the two:
//   page -> `call(method, args)` -> one JSON line to Python -> its answer back
//   Python's events (log lines, run steps) -> the "joblens-event" event -> page
//
// For measuring (step 18b), JOBLENS_SPIKE_MEASURE=1 writes the timings to
// spikes/18_tauri/timing.json and closes the window once the page has its
// first answer from Python.

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::collections::HashMap;
use std::io::{BufRead, BufReader, Write};
use std::path::PathBuf;
use std::process::{Child, ChildStdin, Command, Stdio};
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::sync::{Arc, Mutex};
use std::time::Instant;

use serde_json::{json, Value};
use tauri::{Emitter, Manager, RunEvent, State};
use tokio::sync::oneshot;

type Pending = Arc<Mutex<HashMap<u64, oneshot::Sender<Value>>>>;

struct Sidecar {
    stdin: Mutex<ChildStdin>,
    pending: Pending,
    next: AtomicU64,
    child: Mutex<Child>,
}

struct Clock {
    started: Instant,
    sidecar_ready_ms: Mutex<Option<u128>>,
    page_loaded_ms: Mutex<Option<u128>>,
    first_answer: AtomicBool,
}

/// The repo, from where this crate sits (spikes/18_tauri/src-tauri).
fn repo_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("..").join("..").join("..")
}

/// Every call from the page goes through here: the page's bridge turns
/// `api.list_jobs()` into `call("list_jobs", [])`.
#[tauri::command]
async fn call(
    method: String,
    args: Vec<Value>,
    sidecar: State<'_, Sidecar>,
    clock: State<'_, Clock>,
    app: tauri::AppHandle,
) -> Result<Value, String> {
    let id = sidecar.next.fetch_add(1, Ordering::SeqCst);
    let (tx, rx) = oneshot::channel();
    sidecar.pending.lock().unwrap().insert(id, tx);
    {
        let line = json!({ "id": id, "method": method, "args": args }).to_string();
        let mut stdin = sidecar.stdin.lock().unwrap();
        writeln!(stdin, "{line}").map_err(|e| format!("JobLens's engine isn't running: {e}"))?;
        stdin.flush().map_err(|e| e.to_string())?;
    }
    let reply = rx.await.map_err(|_| "JobLens's engine stopped. Restart the app.".to_string())?;

    if method == "app_info" && !clock.first_answer.swap(true, Ordering::SeqCst) {
        report_timing(&app, &clock);
    }
    if let Some(error) = reply.get("error") {
        return Err(error.as_str().unwrap_or("error").to_string());
    }
    Ok(reply.get("result").cloned().unwrap_or(Value::Null))
}

/// 18b: how long each part of the start took.
fn report_timing(app: &tauri::AppHandle, clock: &Clock) {
    let answered = clock.started.elapsed().as_millis();
    let timing = json!({
        "page_loaded_ms": *clock.page_loaded_ms.lock().unwrap(),
        "sidecar_ready_ms": *clock.sidecar_ready_ms.lock().unwrap(),
        "first_answer_ms": answered,
    });
    eprintln!("[spike] {timing}");
    if std::env::var("JOBLENS_SPIKE_MEASURE").is_ok() {
        let out = repo_root().join("spikes").join("18_tauri").join("timing.json");
        let _ = std::fs::write(out, timing.to_string());
        let handle = app.clone();
        std::thread::spawn(move || {
            std::thread::sleep(std::time::Duration::from_millis(1500));
            handle.exit(0);
        });
    }
}

fn start_sidecar(app: &tauri::AppHandle) -> std::io::Result<Sidecar> {
    let root = repo_root();
    let python = std::env::var("JOBLENS_PYTHON")
        .map(PathBuf::from)
        .unwrap_or_else(|_| root.join(".venv").join("Scripts").join("python.exe"));
    let mut command = Command::new(python);
    command
        .arg("-u")
        .arg(root.join("spikes").join("18_tauri").join("sidecar.py"))
        .current_dir(&root)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::inherit());
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        command.creation_flags(0x0800_0000); // CREATE_NO_WINDOW: no black console box
    }
    let mut child = command.spawn()?;
    let stdin = child.stdin.take().expect("piped stdin");
    let stdout = child.stdout.take().expect("piped stdout");
    let pending: Pending = Arc::new(Mutex::new(HashMap::new()));

    // Python's answers and events, as they come.
    let waiting = pending.clone();
    let handle = app.clone();
    std::thread::spawn(move || {
        for line in BufReader::new(stdout).lines() {
            let Ok(line) = line else { break };
            let Ok(message) = serde_json::from_str::<Value>(&line) else { continue };
            if let Some(event) = message.get("event") {
                if event.get("type").and_then(Value::as_str) == Some("sidecar_ready") {
                    let clock = handle.state::<Clock>();
                    *clock.sidecar_ready_ms.lock().unwrap() = Some(clock.started.elapsed().as_millis());
                }
                let _ = handle.emit("joblens-event", event.clone());
                continue;
            }
            if let Some(id) = message.get("id").and_then(Value::as_u64) {
                if let Some(tx) = waiting.lock().unwrap().remove(&id) {
                    let _ = tx.send(message);
                }
            }
        }
        // Python stopped: every call still waiting gets an error instead of hanging.
        waiting.lock().unwrap().clear();
    });

    Ok(Sidecar { stdin: Mutex::new(stdin), pending, next: AtomicU64::new(1), child: Mutex::new(child) })
}

fn main() {
    let clock = Clock {
        started: Instant::now(),
        sidecar_ready_ms: Mutex::new(None),
        page_loaded_ms: Mutex::new(None),
        first_answer: AtomicBool::new(false),
    };
    let app = tauri::Builder::default()
        .manage(clock)
        .invoke_handler(tauri::generate_handler![call])
        .on_page_load(|webview, _payload| {
            let clock = webview.state::<Clock>();
            let mut loaded = clock.page_loaded_ms.lock().unwrap();
            if loaded.is_none() {
                *loaded = Some(clock.started.elapsed().as_millis());
            }
        })
        .setup(|app| {
            let sidecar = start_sidecar(app.handle())?;
            app.manage(sidecar);
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("couldn't start the JobLens window");

    app.run(|handle, event| {
        if let RunEvent::Exit = event {
            if let Some(sidecar) = handle.try_state::<Sidecar>() {
                let _ = sidecar.child.lock().unwrap().kill();
            }
        }
    });
}
