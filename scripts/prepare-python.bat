@echo off
REM 为 GitHub Actions 构建准备 Python 虚拟环境 (Windows)

echo 🐍 准备 Python 虚拟环境...

cd python-scripts

REM 检查是否已有虚拟环境
if exist ".venv" (
    echo ✅ 虚拟环境已存在
) else (
    echo 📦 创建虚拟环境...
    python -m venv .venv
)

REM 激活虚拟环境
call .venv\Scripts\activate.bat

REM 安装依赖
if exist "requirements.txt" (
    echo 📥 安装 Python 依赖...
    python -m pip install --upgrade pip
    pip install -r requirements.txt
    echo ✅ Python 依赖安装完成
) else (
    echo ⚠️  未找到 requirements.txt，跳过依赖安装
)

REM 安装 Playwright 浏览器（如果需要）
pip list | findstr playwright >nul
if %errorlevel% equ 0 (
    echo 🌐 安装 Playwright 浏览器...
    playwright install chromium
    echo ✅ Playwright 浏览器安装完成
)

echo ✅ Python 环境准备完成
