use std::process::{Command, Stdio};
use std::sync::{Arc, Mutex};
use std::thread;
use tauri::{AppHandle, Emitter, State, Manager};
use tauri::menu::{Menu, MenuItem};
use tauri::tray::{TrayIconBuilder, TrayIconEvent};
use tauri::image::Image;

#[cfg(target_os = "macos")]
use tauri::ActivationPolicy;

#[cfg(target_os = "windows")]
use std::os::windows::process::CommandExt;


/// 当前正在运行的唤醒脚本： (pid, site_id)
struct WakeScriptState(Arc<Mutex<Option<(u32, String)>>>);

/// 当前正在运行的解析脚本： (pid, site_id)
struct ParseScriptState(Arc<Mutex<Option<(u32, String)>>>);

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

    // 尝试使用打包的 Python（生产模式）
    let packaged_dir = resource_dir.join("_up_").join("python-scripts");
    #[cfg(target_os = "windows")]
    let packaged_python = packaged_dir.join("python").join("python.exe");
    #[cfg(not(target_os = "windows"))]
    let packaged_python = packaged_dir.join("python").join("bin").join("python3");

    let (script_dir, python_exe) = if packaged_python.exists() {
        // 生产模式：使用打包的 Python
        (packaged_dir, packaged_python)
    } else {
        // 开发模式：使用项目根目录的脚本和虚拟环境的 Python
        // resource_dir 是 src-tauri/target/debug，需要往上三层到项目根目录
        let project_root = resource_dir
            .parent()  // src-tauri/target
            .unwrap()
            .parent()  // src-tauri
            .unwrap()
            .parent()  // 项目根目录
            .unwrap()
            .to_path_buf();
        let dir = project_root.join("python-scripts");

        #[cfg(target_os = "windows")]
        let python = dir.join(".venv").join("Scripts").join("python.exe");
        #[cfg(not(target_os = "windows"))]
        let python = dir.join(".venv").join("bin").join("python3");

        (dir, python)
    };

    let script_path = script_dir.join(format!("{}.py", site_id));

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

#[tauri::command]
async fn stop_parse_script(state: State<'_, ParseScriptState>, app: AppHandle) -> Result<String, String> {
    let Some((pid, site_id)) = state.0.lock().unwrap().take() else {
        return Ok("No script running".to_string());
    };

    kill_process_by_pid(pid);
    let _ = app.emit("parse_script_finished", (site_id, false, Some(-1i32)));

    Ok("Script stopped".to_string())
}

#[tauri::command]
async fn run_parse_script(app: AppHandle, state: State<'_, ParseScriptState>, site_id: String, days: i32) -> Result<String, String> {
    let resource_dir = app.path()
        .resource_dir()
        .map_err(|e| format!("Failed to get resource dir: {}", e))?;

    let packaged_dir = resource_dir.join("_up_").join("python-scripts");
    #[cfg(target_os = "windows")]
    let packaged_python = packaged_dir.join("python").join("python.exe");
    #[cfg(not(target_os = "windows"))]
    let packaged_python = packaged_dir.join("python").join("bin").join("python3");

    let (script_dir, python_exe) = if packaged_python.exists() {
        (packaged_dir, packaged_python)
    } else {
        let project_root = resource_dir
            .parent().unwrap()
            .parent().unwrap()
            .parent().unwrap()
            .to_path_buf();
        let dir = project_root.join("python-scripts");

        #[cfg(target_os = "windows")]
        let python = dir.join(".venv").join("Scripts").join("python.exe");
        #[cfg(not(target_os = "windows"))]
        let python = dir.join(".venv").join("bin").join("python3");

        (dir, python)
    };

    let script_path = script_dir.join(format!("{}_resume.py", site_id));

    if !script_path.exists() {
        return Err(format!("Script not found: {:?}", script_path));
    }

    if !python_exe.exists() {
        return Err(format!("Python not found: {:?}", python_exe));
    }

    let mut cmd = Command::new(&python_exe);
    cmd.arg("-u")
        .arg(&script_path)
        .arg("--days")
        .arg(days.to_string())
        .current_dir(&script_dir)
        .stdout(Stdio::inherit())
        .stderr(Stdio::inherit());

    #[cfg(windows)]
    cmd.creation_flags(0x08000000);

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
        let _ = app.emit("parse_script_finished", (site_id_clone, success, code));
    });

    Ok("Parse script started".to_string())
}

#[tauri::command]
async fn select_directory(app: AppHandle) -> Result<String, String> {
    use tauri_plugin_dialog::DialogExt;

    let folder = app.dialog()
        .file()
        .blocking_pick_folder();

    match folder {
        Some(path) => Ok(path.to_string()),
        None => Err("未选择目录".to_string()),
    }
}

#[tauri::command]
async fn open_directory(app: AppHandle, path: String) -> Result<(), String> {
    let resource_dir = app.path()
        .resource_dir()
        .map_err(|e| format!("Failed to get resource dir: {}", e))?;

    let abs_path = if path.starts_with("./") || path.starts_with(".\\") {
        let relative = path.trim_start_matches("./").trim_start_matches(".\\");

        // 直接使用 cfg!(debug_assertions) 判断开发/生产模式
        let project_root = if cfg!(debug_assertions) {
            // 开发模式：resource_dir 是 src-tauri/target/debug，向上3层到项目根目录
            resource_dir
                .parent().unwrap()  // src-tauri/target
                .parent().unwrap()  // src-tauri
                .parent().unwrap()  // 项目根目录
                .to_path_buf()
        } else {
            // 生产模式
            resource_dir.parent().unwrap().parent().unwrap().to_path_buf()
        };

        project_root.join(relative)
    } else {
        std::path::PathBuf::from(&path)
    };

    // 如果目录不存在，创建它
    if !abs_path.exists() {
        std::fs::create_dir_all(&abs_path)
            .map_err(|e| format!("Failed to create directory: {}", e))?;
    }

    let path_str = abs_path.to_string_lossy().to_string();

    #[cfg(target_os = "macos")]
    {
        Command::new("open")
            .arg(&path_str)
            .spawn()
            .map_err(|e| format!("Failed to open directory: {}", e))?;
    }

    #[cfg(target_os = "windows")]
    {
        Command::new("explorer")
            .arg(&path_str)
            .spawn()
            .map_err(|e| format!("Failed to open directory: {}", e))?;
    }

    #[cfg(target_os = "linux")]
    {
        Command::new("xdg-open")
            .arg(&path_str)
            .spawn()
            .map_err(|e| format!("Failed to open directory: {}", e))?;
    }

    Ok(())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_dialog::init())
        .manage(WakeScriptState(Arc::new(Mutex::new(None))))
        .manage(ParseScriptState(Arc::new(Mutex::new(None))))
        .invoke_handler(tauri::generate_handler![greet, run_wake_script, stop_wake_script, run_parse_script, stop_parse_script, select_directory, open_directory])
        .setup(|app| {
            // 设置应用激活策略，使其不出现在 Dock
        // macOS: 隐藏 Dock 图标
        #[cfg(target_os = "macos")]
        app.set_activation_policy(tauri::ActivationPolicy::Accessory);
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
