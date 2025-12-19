#!/bin/bash

# Docker兼容部署脚本
# 适用于在Docker容器环境中部署Google地图爬虫应用

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

# 检查是否在Docker容器中运行
check_docker_env() {
    if [ -f /.dockerenv ] || [ -n "${CONTAINER_ID}" ] || grep -q 'docker\|lxc' /proc/1/cgroup 2>/dev/null; then
        log_info "检测到Docker容器环境"
        export DOCKER_ENV=true
    else
        log_info "未检测到Docker容器环境，将以兼容模式运行"
        export DOCKER_ENV=false
    fi
}

# 设置工作目录
setup_directories() {
    log_info "设置工作目录和权限..."
    
    # 应用根目录
    APP_ROOT=${APP_ROOT:-"/app"}
    cd "$APP_ROOT"
    
    # 创建必要的目录
    mkdir -p output logs temp
    chmod 755 output logs temp
    
    # 确保脚本有执行权限
    find . -name "*.py" -exec chmod +x {} \; 2>/dev/null || true
    
    log_success "目录设置完成"
}

# 清理函数
cleanup() {
    log_info "清理临时文件..."
    rm -rf /tmp/deploy_* 2>/dev/null || true
    rm -f /tmp/*.zip 2>/dev/null || true
}

# 错误处理
error_handler() {
    local line_number=$1
    log_error "脚本在第 $line_number 行发生错误"
    cleanup
    exit 1
}

# 设置错误处理
trap 'error_handler $LINENO' ERR

# 检查网络连接
check_network() {
    log_info "检查网络连接..."
    if ! ping -c 1 8.8.8.8 >/dev/null 2>&1; then
        log_warning "网络连接可能存在问题"
    else
        log_success "网络连接正常"
    fi
}

# 安装依赖
install_dependencies() {
    log_info "安装Python依赖..."
    
    # 检查requirements.txt是否存在
    if [ ! -f "requirements.txt" ]; then
        log_error "requirements.txt文件不存在"
        exit 1
    fi
    
    # 使用pip安装依赖
    if command -v pip3 >/dev/null 2>&1; then
        PIP_CMD="pip3"
    elif command -v pip >/dev/null 2>&1; then
        PIP_CMD="pip"
    else
        log_error "未找到pip命令"
        exit 1
    fi
    
    # 安装依赖
    $PIP_CMD install --no-cache-dir -r requirements.txt
    log_success "Python依赖安装完成"
}

# 初始化数据库
init_database() {
    log_info "初始化数据库..."
    
    # 检查数据库文件是否存在
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
    else
        log_info "数据库已存在，跳过初始化"
    fi
    
    log_success "数据库准备完成"
}

# 配置环境变量
configure_env() {
    log_info "配置环境变量..."
    
    # 设置Flask环境
    export FLASK_ENV=${FLASK_ENV:-"production"}
    export PORT=${PORT:-5000}
    
    # 设置Chrome相关环境变量
    export CHROME_BIN=${CHROME_BIN:-"/usr/bin/google-chrome"}
    export CHROMEDRIVER_PATH=${CHROMEDRIVER_PATH:-"/usr/local/bin/chromedriver"}
    
    # 设置Docker环境标识
    export IS_DOCKER=${IS_DOCKER:-"true"}
    
    # 设置应用特定环境变量
    export PYTHONPATH=${PYTHONPATH:-"$APP_ROOT"}
    
    log_success "环境变量配置完成"
}

# 健康检查
health_check() {
    log_info "执行健康检查..."
    
    # 检查关键文件
    local required_files=("app.py" "db.py" "requirements.txt")
    for file in "${required_files[@]}"; do
        if [ ! -f "$file" ]; then
            log_error "关键文件 $file 不存在"
            return 1
        fi
    done
    
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
    
    # 检查Chrome/ChromeDriver（如果在Docker环境中）
    if [ "$DOCKER_ENV" = "true" ]; then
        if [ -x "$CHROME_BIN" ]; then
            log_success "Chrome可执行文件检查通过"
        else
            log_warning "Chrome可执行文件未找到或不可执行"
        fi
        
        if [ -x "$CHROMEDRIVER_PATH" ]; then
            log_success "ChromeDriver可执行文件检查通过"
        else
            log_warning "ChromeDriver可执行文件未找到或不可执行"
        fi
    fi
    
    log_success "健康检查完成"
}

# 启动应用
start_application() {
    log_info "启动应用..."
    
    # 确保app.py可执行
    chmod +x app.py
    
    # 启动Flask应用
    if [ "$DOCKER_ENV" = "true" ]; then
        # 在Docker环境中，使用exec让应用成为主进程
        exec python3 app.py
    else
        # 在非Docker环境中，正常启动
        python3 app.py
    fi
}

# 主函数
main() {
    log_info "开始Docker兼容部署流程..."
    
    # 检查Docker环境
    check_docker_env
    
    # 设置目录
    setup_directories
    
    # 检查网络
    check_network
    
    # 安装依赖
    install_dependencies
    
    # 初始化数据库
    init_database
    
    # 配置环境变量
    configure_env
    
    # 执行健康检查
    health_check
    
    # 启动应用
    start_application
}

# 脚本入口点
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi