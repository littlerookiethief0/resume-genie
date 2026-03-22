# GitHub Actions 自动打包说明

代码推送到 GitHub 后，**在 GitHub 云端完成打包**，无需本机执行 `pnpm tauri build`。

## 怎么在 GitHub 上打包

1. **把代码推到 `main`**（本地执行 `git push origin main`）。推送成功后会自动跑工作流 **Build and Release**。
2. 或打开仓库 **Actions** → 选中 **Build and Release** → 右上角 **Run workflow** → **Run workflow**（手动再打一版）。
3. 等待任务变绿（约 10～40 分钟，视缓存而定）。
4. 在 **Actions** 里点进本次运行，页面底部 **Artifacts** 可下载 macOS / Windows 产物；同时会创建/更新 **Draft Release**（标签形如 `v0.2.7`），到 **Releases** 里可下载安装包或编辑后发布。

## 触发方式

1. **自动触发**：推送代码到 `main` 分支时自动构建
2. **手动触发**：在 GitHub Actions 页面点击 "Run workflow" 按钮

## 构建平台

- **macOS (Apple Silicon)**: aarch64-apple-darwin
  - 产物：.dmg 和 .app.tar.gz
  - 包含完整的 Python 环境和脚本
- **Windows (x64)**: x86_64-pc-windows-msvc
  - 产物：.msi 和 .exe (NSIS 安装包)
  - 包含完整的 Python 环境和脚本

## Python 环境打包

应用会自动打包以下内容：
- `python-scripts/*.py` - 所有 Python 脚本
- `python-scripts/.venv/**/*` - 完整的 Python 虚拟环境
- Playwright 浏览器驱动

构建时会自动：
1. 创建 Python 虚拟环境
2. 安装 requirements.txt 中的依赖
3. 安装 Playwright 浏览器
4. 将所有内容打包进应用

## 下载构建产物

1. 进入 GitHub 仓库的 Actions 页面
2. 点击最新的构建任务
3. 在页面底部的 "Artifacts" 区域下载：
   - `resume-genie-macos-aarch64` - macOS 安装包
   - `resume-genie-windows-x64` - Windows 安装包

## 发布版本

构建完成后会创建一个草稿 Release，你可以：
1. 进入 GitHub Releases 页面
2. 编辑草稿 Release
3. 添加更新日志
4. 点击 "Publish release" 发布

## 本地测试构建

### 准备 Python 环境

macOS/Linux:
```bash
bash scripts/prepare-python.sh
```

Windows:
```bash
scripts\prepare-python.bat
```

### 构建应用

macOS:
```bash
pnpm install
pnpm tauri build --target aarch64-apple-darwin
```

Windows:
```bash
pnpm install
pnpm tauri build --target x86_64-pc-windows-msvc
```

## 注意事项

- Python 环境会被完整打包进应用（约 200-300MB）
- 首次构建可能需要 30-40 分钟（下载依赖 + Python 环境）
- 后续构建会使用缓存，约 10-15 分钟
- 确保 `python-scripts/requirements.txt` 包含所有依赖
- Playwright 浏览器会自动安装并打包

## 故障排查

### Python 脚本找不到
- 检查 `src-tauri/tauri.conf.json` 中的 `bundle.resources` 配置
- 确保路径正确：`../python-scripts/*.py`

### 依赖缺失
- 更新 `python-scripts/requirements.txt`
- 重新运行 `scripts/prepare-python.sh`

### 构建失败
- 查看 GitHub Actions 日志
- 本地测试构建命令
- 检查 Python 版本（需要 3.12）
