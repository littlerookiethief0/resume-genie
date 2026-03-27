use std::process::{Command, Stdio};
use std::sync::{Arc, Mutex};
use std::thread;
use std::io::{BufRead, BufReader};
use serde_json::{json, Value};
use tauri::{AppHandle, Emitter, State, Manager};
use tauri::menu::{Menu, MenuItem};
use tauri::tray::{TrayIconBuilder, TrayIconEvent};
use tauri::image::Image;

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

#[tauri::command]
async fn verify_mobile_account(mobile: String) -> Result<Value, String> {
    let mobile = mobile.trim().to_string();
    let is_valid_mobile = mobile.len() == 11
        && mobile.starts_with('1')
        && mobile.chars().all(|c| c.is_ascii_digit());
    if !is_valid_mobile {
        return Ok(json!({"code": -1, "msg": "手机号格式错误", "data": 0}));
    }

    let client = reqwest::Client::new();
    let resp = client
        .post("http://mopinleads.58.com/account/verify")
        .json(&json!({ "mobile": mobile }))
        .send()
        .await
        .map_err(|e| format!("请求失败: {}", e))?;

    let status = resp.status();
    let body = resp
        .json::<Value>()
        .await
        .map_err(|e| format!("响应解析失败: {}", e))?;

    if !status.is_success() {
        return Err(format!("接口返回异常状态: {}", status));
    }
    Ok(body)
}

#[tauri::command]
async fn check_version(current_version: String) -> Result<Value, String> {
    let client = reqwest::Client::new();
    let url = format!(
        "https://jobdig.100dp.com/api/version/check?currentVersion={}",
        current_version
    );
    let resp = client
        .get(&url)
        .send()
        .await
        .map_err(|e| format!("请求失败: {}", e))?;

    let status = resp.status();
    let body = resp
        .json::<Value>()
        .await
        .map_err(|e| format!("响应解析失败: {}", e))?;

    if !status.is_success() {
        return Err(format!("接口返回异常状态: {}", status));
    }
    Ok(body)
}

fn get_log_file() -> Option<std::fs::File> {
    let home = {
        #[cfg(windows)]
        { std::env::var_os("USERPROFILE").map(std::path::PathBuf::from) }
        #[cfg(not(windows))]
        { std::env::var_os("HOME").map(std::path::PathBuf::from) }
    };
    let log_dir = home?.join(".resume-genie").join("logs");
    std::fs::create_dir_all(&log_dir).ok()?;
    let log_path = log_dir.join("script_stderr.log");
    std::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(log_path)
        .ok()
}

