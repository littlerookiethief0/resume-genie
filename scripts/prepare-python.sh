#!/bin/bash
# 为 GitHub Actions 构建准备 Python 虚拟环境

set -e

echo "🐍 准备 Python 虚拟环境..."

cd python-scripts

# 检查是否已有虚拟环境
if [ -d ".venv" ]; then
    echo "✅ 虚拟环境已存在"
else
    echo "📦 创建虚拟环境..."
    python3 -m venv .venv
fi

# 激活虚拟环境
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
elif [ -f ".venv/Scripts/activate" ]; then
    source .venv/Scripts/activate
else
    echo "❌ 无法找到虚拟环境激活脚本"
    exit 1
fi

# 安装依赖
if [ -f "requirements.txt" ]; then
    echo "📥 安装 Python 依赖..."
    pip install --upgrade pip
    pip install -r requirements.txt
    echo "✅ Python 依赖安装完成"
else
    echo "⚠️  未找到 requirements.txt，跳过依赖安装"
fi

echo "✅ Python 环境准备完成"
