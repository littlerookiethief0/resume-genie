use std::process::{Command, Stdio};
use std::sync::{Arc, Mutex};
use std::thread;
use tauri::{AppHandle, Emitter, State, Manager};
use tauri::menu::{Menu, MenuItem};
use tauri::tray::{TrayIconBuilder, TrayIconEvent};
use tauri::image::Image;

#[cfg(windows)]
use std::os::windows::process::CommandExt;


/// 当前正在运行的唤醒脚本： (pid, site_id)
struct WakeScriptState(Arc<Mutex<Option<(u32, String)>>>);

#[tauri::command]
fn greet(name: &str) -> String {
    format!("Hello, {}! You've been greeted from Rust!", name)
}

fn kill_process_by_pid(pid: u32) {
    #[cfg(unix)]
    {
        let _ = Command::new("kill")
            .arg("-9")
            .arg(pid.to_string())
            .output();
    }
    #[cfg(windows)]
    {
        let _ = Command::new("cmd")
            .args(["/C", "taskkill", "/F", "/PID", &pid.to_string()])
            .output();
    }
}

#[tauri::command]
async fn run_wake_script(app: AppHandle, state: State<'_, WakeScriptState>, site_id: String) -> Result<String, String> {
    // 获取资源目录路径
    let resource_dir = app.path()
        .resource_dir()
        .map_err(|e| format!("Failed to get resource dir: {}", e))?;

    // Python 脚本路径（打包后在 resources 目录）
    // macOS: Resources/_up_/python-scripts/
    // Windows: AppData/Local/app-name/python-scripts/
    let script_dir = if resource_dir.join("_up_").join("python-scripts").exists() {
        resource_dir.join("_up_").join("python-scripts")
    } else {
        resource_dir.join("python-scripts")
    };

    let script_path = script_dir.join(format!("{}.py", site_id));

    // 使用打包的 standalone Python
    #[cfg(target_os = "windows")]
    let python_exe = script_dir.join("python").join("python.exe");

    #[cfg(not(target_os = "windows"))]
    let python_exe = script_dir.join("python").join("bin").join("python3");

    // 检查脚本是否存在
    if !script_path.exists() {
        return Err(format!("Script not found: {:?}", script_path));
    }

    // 检查 Python 是否存在
    if !python_exe.exists() {
        return Err(format!("Python not found: {:?}", python_exe));
    }

    let mut cmd = Command::new(&python_exe);
    cmd.arg("-u")
        .arg(&script_path)
        .current_dir(&script_dir)
        .stdout(Stdio::inherit())
        .stderr(Stdio::inherit());

    // Windows: 隐藏控制台窗口
    #[cfg(windows)]
    cmd.creation_flags(0x08000000); // CREATE_NO_WINDOW

    let mut child = cmd.spawn()
        .map_err(|e| format!("Failed to execute script: {}", e))?;

    let pid = child.id();
    let site_id_clone = site_id.clone();
    *state.0.lock().unwrap() = Some((pid, site_id.clone()));

    let state_inner = Arc::clone(&state.0);
    thread::spawn(move || {
        let status = child.wait();
        state_inner.lock().unwrap().take();
        let (success, code) = match &status {
            Ok(s) => (s.success(), s.code()),
            Err(_) => (false, None),
        };
        let _ = app.emit("wake_script_finished", (site_id_clone, success, code));
    });

    Ok("Script started".to_string())
}

#[tauri::command]
async fn stop_wake_script(state: State<'_, WakeScriptState>, app: AppHandle) -> Result<String, String> {
    let Some((pid, site_id)) = state.0.lock().unwrap().take() else {
        return Ok("No script running".to_string());
    };

    kill_process_by_pid(pid);
    let _ = app.emit("wake_script_finished", (site_id, false, Some(-1i32)));

    Ok("Script stopped".to_string())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .manage(WakeScriptState(Arc::new(Mutex::new(None))))
        .invoke_handler(tauri::generate_handler![greet, run_wake_script, stop_wake_script])
        .setup(|app| {
            // 加载托盘图标
            let icon_bytes = include_bytes!("../icons/icon.png");
            let img = image::load_from_memory(icon_bytes).expect("Failed to load icon").to_rgba8();
            let (width, height) = img.dimensions();
            let icon = Image::new_owned(img.into_raw(), width, height);

            // 创建托盘菜单
            let show = MenuItem::with_id(app, "show", "显示", true, None::<&str>)?;
            let quit = MenuItem::with_id(app, "quit", "退出", true, None::<&str>)?;
            let menu = Menu::with_items(app, &[&show, &quit])?;

            // 创建系统托盘
            let _tray = TrayIconBuilder::new()
                .icon(icon)
                .menu(&menu)
                .on_menu_event(|app, event| {
                    match event.id.as_ref() {
                        "show" => {
                            if let Some(window) = app.get_webview_window("main") {
                                let _ = window.show();
                                let _ = window.set_focus();
                            }
                        }
                        "quit" => {
                            app.exit(0);
                        }
                        _ => {}
                    }
                })
                .on_tray_icon_event(|tray, event| {
                    if let TrayIconEvent::Click { .. } = event {
                        let app = tray.app_handle();
                        if let Some(window) = app.get_webview_window("main") {
                            let _ = window.show();
                            let _ = window.set_focus();
                        }
                    }
                })
                .build(app)?;

            // 处理窗口关闭事件：最小化到托盘而不是退出
            if let Some(window) = app.get_webview_window("main") {
                let window_clone = window.clone();
                window.on_window_event(move |event| {
                    if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                        api.prevent_close();
                        let _ = window_clone.hide();
                    }
                });
            }

            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
