@echo off
REM 为 GitHub Actions 构建准备 Python 虚拟环境 (Windows)
setlocal enabledelayedexpansion

echo 🐍 准备 Python 虚拟环境...

cd python-scripts
if errorlevel 1 (
    echo ❌ 无法进入 python-scripts 目录
    exit /b 1
)

REM 检查是否已有虚拟环境
if exist ".venv" (
    echo ✅ 虚拟环境已存在
) else (
    echo 📦 创建虚拟环境...
    python -m venv .venv
    if errorlevel 1 (
        echo ❌ 创建虚拟环境失败
        exit /b 1
    )
)

REM 激活虚拟环境
call .venv\Scripts\activate.bat
if errorlevel 1 (
    echo ❌ 激活虚拟环境失败
    exit /b 1
)

REM 安装依赖
if exist "requirements.txt" (
    echo 📥 安装 Python 依赖...
    python -m pip install --upgrade pip
    if errorlevel 1 (
        echo ❌ 升级 pip 失败
        exit /b 1
    )
    pip install -r requirements.txt
    if errorlevel 1 (
        echo ❌ 安装依赖失败
        exit /b 1
    )
    echo ✅ Python 依赖安装完成
) else (
    echo ⚠️  未找到 requirements.txt，跳过依赖安装
)

echo ✅ Python 环境准备完成
