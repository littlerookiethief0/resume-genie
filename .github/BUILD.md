# GitHub Actions 自动打包说明

## 触发方式

1. **自动触发**：推送代码到 `main` 分支时自动构建
2. **手动触发**：在 GitHub Actions 页面点击 "Run workflow" 按钮

## 构建平台

- **macOS (Apple Silicon)**: aarch64-apple-darwin
  - 产物：.dmg 和 .app.tar.gz
- **Windows (x64)**: x86_64-pc-windows-msvc
  - 产物：.msi 和 .exe (NSIS 安装包)

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

### macOS
```bash
pnpm install
pnpm tauri build --target aarch64-apple-darwin
```

### Windows
```bash
pnpm install
pnpm tauri build --target x86_64-pc-windows-msvc
```

## 注意事项

- Python 脚本目录 `python-scripts/` 不会被打包进应用
- 如需打包 Python 环境，需要额外配置 Tauri 的资源文件
- 首次构建可能需要 20-30 分钟（下载依赖）
- 后续构建会使用缓存，约 5-10 分钟
