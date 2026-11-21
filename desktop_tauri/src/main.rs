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
use tauri::menu::{Menu, MenuItem, PredefinedMenuItem};
use tauri::tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent};
use tauri::{AppHandle, Emitter, Manager, RunEvent, State, WebviewWindow, WindowEvent};
use tauri_plugin_dialog::{DialogExt, FileDialogBuilder, FilePath};
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
async fn call(
    method: String,
    args: Vec<Value>,
    window: tauri::WebviewWindow,
    engine: State<'_, Engine>,
) -> Result<Value, String> {
    let id = engine.next.fetch_add(1, Ordering::SeqCst);
    let (tx, rx) = oneshot::channel();
    engine.pending.lock().unwrap().insert(id, tx);
    // 18d4: the engine answers the quick box with its own small API.
    let message = json!({ "id": id, "method": method, "args": args, "window": window.label() });
    if let Err(e) = engine.send(&message) {
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

/// 18d4: the quick-analyze box: small, frameless, on top, made once and kept
/// hidden so the shortcut opens it at once (as in 1.2.0).
fn make_quick_box(app: &AppHandle) -> tauri::Result<WebviewWindow> {
    tauri::WebviewWindowBuilder::new(app, "quick", tauri::WebviewUrl::App("index.html".into()))
        .title("JobLens quick analyze")
        // The page shows only the box when its address ends in #/quick (main.tsx).
        .initialization_script("if (location.hash !== '#/quick') location.hash = '#/quick';")
        .inner_size(480.0, 210.0)
        .resizable(false)
        .decorations(false)
        .always_on_top(true)
        .skip_taskbar(true)
        .center()
        .visible(false)
        .background_color(tauri::window::Color(10, 13, 22, 255))
        .build()
}

fn show_quick_box(app: &AppHandle) {
    if let Some(box_) = app.get_webview_window("quick") {
        let _ = box_.center();
        let _ = box_.show();
        let _ = box_.set_focus();
        // A fresh box each time: clear it, focus the field, fill in a copied link.
        let _ = box_.eval("window.joblensQuick && window.joblensQuick.opened()");
    }
}

/// Tell the engine what happened to the window. False if it isn't there to hear it.
fn tell_engine(app: &AppHandle, message: Value) -> bool {
    match app.try_state::<Engine>() {
        Some(engine) => engine.send(&message).is_ok(),
        None => false,
    }
}

/// The app id Windows shows notifications under; the engine registers it
/// for this user (engine.register_notification_sender).
const NOTIFICATION_SENDER: &str = "JobLens.Desktop";

/// 18d3: the tray's menu, as the engine describes it: [{id, text, enabled?, visible?} | {separator}].
fn tray_menu(app: &AppHandle, items: &Value) -> tauri::Result<Menu<tauri::Wry>> {
    let menu = Menu::new(app)?;
    for item in items.as_array().into_iter().flatten() {
        if item.get("visible").and_then(Value::as_bool) == Some(false) {
            continue;
        }
        if item.get("separator").and_then(Value::as_bool) == Some(true) {
            menu.append(&PredefinedMenuItem::separator(app)?)?;
            continue;
        }
        let id = item.get("id").and_then(Value::as_str).unwrap_or("");
        let text = item.get("text").and_then(Value::as_str).unwrap_or(id);
        let enabled = item.get("enabled").and_then(Value::as_bool).unwrap_or(true);
        menu.append(&MenuItem::with_id(app, id, text, enabled, None::<&str>)?)?;
    }
    Ok(menu)
}

/// 18d3: draw the tray, or update it. Clicks go to the engine, which decides.
fn draw_tray(app: &AppHandle, args: &Value) -> Result<(), String> {
    let menu = tray_menu(app, args.get("menu").unwrap_or(&Value::Null)).map_err(|e| e.to_string())?;
    let tooltip = args.get("tooltip").and_then(Value::as_str).unwrap_or("JobLens").to_string();
    if let Some(tray) = app.tray_by_id("main") {
        tray.set_menu(Some(menu)).map_err(|e| e.to_string())?;
        tray.set_tooltip(Some(tooltip)).map_err(|e| e.to_string())?;
        return Ok(());
    }
    let mut builder = TrayIconBuilder::with_id("main")
        .tooltip(tooltip)
        .menu(&menu)
        .show_menu_on_left_click(false)
        .on_menu_event(|app, event| {
            tell_engine(app, json!({ "shell": "tray", "item": event.id().as_ref() }));
        })
        .on_tray_icon_event(|tray, event| {
            // A left click on the icon opens JobLens, like "Open JobLens".
            if let TrayIconEvent::Click { button: MouseButton::Left, button_state: MouseButtonState::Up, .. } = event {
                tell_engine(tray.app_handle(), json!({ "shell": "tray", "item": "open" }));
            }
        });
    if let Some(icon) = app.default_window_icon() {
        builder = builder.icon(icon.clone());
    }
    builder.build(app).map_err(|e| e.to_string())?;
    Ok(())
}

/// 18d3: a Windows notification (with its sound). A click on it tells the
/// engine, which opens the screen it was about.
fn notify(app: &AppHandle, args: &Value) -> Result<(), String> {
    use tauri_winrt_notification::{Sound, Toast};

    let title = args.get("title").and_then(Value::as_str).unwrap_or("JobLens");
    let body = args.get("body").and_then(Value::as_str).unwrap_or("");
    let clicked = app.clone();
    Toast::new(NOTIFICATION_SENDER)
        .title(title)
        .text1(body)
        .sound(Some(Sound::Default))
        .on_activated(move |_action| {
            tell_engine(&clicked, json!({ "shell": "notification_clicked" }));
            Ok(())
        })
        .show()
        .map_err(|e| e.to_string())
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
            // 19b: plus a query like "tracker?job=12": ? = & can't end the quoted string below.
            let page = args.get("page").and_then(Value::as_str).unwrap_or("dashboard");
            if !page.chars().all(|c| c.is_ascii_alphanumeric() || "-?=&".contains(c)) {
                return Err(format!("Not a JobLens page: {page}"));
            }
            if let Some(window) = main_window(app) {
                let _ = window.eval(&format!("window.location.hash = '#/{page}'"));
            }
            show(app);
            Ok(Value::Null)
        }
        "is_visible" => {
            let label = args.get("window").and_then(Value::as_str).unwrap_or("main");
            Ok(json!(app.get_webview_window(label).and_then(|w| w.is_visible().ok()).unwrap_or(false)))
        }
        "quick_show" => {
            show_quick_box(app);
            Ok(Value::Null)
        }
        "quick_hide" => {
            if let Some(box_) = app.get_webview_window("quick") {
                let _ = box_.hide();
            }
            Ok(Value::Null)
        }
        "tray" => draw_tray(app, args).map(|_| Value::Null),
        "notify" => notify(app, args).map(|_| Value::Null),
        other => Err(format!("The window can't '{other}' yet.")),
    }
}

