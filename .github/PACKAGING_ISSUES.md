# Tauri + Python 打包问题汇总

本文档记录了 resume-genie 项目在 GitHub Actions 自动打包过程中遇到的所有问题及解决方案。

## 目录
- [Rust 编译问题](#rust-编译问题)
- [Tauri 配置问题](#tauri-配置问题)
- [GitHub Actions 问题](#github-actions-问题)
- [资源打包问题](#资源打包问题)
- [Python 环境问题](#python-环境问题)
- [Windows 特定问题](#windows-特定问题)

---

## Rust 编译问题

### 问题 1: Manager trait 缺失

**错误信息：**
```
no method named 'path' found for struct 'AppHandle<R>' in the current scope
```

**原因：**
使用 `app.path()` 方法需要导入 `Manager` trait。

**解决方案：**
```rust
use tauri::{AppHandle, Emitter, State, Manager};  // 添加 Manager
```

---

## Tauri 配置问题

### 问题 2: 重复的 identifier 字段

**错误信息：**
```
Additional properties are not allowed ('identifier' was unexpected)
```

**原因：**
`identifier` 字段在 `tauri.conf.json` 中重复定义（顶层和 bundle 中都有）。

**解决方案：**
只在顶层保留 `identifier`，从 `bundle` 部分删除：
```json
{
  "identifier": "com.resumegenie.app",  // 保留
  "bundle": {
    // "identifier": "..."  // 删除
  }
}
```

### 问题 3: Windows 缺少 .ico 图标

**错误信息：**
```
failed to bundle project `Couldn't find a .ico icon`
```

**原因：**
Windows 打包需要 `.ico` 格式的图标文件。

**解决方案：**
在 `tauri.conf.json` 的 `icon` 数组中添加：
```json
"icon": [
  "icons/32x32.png",
  "icons/128x128.png",
  "icons/128x128@2x.png",
  "icons/icon.icns",
  "icons/icon.ico",      // 添加这行
  "icons/icon.png"
]
```

---

## GitHub Actions 问题

### 问题 4: GitHub API 权限不足

**错误信息：**
```
Resource not accessible by integration
```

**原因：**
默认的 `GITHUB_TOKEN` 没有创建 release 的权限。

**解决方案：**
在 workflow 文件中添加权限声明：
```yaml
permissions:
  contents: write
  packages: write
```

### 问题 5: Node.js 20 弃用警告

**警告信息：**
```
Node.js 20 actions are deprecated
```

**原因：**
GitHub Actions 将弃用 Node.js 20。

**解决方案：**
添加环境变量强制使用 Node.js 24：
```yaml
env:
  FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true
```

---

## 资源打包问题

### 问题 6: macOS 和 Windows 资源路径不一致

**现象：**
- macOS: `Resources/_up_/python-scripts/`
- Windows: `AppData/Local/app-name/python-scripts/`

**原因：**
Tauri 在不同平台处理 `../` 路径的方式不同。macOS 会创建 `_up_` 目录，Windows 不会。

**解决方案：**
动态检测路径：
```rust
let script_dir = if resource_dir.join("_up_").join("python-scripts").exists() {
    resource_dir.join("_up_").join("python-scripts")
} else {
    resource_dir.join("python-scripts")
};
```

---

## Python 环境问题

### 问题 7: Python 虚拟环境不可重定位

**现象：**
在 GitHub Actions 创建的 Python venv 在用户机器上无法运行。

**原因：**
Python 虚拟环境包含硬编码的路径，不能跨机器使用。

**解决方案：**
使用 python-build-standalone 提供的可重定位 Python：

```yaml
- name: Download standalone Python (macOS)
  if: matrix.platform == 'macos-latest'
  run: |
    cd python-scripts
    curl -L https://github.com/indygreg/python-build-standalone/releases/download/20241016/cpython-3.12.7+20241016-aarch64-apple-darwin-install_only_stripped.tar.gz -o python.tar.gz
    mkdir -p python
    tar -xzf python.tar.gz -C python --strip-components=1
    rm python.tar.gz
    ./python/bin/python3 -m pip install -r requirements.txt

- name: Download standalone Python (Windows)
  if: matrix.platform == 'windows-latest'
  run: |
    cd python-scripts
    curl -L https://github.com/indygreg/python-build-standalone/releases/download/20241016/cpython-3.12.7+20241016-x86_64-pc-windows-msvc-shared-install_only_stripped.tar.gz -o python.tar.gz
    mkdir python
    tar -xzf python.tar.gz -C python --strip-components=1
    del python.tar.gz
    python\python.exe -m pip install -r requirements.txt
```

Rust 代码中使用打包的 Python：
```rust
#[cfg(target_os = "windows")]
let python_exe = script_dir.join("python").join("python.exe");

#[cfg(not(target_os = "windows"))]
let python_exe = script_dir.join("python").join("bin").join("python3");
```

---

## Windows 特定问题

### 问题 8: 启动 Python 脚本时弹出控制台窗口

**现象：**
Windows 上运行 Python 脚本时会弹出黑色的控制台窗口。

**原因：**
Windows 默认为控制台程序创建新窗口。

**解决方案：**
使用 `CREATE_NO_WINDOW` 标志：

```rust
#[cfg(windows)]
use std::os::windows::process::CommandExt;

// 创建命令时
let mut cmd = Command::new(&python_exe);
cmd.arg("-u")
    .arg(&script_path)
    .current_dir(&script_dir)
    .stdout(Stdio::inherit())
    .stderr(Stdio::inherit());

// Windows: 隐藏控制台窗口
#[cfg(windows)]
cmd.creation_flags(0x08000000); // CREATE_NO_WINDOW

let mut child = cmd.spawn()?;
```

---

## 最终配置

### tauri.conf.json
```json
{
  "identifier": "com.resumegenie.app",
  "bundle": {
    "icon": [
      "icons/32x32.png",
      "icons/128x128.png",
      "icons/128x128@2x.png",
      "icons/icon.icns",
      "icons/icon.ico",
      "icons/icon.png"
    ],
    "resources": [
      "../python-scripts"
    ]
  }
}
```

### .github/workflows/build.yml
```yaml
permissions:
  contents: write
  packages: write

env:
  FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true

jobs:
  build:
    steps:
      - name: Download standalone Python (macOS)
        if: matrix.platform == 'macos-latest'
        run: |
          cd python-scripts
          curl -L https://github.com/indygreg/python-build-standalone/releases/download/20241016/cpython-3.12.7+20241016-aarch64-apple-darwin-install_only_stripped.tar.gz -o python.tar.gz
          mkdir -p python
          tar -xzf python.tar.gz -C python --strip-components=1
          rm python.tar.gz
          ./python/bin/python3 -m pip install -r requirements.txt

      - name: Download standalone Python (Windows)
        if: matrix.platform == 'windows-latest'
        run: |
          cd python-scripts
          curl -L https://github.com/indygreg/python-build-standalone/releases/download/20241016/cpython-3.12.7+20241016-x86_64-pc-windows-msvc-shared-install_only_stripped.tar.gz -o python.tar.gz
          mkdir python
          tar -xzf python.tar.gz -C python --strip-components=1
          del python.tar.gz
          python\python.exe -m pip install -r requirements.txt
```

### src-tauri/src/lib.rs
```rust
use std::process::{Command, Stdio};
use std::sync::{Arc, Mutex};
use std::thread;
use tauri::{AppHandle, Emitter, State, Manager};

#[cfg(windows)]
use std::os::windows::process::CommandExt;

#[tauri::command]
async fn run_wake_script(app: AppHandle, state: State<'_, WakeScriptState>, site_id: String) -> Result<String, String> {
    let resource_dir = app.path()
        .resource_dir()
        .map_err(|e| format!("Failed to get resource dir: {}", e))?;

    // 动态检测资源路径
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

    if !script_path.exists() {
        return Err(format!("Script not found: {:?}", script_path));
    }

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
    cmd.creation_flags(0x08000000);

    let mut child = cmd.spawn()
        .map_err(|e| format!("Failed to execute script: {}", e))?;

    // ... 其余代码
}
```

---

## 关键要点

1. **Python 环境必须可重定位**：使用 python-build-standalone
2. **资源路径需要跨平台兼容**：动态检测 `_up_` 目录
3. **Windows 需要隐藏控制台**：使用 `CREATE_NO_WINDOW` 标志
4. **GitHub Actions 需要正确权限**：添加 `permissions` 配置
5. **图标文件要完整**：包含 `.ico` 文件用于 Windows

---

## 参考资源

- [python-build-standalone](https://github.com/indygreg/python-build-standalone)
- [Tauri 文档](https://tauri.app/v2/guides/)
- [GitHub Actions 权限](https://docs.github.com/en/actions/security-guides/automatic-token-authentication)
