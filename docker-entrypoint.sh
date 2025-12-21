#!/bin/bash
set -e

# 启动 Flask 应用
echo "Starting Flask application..."
exec python app.py