/// 18d2: the engine's {"name": "CSV file", "extensions": ["csv"]} filters, on a dialog.
fn with_filters(mut dialog: FileDialogBuilder<tauri::Wry>, args: &Value) -> FileDialogBuilder<tauri::Wry> {
    for filter in args.get("filters").and_then(Value::as_array).into_iter().flatten() {
        let name = filter.get("name").and_then(Value::as_str).unwrap_or("Files");
        let extensions: Vec<&str> = filter
            .get("extensions")
            .and_then(Value::as_array)
            .map(|list| list.iter().filter_map(Value::as_str).collect())
            .unwrap_or_default();
        dialog = dialog.add_filter(name, &extensions);
    }
    dialog
}

fn path_text(path: FilePath) -> Option<String> {
    path.into_path().ok().map(|p| p.to_string_lossy().into_owned())
}

/// 18d2: Open and Save. They don't block the window: the answer goes back to
/// the engine when you choose or cancel (null). Returns false for other actions.
fn ask_dialog(app: &AppHandle, action: &str, args: &Value, number: Value) -> bool {
    let mut dialog = with_filters(app.dialog().file(), args);
    if let Some(window) = main_window(app) {
        dialog = dialog.set_parent(&window);
    }
    let reply_to = app.clone();
    match action {
        "pick_files" => {
            dialog.pick_files(move |paths| {
                let chosen = paths.map(|list| list.into_iter().filter_map(path_text).collect::<Vec<_>>());
                tell_engine(&reply_to, json!({ "answer": number, "result": chosen }));
            });
            true
        }
        "save_file" => {
            if let Some(name) = args.get("name").and_then(Value::as_str) {
                dialog = dialog.set_file_name(name);
            }
            dialog.save_file(move |path| {
                let chosen = path.and_then(path_text);
                tell_engine(&reply_to, json!({ "answer": number, "result": chosen }));
            });
            true
        }
        _ => false,
    }
}

