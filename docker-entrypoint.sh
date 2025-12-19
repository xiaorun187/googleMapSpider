#!/bin/bash

# Docker容器入口点脚本
# 用于启动Flask应用

set -e  # 遇到错误立即退出

echo "========================================="
echo "Google Maps Spider - Docker容器启动中..."
echo "========================================="

# 检查环境变量
if [ -z "$PORT" ]; then
    export PORT=5000
fi

echo "Flask应用将监听端口: $PORT"

# 确保output目录存在
mkdir -p /app/output

# 检查Chrome是否可用
echo "检查Chrome浏览器..."
if ! command -v google-chrome &> /dev/null; then
    echo "错误: Chrome浏览器未找到"
    exit 1
fi

# 检查ChromeDriver是否可用
echo "检查ChromeDriver..."
if ! command -v chromedriver &> /dev/null; then
    echo "错误: ChromeDriver未找到"
    exit 1
fi

# 显示Chrome和ChromeDriver版本
echo "Chrome版本: $(google-chrome --version)"
echo "ChromeDriver版本: $(chromedriver --version)"

# 初始化数据库（如果需要）
echo "初始化数据库..."
python -c "from db import init_db; init_db()" || echo "数据库初始化失败，但继续启动应用..."

# 启动Flask应用
echo "启动Flask应用..."
echo "========================================="
exec python app.py