fn spawn_stderr_reader(stderr: std::process::ChildStderr, app: AppHandle, label: String) {
    thread::spawn(move || {
        use std::io::Write;
        let mut log_file = get_log_file();
        let reader = BufReader::new(stderr);
        for line in reader.lines() {
            if let Ok(line) = line {
                eprintln!("[{}] {}", label, line);
                let _ = app.emit("script_stderr", (&label, &line));
                if let Some(ref mut f) = log_file {
                    let _ = writeln!(f, "[{}] {}", label, line);
                }
            }
        }
    });
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

fn stop_all_running_scripts(app: &AppHandle) {
    if let Some((pid, site_id)) = app.state::<WakeScriptState>().0.lock().unwrap().take() {
        kill_process_by_pid(pid);
        let _ = app.emit("wake_script_finished", (site_id, false, Some(-1i32)));
    }
    if let Some((pid, site_id)) = app.state::<ParseScriptState>().0.lock().unwrap().take() {
        kill_process_by_pid(pid);
        let _ = app.emit("parse_script_finished", (site_id, false, Some(-1i32)));
    }
}

#[tauri::command]
async fn run_wake_script(
    app: AppHandle,
    state: State<'_, WakeScriptState>,
    site_id: String,
    days: i32,
    auto_parse: bool,
) -> Result<String, String> {
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

    // 不设置 PLAYWRIGHT_BROWSERS_PATH 指向包内目录：Camoufox 二进制由首次运行
    // `python -m camoufox fetch` 下载到用户缓存（camoufox/pkgman），不应打进安装包。
    let mut cmd = Command::new(&python_exe);
    cmd.arg("-u")
        .arg(&script_path)
        .current_dir(&script_dir)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .env("PYTHONUTF8", "1");

    // Windows: 隐藏控制台窗口
    #[cfg(windows)]
    cmd.creation_flags(0x08000000); // CREATE_NO_WINDOW

    let mut child = cmd.spawn()
        .map_err(|e| format!("Failed to execute script: {}", e))?;

    if let Some(stderr) = child.stderr.take() {
        spawn_stderr_reader(stderr, app.clone(), format!("wake:{}", site_id));
    }

    // 读取唤醒脚本的 stdout，解析 STEP: 前缀并发送事件
    let stdout = child.stdout.take();
    let app_stdout = app.clone();
    let site_id_stdout = site_id.clone();
    if let Some(stdout) = stdout {
        thread::spawn(move || {
            let reader = BufReader::new(stdout);
            for line in reader.lines() {
                if let Ok(line) = line {
                    if let Some(step_str) = line.strip_prefix("STEP:") {
                        if let Ok(step) = step_str.trim().parse::<i32>() {
                            let _ = app_stdout.emit("wake_step", (site_id_stdout.clone(), step));
                        }
                    } else {
                        eprintln!("[wake:{}] {}", site_id_stdout, line);
                    }
                }
            }
        });
    }

    let pid = child.id();
    let site_id_clone = site_id.clone();
    *state.0.lock().unwrap() = Some((pid, site_id.clone()));

    let state_inner = Arc::clone(&state.0);
    let script_dir_chain = script_dir.clone();
    let python_exe_chain = python_exe.clone();
    let app_chain = app.clone();
    thread::spawn(move || {
        let status = child.wait();
        state_inner.lock().unwrap().take();
        let (wake_ok, wake_code) = match &status {
            Ok(s) => (s.success(), s.code()),
            Err(_) => (false, None),
        };

        if !wake_ok {
            let _ = app_chain.emit("wake_script_finished", (site_id_clone.clone(), false, wake_code));
            return;
        }

        if auto_parse {
            let parse_script = script_dir_chain.join(format!("{}_resume.py", site_id_clone));
            if parse_script.exists() {
                let mut parse_cmd = Command::new(&python_exe_chain);
                parse_cmd
                    .arg("-u")
                    .arg(&parse_script)
                    .arg("--days")
                    .arg(days.to_string())
                    .current_dir(&script_dir_chain)
                    .stdout(Stdio::piped())
                    .stderr(Stdio::piped())
                    .env("PYTHONUTF8", "1");

                #[cfg(windows)]
                parse_cmd.creation_flags(0x08000000);

                if let Ok(mut parse_child) = parse_cmd.spawn() {
                    if let Some(stderr) = parse_child.stderr.take() {
                        spawn_stderr_reader(stderr, app_chain.clone(), format!("parse:{}", site_id_clone));
                    }
                    if let Some(stdout) = parse_child.stdout.take() {
                        let app_parse = app_chain.clone();
                        let site_parse = site_id_clone.clone();
                        thread::spawn(move || {
                            let reader = BufReader::new(stdout);
                            for line in reader.lines() {
                                if let Ok(line) = line {
                                    if line.starts_with("RESUME_DATA:") {
                                        if let Some(json_str) = line.strip_prefix("RESUME_DATA:") {
                                            let _ = app_parse.emit(
                                                "parse_resume_data",
                                                (site_parse.clone(), json_str),
                                            );
                                        }
                                    }
                                }
                            }
                        });
                    }

                    let parse_status = parse_child.wait();
                    let (parse_ok, parse_code) = match parse_status {
                        Ok(s) => (s.success(), s.code()),
                        Err(_) => (false, None),
                    };
                    let _ = app_chain.emit(
                        "wake_script_finished",
                        (site_id_clone, parse_ok, parse_code),
                    );
                    return;
                }
            }
        }

        let _ = app_chain.emit("wake_script_finished", (site_id_clone, true, wake_code));
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

/// 仅执行解析脚本 `{site_id}_resume.py`（主投/下载简历解析与保存）
#[tauri::command]
async fn run_parse_script(
    app: AppHandle,
    state: State<'_, ParseScriptState>,
    site_id: String,
    days: i32,
) -> Result<String, String> {
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
        return Err(format!("解析脚本不存在: {:?}", script_path));
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
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .env("PYTHONUTF8", "1");

    #[cfg(windows)]
    cmd.creation_flags(0x08000000);

    let mut child = cmd.spawn()
        .map_err(|e| format!("Failed to execute script: {}", e))?;

    if let Some(stderr) = child.stderr.take() {
        spawn_stderr_reader(stderr, app.clone(), format!("parse:{}", site_id));
    }

    let pid = child.id();
    *state.0.lock().unwrap() = Some((pid, site_id.clone()));

    // 读取stdout并发送事件
    let stdout = child.stdout.take().unwrap();
    let app_clone = app.clone();
    let site_id_for_stdout = site_id.clone();
    thread::spawn(move || {
        let reader = BufReader::new(stdout);
        for line in reader.lines() {
            if let Ok(line) = line {
                if line.starts_with("RESUME_DATA:") {
                    if let Some(json_str) = line.strip_prefix("RESUME_DATA:") {
                        let _ = app_clone.emit("parse_resume_data", (site_id_for_stdout.clone(), json_str));
                    }
                }
            }
        }
    });

    let state_inner = Arc::clone(&state.0);
    let app_for_finish = app.clone();
    let site_id_for_finish = site_id.clone();
    thread::spawn(move || {
        let status = child.wait();
        state_inner.lock().unwrap().take();
        let (success, code) = match &status {
            Ok(s) => (s.success(), s.code()),
            Err(_) => (false, None),
        };

        let _ = app_for_finish.emit("parse_script_finished", (site_id_for_finish, success, code));
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

        if cfg!(debug_assertions) {
            let project_root = resource_dir
                .parent().unwrap()
                .parent().unwrap()
                .parent().unwrap()
                .to_path_buf();
            project_root.join(relative)
        } else {
            let home = {
                #[cfg(windows)]
                { std::env::var_os("USERPROFILE").map(std::path::PathBuf::from) }
                #[cfg(not(windows))]
                { std::env::var_os("HOME").map(std::path::PathBuf::from) }
            };
            match home {
                Some(h) => h.join(".resume-genie").join("data").join(relative),
                None => resource_dir.join("_up_").join(relative),
            }
        }
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
        .invoke_handler(tauri::generate_handler![greet, verify_mobile_account, check_version, run_wake_script, stop_wake_script, run_parse_script, stop_parse_script, select_directory, open_directory])
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
                            stop_all_running_scripts(&app);
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