/// How to start the engine: the installed one, or Python from the repo.
fn engine_command() -> Command {
    let exe_dir = std::env::current_exe().ok().and_then(|p| p.parent().map(PathBuf::from));
    if let Some(installed) = exe_dir.map(|d| d.join("engine").join("joblens-engine.exe")) {
        if installed.exists() && std::env::var("JOBLENS_PYTHON").is_err() {
            let mut command = Command::new(installed);
            command.stderr(engine_log()); // no terminal to print to: a file
            return command;
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

/// 18d5: Windows is shutting down, or an installer (Inno Setup, through the
/// Restart Manager) asks JobLens to close. The X button may only hide to the
/// tray, so this listens on the main window itself: say yes, then stop the
/// engine properly (stop the run, free the model) before Windows ends us.
#[cfg(windows)]
mod windows_closing {
    use std::sync::OnceLock;

    use tauri::{AppHandle, WebviewWindow};
    use windows_sys::Win32::Foundation::{HWND, LPARAM, LRESULT, WPARAM};
    use windows_sys::Win32::UI::Shell::{DefSubclassProc, SetWindowSubclass};
    use windows_sys::Win32::UI::WindowsAndMessaging::{WM_ENDSESSION, WM_QUERYENDSESSION};

    static APP: OnceLock<AppHandle> = OnceLock::new();

    unsafe extern "system" fn on_message(
        hwnd: HWND,
        message: u32,
        wparam: WPARAM,
        lparam: LPARAM,
        _id: usize,
        _data: usize,
    ) -> LRESULT {
        match message {
            WM_QUERYENDSESSION => 1, // "may JobLens close?" yes, always
            WM_ENDSESSION if wparam != 0 => {
                if let Some(app) = APP.get() {
                    super::stop_engine(app);
                    app.exit(0);
                }
                0
            }
            _ => unsafe { DefSubclassProc(hwnd, message, wparam, lparam) },
        }
    }

    pub fn listen(app: &AppHandle, window: &WebviewWindow) {
        let _ = APP.set(app.clone());
        if let Ok(hwnd) = window.hwnd() {
            unsafe {
                SetWindowSubclass(hwnd.0 as HWND, Some(on_message), 1, 0);
            }
        }
    }
}

/// 18d6: what the installed engine prints (warnings, "! ..." lines) goes to
/// %LOCALAPPDATA%\JobLens\engine.log, new each start, for troubleshooting.
fn engine_log() -> Stdio {
    if let Ok(base) = std::env::var("LOCALAPPDATA") {
        let folder = PathBuf::from(base).join("JobLens");
        if std::fs::create_dir_all(&folder).is_ok() {
            if let Ok(file) = std::fs::File::create(folder.join("engine.log")) {
                return Stdio::from(file);
            }
        }
    }
    Stdio::null()
}

fn start_engine(app: &AppHandle) -> std::io::Result<Engine> {
    let mut command = engine_command();
    // 18d5: Start with Windows must name this program, not the engine.
    if let Ok(exe) = std::env::current_exe() {
        command.env("JOBLENS_APP_EXE", exe);
    }
    command.stdin(Stdio::piped()).stdout(Stdio::piped());
    if std::env::var("JOBLENS_PYTHON").is_ok() || !std::env::current_exe().map(|e| e.with_file_name("engine").exists()).unwrap_or(false) {
        command.stderr(Stdio::inherit()); // from source: the terminal you started it in
    }
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
                let _ = handle.emit_to("main", "joblens-event", event.clone());
            } else if let Some(action) = message.get("do").and_then(Value::as_str) {
                let args = message.get("args").cloned().unwrap_or(Value::Null);
                let ask = message.get("ask").cloned();
                let action = action.to_string();
                // Window work belongs on the main thread; the answer goes back to the engine.
                let app = handle.clone();
                let _ = handle.run_on_main_thread(move || {
                    if let Some(number) = ask.clone() {
                        if ask_dialog(&app, &action, &args, number) {
                            return; // a dialog answers when you close it
                        }
                    }
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
    // 18d5: started by Windows at sign-in (Start with Windows): stay in the tray.
    let in_tray = std::env::args().any(|a| a == "--tray");
    let app = tauri::Builder::default()
        // 18d5: one JobLens at a time (first, before anything else starts): a
        // second start brings this one's window back, and exits.
        .plugin(tauri_plugin_single_instance::init(|app, _args, _cwd| show(app)))
        .plugin(tauri_plugin_dialog::init())
        .invoke_handler(tauri::generate_handler![call])
        .on_page_load(|webview, _payload| {
            if webview.label() == "main" {
                tell_engine(webview.app_handle(), json!({ "shell": "page_loaded" }));
            }
        })
        .on_window_event(|window, event| {
            // 18d3: the X asks the engine first: it may hide to the tray instead
            // (a run going, or JobLens kept in the tray). If the engine isn't
            // there to answer, the window just closes.
            match event {
                WindowEvent::CloseRequested { api, .. } if window.label() == "quick" => {
                    // Alt+F4 on the box: hide it, it's needed again next time.
                    api.prevent_close();
                    let _ = window.hide();
                }
                WindowEvent::CloseRequested { api, .. } => {
                    if window.label() == "main"
                        && tell_engine(window.app_handle(), json!({ "shell": "close_requested" }))
                    {
                        api.prevent_close();
                    }
                }
                // The hidden box mustn't keep JobLens running once the main window is gone
                // (1.0.0-1.0.1 had exactly this bug with pywebview).
                WindowEvent::Destroyed if window.label() == "main" => window.app_handle().exit(0),
                _ => {}
            }
        })
        .setup(move |app| {
            let engine = start_engine(app.handle())?;
            app.manage(engine);
            make_quick_box(app.handle())?;
            if let Some(window) = main_window(app.handle()) {
                #[cfg(windows)]
                windows_closing::listen(app.handle(), &window);
                if in_tray {
                    // The page still loads, hidden; the tray and reminders work.
                    tell_engine(app.handle(), json!({ "shell": "visibility", "visible": false }));
                } else {
                    show(app.handle());
                }
            }
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
