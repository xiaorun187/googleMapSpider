#!/bin/bash
set -e

# 确保数据目录存在
mkdir -p /app/data /app/output

# 启动 Flask 应用
echo "Starting Flask application..."
exec python app.py
