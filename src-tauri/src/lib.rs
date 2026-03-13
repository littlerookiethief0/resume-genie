use std::process::{Command, Stdio};

#[tauri::command]
fn greet(name: &str) -> String {
    format!("Hello, {}! You've been greeted from Rust!", name)
}

#[tauri::command]
async fn run_wake_script(site_id: String) -> Result<String, String> {
    // 获取当前可执行文件所在目录，然后向上找到项目根目录
    let exe_dir = std::env::current_exe()
        .map_err(|e| format!("Failed to get exe path: {}", e))?
        .parent()
        .ok_or("Failed to get parent dir")?
        .to_path_buf();

    // 在开发模式下，从 src-tauri/target/debug 向上 3 级到项目根
    // 在生产模式下，需要根据实际打包结构调整
    let project_root = exe_dir
        .parent()
        .and_then(|p| p.parent())
        .and_then(|p| p.parent())
        .ok_or("Failed to find project root")?
        .to_path_buf();

    // Python 脚本路径
    let script_path = project_root
        .join("python-scripts")
        .join(format!("{}.py", site_id));

    // Python 虚拟环境路径
    let venv_python = project_root
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

    // 执行 Python 脚本（继承 stdout/stderr，这样可以在终端看到输出）
    let mut child = Command::new(&venv_python)
        .arg("-u")  // Python unbuffered 模式
        .arg(&script_path)
        .current_dir(project_root.join("python-scripts"))
        .stdout(Stdio::inherit())  // 继承父进程的 stdout
        .stderr(Stdio::inherit())  // 继承父进程的 stderr
        .spawn()
        .map_err(|e| format!("Failed to execute script: {}", e))?;

    // 等待脚本执行完成
    let status = child.wait()
        .map_err(|e| format!("Failed to wait for script: {}", e))?;

    if status.success() {
        Ok("Script executed successfully".to_string())
    } else {
        Err(format!("Script failed with exit code: {:?}", status.code()))
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![greet, run_wake_script])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
