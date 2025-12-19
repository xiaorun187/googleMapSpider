#!/bin/bash

# Docker容器启动脚本
# 专门用于在Docker容器内启动应用

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 错误处理
error_handler() {
    local line_number=$1
    log_error "脚本在第 $line_number 行发生错误"
    exit 1
}

# 设置错误处理
trap 'error_handler $LINENO' ERR

# 初始化函数
init_app() {
    log_info "初始化应用..."
    
    # 设置工作目录
    cd /app
    
    # 创建必要的目录
    mkdir -p output logs temp
    
    # 设置权限
    chmod 755 output logs temp
    
    # 初始化数据库（如果不存在）
    if [ ! -f "google_maps_data.db" ]; then
        log_info "创建新数据库..."
        python3 -c "
from db import init_database
try:
    init_database()
    print('数据库初始化成功')
except Exception as e:
    print(f'数据库初始化失败: {e}')
    exit(1)
"
    fi
    
    log_success "应用初始化完成"
}

# 健康检查
health_check() {
    log_info "执行健康检查..."
    
    # 检查关键文件
    if [ ! -f "app.py" ]; then
        log_error "app.py文件不存在"
        exit 1
    fi
    
    # 检查Python模块
    python3 -c "
try:
    import flask
    import selenium
    import sqlite3
    print('关键Python模块检查通过')
except ImportError as e:
    print(f'模块导入失败: {e}')
    exit(1)
"
    
    # 检查Chrome/ChromeDriver
    if [ -x "/usr/bin/google-chrome" ]; then
        log_success "Chrome可执行文件检查通过"
    else
        log_warning "Chrome可执行文件未找到或不可执行"
    fi
    
    if [ -x "/usr/local/bin/chromedriver" ]; then
        log_success "ChromeDriver可执行文件检查通过"
    else
        log_warning "ChromeDriver可执行文件未找到或不可执行"
    fi
    
    log_success "健康检查完成"
}

# 启动应用
start_app() {
    log_info "启动Flask应用..."
    
    # 设置环境变量
    export FLASK_ENV=${FLASK_ENV:-"production"}
    export PORT=${PORT:-5000}
    export CHROME_BIN="/usr/bin/google-chrome"
    export CHROMEDRIVER_PATH="/usr/local/bin/chromedriver"
    export IS_DOCKER="true"
    export PYTHONPATH="/app"
    
    # 确保app.py可执行
    chmod +x app.py
    
    # 启动应用
    exec python3 app.py
}

# 主函数
main() {
    log_info "Docker容器启动流程开始..."
    
    # 初始化应用
    init_app
    
    # 执行健康检查
    health_check
    
    # 启动应用
    start_app
}

# 脚本入口点
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi