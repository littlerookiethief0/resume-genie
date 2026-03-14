use std::process::{Command, Stdio};
use std::sync::{Arc, Mutex};
use std::thread;
use tauri::{AppHandle, Emitter, State, Manager};


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
    let script_path = resource_dir
        .join("_up_")
        .join("python-scripts")
        .join(format!("{}.py", site_id));

    // Python 虚拟环境路径
    #[cfg(target_os = "windows")]
    let venv_python = resource_dir
        .join("_up_")
        .join("python-scripts")
        .join(".venv")
        .join("Scripts")
        .join("python.exe");

    #[cfg(not(target_os = "windows"))]
    let venv_python = resource_dir
        .join("_up_")
        .join("python-scripts")
        .join(".venv")
        .join("bin")
        .join("python");

    // 检查脚本是否存在
    if !script_path.exists() {
        return Err(format!("Script not found: {:?}", script_path));
    }

    // 检查 Python 是否存在
    if !venv_python.exists() {
        return Err(format!("Python venv not found: {:?}", venv_python));
    }

    let mut child = Command::new(&venv_python)
        .arg("-u")
        .arg(&script_path)
        .current_dir(resource_dir.join("_up_").join("python-scripts"))
        .stdout(Stdio::inherit())
        .stderr(Stdio::inherit())
        .spawn()
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
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
