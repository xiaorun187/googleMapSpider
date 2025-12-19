#!/bin/bash

# 一键部署脚本 - Google Maps Spider
# 用途: 将本地代码上传到服务器并自动部署

set -e  # 遇到错误立即退出

# 配置变量
SERVER_IP="155.138.226.211"
SERVER_USER="root"
SERVER_PATH="/opt/google-maps-spider"
LOCAL_PATH="$(dirname "$0")"
DEPLOY_PACKAGE="deploy-$(date +%Y%m%d-%H%M%S).zip"

# 颜色输出
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

# 显示帮助信息
show_help() {
    echo "Google Maps Spider 一键部署脚本"
    echo ""
    echo "用法: $0 [选项]"
    echo ""
    echo "选项:"
    echo "  deploy              完整部署 (默认: 打包 -> 上传 -> 部署)"
    echo "  upload              仅上传代码包"
    echo "  update              仅更新服务器代码并重启容器"
    echo "  status              检查服务器应用状态"
    echo "  logs                查看应用日志"
    echo "  help                显示此帮助信息"
    echo ""
    echo "示例:"
    echo "  $0                  # 执行完整部署"
    echo "  $0 deploy           # 执行完整部署"
    echo "  $0 upload           # 仅上传代码"
    echo "  $0 update           # 仅更新并重启"
    echo "  $0 status           # 检查状态"
}

# 检查本地环境
check_local_env() {
    log_info "检查本地环境..."
    
    # 检查必要文件
    if [ ! -f "$LOCAL_PATH/Dockerfile" ]; then
        log_error "Dockerfile 不存在!"
        exit 1
    fi
    
    if [ ! -f "$LOCAL_PATH/docker-compose.yml" ]; then
        log_error "docker-compose.yml 不存在!"
        exit 1
    fi
    
    # 检查SSH连接
    if ! ssh -o BatchMode=yes -o ConnectTimeout=5 $SERVER_USER@$SERVER_IP exit 2>/dev/null; then
        log_error "无法连接到服务器 $SERVER_IP，请检查SSH配置"
        exit 1
    fi
    
    log_success "本地环境检查通过"
}

# 打包代码
package_code() {
    log_info "打包代码..."
    
    cd "$LOCAL_PATH"
    
    # 创建临时目录
    TEMP_DIR=$(mktemp -d)
    
    # 复制必要文件
    cp -r app.py static templates requirements.txt Dockerfile docker-compose.yml docker-entrypoint.sh deploy-status.sh "$TEMP_DIR/" 2>/dev/null || true
    
    # 创建部署包
    cd "$TEMP_DIR"
    zip -r "$LOCAL_PATH/$DEPLOY_PACKAGE" . > /dev/null
    
    # 清理临时目录
    rm -rf "$TEMP_DIR"
    
    log_success "代码打包完成: $DEPLOY_PACKAGE"
}

# 上传代码到服务器
upload_code() {
    log_info "上传代码到服务器..."
    
    # 确保服务器目录存在
    ssh $SERVER_USER@$SERVER_IP "mkdir -p $SERVER_PATH"
    
    # 上传部署包
    scp "$LOCAL_PATH/$DEPLOY_PACKAGE" $SERVER_USER@$SERVER_IP:$SERVER_PATH/
    
    # 在服务器解压
    ssh $SERVER_USER@$SERVER_IP "cd $SERVER_PATH && unzip -o $DEPLOY_PACKAGE && rm $DEPLOY_PACKAGE"
    
    log_success "代码上传完成"
}

# 在服务器部署应用
deploy_app() {
    log_info "在服务器部署应用..."
    
    # 停止现有容器
    ssh $SERVER_USER@$SERVER_IP "cd $SERVER_PATH && docker-compose down 2>/dev/null || true"
    
    # 构建并启动新容器
    ssh $SERVER_USER@$SERVER_IP "cd $SERVER_PATH && docker-compose up -d --build"
    
    log_success "应用部署完成"
}

# 检查应用状态
check_status() {
    log_info "检查应用状态..."
    
    # 获取容器名称
    CONTAINER_NAME=$(ssh $SERVER_USER@$SERVER_IP "cd $SERVER_PATH && docker-compose ps -q" | xargs -I {} ssh $SERVER_USER@$SERVER_IP "docker inspect {} --format '{{.Name}}' | sed 's/\///'")
    
    if [ -z "$CONTAINER_NAME" ]; then
        log_error "未找到运行中的容器"
        return 1
    fi
    
    # 使用状态检查脚本
    ssh $SERVER_USER@$SERVER_IP "cd $SERVER_PATH && ./deploy-status.sh status $CONTAINER_NAME"
}

# 查看应用日志
show_logs() {
    log_info "查看应用日志..."
    ssh $SERVER_USER@$SERVER_IP "cd $SERVER_PATH && docker-compose logs -f --tail=50"
}

# 仅更新代码并重启
update_only() {
    log_info "更新服务器代码并重启应用..."
    
    # 上传代码
    upload_code
    
    # 重启容器
    ssh $SERVER_USER@$SERVER_IP "cd $SERVER_PATH && docker-compose restart"
    
    log_success "代码更新并重启完成"
}

# 清理本地部署包
cleanup() {
    if [ -f "$LOCAL_PATH/$DEPLOY_PACKAGE" ]; then
        rm "$LOCAL_PATH/$DEPLOY_PACKAGE"
        log_info "已清理本地部署包: $DEPLOY_PACKAGE"
    fi
}

# 主函数
main() {
    local command=${1:-deploy}
    
    case $command in
        "deploy")
            log_info "开始完整部署流程..."
            check_local_env
            package_code
            upload_code
            deploy_app
            sleep 5  # 等待容器启动
            check_status
            cleanup
            log_success "完整部署完成!"
            ;;
        "upload")
            log_info "开始上传代码..."
            check_local_env
            package_code
            upload_code
            cleanup
            log_success "代码上传完成!"
            ;;
        "update")
            log_info "开始更新代码..."
            check_local_env
            update_only
            sleep 3  # 等待容器重启
            check_status
            log_success "代码更新完成!"
            ;;
        "status")
            check_status
            ;;
        "logs")
            show_logs
            ;;
        "help"|"-h"|"--help")
            show_help
            ;;
        *)
            log_error "未知命令: $command"
            show_help
            exit 1
            ;;
    esac
}

# 捕获退出信号，执行清理
trap cleanup EXIT

# 执行主函数
main "$@"