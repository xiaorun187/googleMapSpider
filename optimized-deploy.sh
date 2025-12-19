#!/bin/bash

# 优化的一键部署脚本 - Google Maps Spider
# 具备并行处理、详细日志、错误恢复、版本控制等功能

set -e  # 遇到错误立即退出

# 全局变量
SERVER_IP="155.138.226.211"
SERVER_USER="root"
SERVER_PATH="/opt/google-maps-spider"
LOCAL_PATH="$(cd "$(dirname "$0")" && pwd)"
DEPLOY_PACKAGE="deploy-$(date +%Y%m%d-%H%M%S).zip"
LOG_DIR="$LOCAL_PATH/logs"
LOG_FILE="$LOG_DIR/deploy-$(date +%Y%m%d-%H%M%S).log"
TEMP_DIR=""
BACKUP_DIR="$SERVER_PATH/backups"
MAX_BACKUPS=5
PARALLEL_UPLOADS=3
RESOURCE_MONITOR_INTERVAL=5
DEPLOYMENT_ID="$(date +%s)"
VERSION_FILE="$LOCAL_PATH/.deploy_version"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 进度条字符
SPINNER="⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

# 初始化日志目录
init_logging() {
    mkdir -p "$LOG_DIR"
    exec > >(tee -a "$LOG_FILE")
    exec 2>&1
    
    # 创建日志文件
    touch "$LOG_FILE"
    echo "======================================" | tee -a "$LOG_FILE"
    echo "部署开始时间: $(date)" | tee -a "$LOG_FILE"
    echo "部署ID: $DEPLOYMENT_ID" | tee -a "$LOG_FILE"
    echo "======================================" | tee -a "$LOG_FILE"
}

# 日志函数
log_info() {
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${BLUE}[INFO $timestamp]${NC} $1" | tee -a "$LOG_FILE"
}

log_success() {
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${GREEN}[SUCCESS $timestamp]${NC} $1" | tee -a "$LOG_FILE"
}

log_warning() {
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${YELLOW}[WARNING $timestamp]${NC} $1" | tee -a "$LOG_FILE"
}

log_error() {
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${RED}[ERROR $timestamp]${NC} $1" | tee -a "$LOG_FILE"
}

log_debug() {
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${PURPLE}[DEBUG $timestamp]${NC} $1" | tee -a "$LOG_FILE"
}

# 显示进度条
show_progress() {
    local current=$1
    local total=$2
    local desc=$3
    local percent=$((current * 100 / total))
    local filled=$((percent / 2))
    local empty=$((50 - filled))
    
    printf "\r${CYAN}[$desc]${NC} ["
    printf "%*s" $filled | tr ' ' '='
    printf "%*s" $empty | tr ' ' '-'
    printf "] %d%% (%d/%d)" $percent $current $total
}

# 显示旋转动画
show_spinner() {
    local pid=$1
    local desc=$2
    local delay=0.1
    local spin_count=0
    
    while [ "$(ps a | awk '{print $1}' | grep $pid)" ]; do
        local spin_char=${SPINNER:spin_count:1}
        printf "\r${CYAN}[$desc]${NC} ${spin_char} "
        spin_count=$(( (spin_count + 1) % ${#SPINNER} ))
        sleep $delay
    done
    printf "\r${CYAN}[$desc]${NC} ✓ \n"
}

# 检测操作系统
detect_os() {
    case "$(uname -s)" in
        Linux*)     OS_TYPE="Linux";;
        Darwin*)    OS_TYPE="macOS";;
        CYGWIN*|MINGW*|MSYS*) OS_TYPE="Windows";;
        *)          OS_TYPE="Unknown";;
    esac
    log_debug "检测到操作系统: $OS_TYPE"
}

# 检查本地环境
check_local_env() {
    log_info "检查本地环境..."
    
    # 检测操作系统
    detect_os
    
    # 检查必要文件
    local required_files=("Dockerfile" "docker-compose.yml" "app.py" "requirements.txt")
    for file in "${required_files[@]}"; do
        if [ ! -f "$LOCAL_PATH/$file" ]; then
            log_error "必要文件不存在: $file"
            return 1
        fi
    done
    
    # 检查SSH连接
    log_info "检查SSH连接..."
    if ! ssh -o BatchMode=yes -o ConnectTimeout=5 $SERVER_USER@$SERVER_IP exit 2>/dev/null; then
        log_error "无法连接到服务器 $SERVER_IP，请检查SSH配置"
        return 1
    fi
    
    # 检查服务器环境
    log_info "检查服务器环境..."
    if ! ssh $SERVER_USER@$SERVER_IP "command -v docker >/dev/null 2>&1"; then
        log_error "服务器未安装Docker"
        return 1
    fi
    
    if ! ssh $SERVER_USER@$SERVER_IP "command -v docker-compose >/dev/null 2>&1"; then
        log_error "服务器未安装Docker Compose"
        return 1
    fi
    
    log_success "本地环境检查通过"
    return 0
}

# 资源监控
monitor_resources() {
    local monitor_pid=$1
    local duration=${2:-60}  # 默认监控60秒
    
    log_debug "启动资源监控，PID: $monitor_pid，持续时间: ${duration}秒"
    
    # 本地资源监控
    (
        local count=0
        while [ $count -lt $duration ]; do
            if [ "$(uname -s)" = "Linux" ]; then
                local cpu_usage=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1)
                local mem_usage=$(free -m | awk 'NR==2{printf "%.1f", $3*100/$2}')
                log_debug "本地资源 - CPU: ${cpu_usage}%, 内存: ${mem_usage}%"
            elif [ "$(uname -s)" = "Darwin" ]; then
                local cpu_usage=$(top -l 1 | grep "CPU usage" | awk '{print $3}' | cut -d'%' -f1)
                local mem_usage=$(vm_stat | grep "Pages free" | awk '{print $3}' | sed 's/\.//')
                log_debug "本地资源 - CPU: ${cpu_usage}%, 可用内存页: ${mem_usage}"
            fi
            sleep $RESOURCE_MONITOR_INTERVAL
            count=$((count + RESOURCE_MONITOR_INTERVAL))
        done
    ) &
    
    local local_monitor_pid=$!
    
    # 服务器资源监控
    (
        ssh $SERVER_USER@$SERVER_IP "
            count=0
            while [ \$count -lt $duration ]; do
                cpu_usage=\$(top -bn1 | grep 'Cpu(s)' | awk '{print \$2}' | cut -d'%' -f1)
                mem_usage=\$(free -m | awk 'NR==2{printf \"%.1f\", \$3*100/\$2}')
                echo \"[\$(date '+%Y-%m-%d %H:%M:%S')] 服务器资源 - CPU: \${cpu_usage}%, 内存: \${mem_usage}%\"
                sleep $RESOURCE_MONITOR_INTERVAL
                count=\$((count + RESOURCE_MONITOR_INTERVAL))
            done
        " >> "$LOG_FILE" 2>&1
    ) &
    
    local server_monitor_pid=$!
    
    # 等待主进程完成
    wait $monitor_pid
    
    # 停止监控
    kill $local_monitor_pid $server_monitor_pid 2>/dev/null || true
    log_debug "资源监控已停止"
}

# 并行打包代码
package_code() {
    log_info "开始打包代码..."
    
    # 创建临时目录
    TEMP_DIR=$(mktemp -d)
    log_debug "创建临时目录: $TEMP_DIR"
    
    # 创建后台任务列表
    local pids=()
    local task_count=0
    local total_tasks=7  # 预估任务总数
    
    # 任务1: 复制核心文件
    (
        log_debug "复制核心文件..."
        cp app.py db.py scraper.py requirements.txt Dockerfile docker-compose.yml "$TEMP_DIR/"
        log_debug "核心文件复制完成"
    ) &
    pids+=($!)
    task_count=$((task_count + 1))
    show_progress $task_count $total_tasks "打包代码"
    
    # 任务2: 复制静态文件
    (
        log_debug "复制静态文件..."
        if [ -d "static" ]; then
            cp -r static "$TEMP_DIR/"
        fi
        log_debug "静态文件复制完成"
    ) &
    pids+=($!)
    task_count=$((task_count + 1))
    show_progress $task_count $total_tasks "打包代码"
    
    # 任务3: 复制模板文件
    (
        log_debug "复制模板文件..."
        if [ -d "templates" ]; then
            cp -r templates "$TEMP_DIR/"
        fi
        log_debug "模板文件复制完成"
    ) &
    pids+=($!)
    task_count=$((task_count + 1))
    show_progress $task_count $total_tasks "打包代码"
    
    # 任务4: 复制脚本文件
    (
        log_debug "复制脚本文件..."
        if [ -f "docker-entrypoint.sh" ]; then
            cp docker-entrypoint.sh "$TEMP_DIR/"
        fi
        if [ -f "deploy-status.sh" ]; then
            cp deploy-status.sh "$TEMP_DIR/"
        fi
        log_debug "脚本文件复制完成"
    ) &
    pids+=($!)
    task_count=$((task_count + 1))
    show_progress $task_count $total_tasks "打包代码"
    
    # 任务5: 复制模型文件
    (
        log_debug "复制模型文件..."
        if [ -d "models" ]; then
            cp -r models "$TEMP_DIR/"
        fi
        log_debug "模型文件复制完成"
    ) &
    pids+=($!)
    task_count=$((task_count + 1))
    show_progress $task_count $total_tasks "打包代码"
    
    # 任务6: 复制工具文件
    (
        log_debug "复制工具文件..."
        if [ -d "utils" ]; then
            cp -r utils "$TEMP_DIR/"
        fi
        if [ -d "validators" ]; then
            cp -r validators "$TEMP_DIR/"
        fi
        log_debug "工具文件复制完成"
    ) &
    pids+=($!)
    task_count=$((task_count + 1))
    show_progress $task_count $total_tasks "打包代码"
    
    # 等待所有复制任务完成
    for pid in "${pids[@]}"; do
        wait $pid
    done
    
    # 任务7: 创建压缩包
    (
        log_debug "创建压缩包..."
        cd "$TEMP_DIR"
        zip -r "$DEPLOY_PACKAGE" . > /dev/null
        log_debug "压缩包创建完成"
    ) &
    local zip_pid=$!
    show_spinner $zip_pid "创建压缩包"
    wait $zip_pid
    task_count=$((task_count + 1))
    show_progress $task_count $total_tasks "打包代码"
    
    # 检查压缩包
    if [ ! -f "$TEMP_DIR/$DEPLOY_PACKAGE" ]; then
        log_error "创建部署包失败"
        return 1
    fi
    
    local package_size=$(ls -lh "$TEMP_DIR/$DEPLOY_PACKAGE" | awk '{print $5}')
    log_info "部署包大小: $package_size"
    
    # 移动部署包到项目目录
    mv "$TEMP_DIR/$DEPLOY_PACKAGE" "$LOCAL_PATH/"
    
    log_success "代码打包完成: $DEPLOY_PACKAGE"
    return 0
}

# 并行上传代码
upload_code() {
    log_info "开始上传代码到服务器..."
    
    # 检查部署包是否存在
    if [ ! -f "$LOCAL_PATH/$DEPLOY_PACKAGE" ]; then
        log_error "部署包不存在: $LOCAL_PATH/$DEPLOY_PACKAGE"
        return 1
    fi
    
    # 确保服务器目录存在
    ssh $SERVER_USER@$SERVER_IP "mkdir -p $SERVER_PATH $BACKUP_DIR"
    
    # 启动资源监控
    monitor_resources $$ 30 &
    local monitor_pid=$!
    
    # 上传部署包
    (
        scp "$LOCAL_PATH/$DEPLOY_PACKAGE" $SERVER_USER@$SERVER_IP:$SERVER_PATH/
    ) &
    local upload_pid=$!
    show_spinner $upload_pid "上传代码包"
    wait $upload_pid
    
    # 停止资源监控
    kill $monitor_pid 2>/dev/null || true
    
    # 在服务器解压
    log_info "在服务器解压部署包..."
    (
        ssh $SERVER_USER@$SERVER_IP "cd $SERVER_PATH && unzip -o $DEPLOY_PACKAGE && rm $DEPLOY_PACKAGE"
    ) &
    local extract_pid=$!
    show_spinner $extract_pid "解压部署包"
    wait $extract_pid
    
    log_success "代码上传完成"
    return 0
}

# 创建备份
create_backup() {
    log_info "创建当前版本备份..."
    
    local backup_name="backup-$(date +%Y%m%d-%H%M%S).tar.gz"
    
    ssh $SERVER_USER@$SERVER_IP "
        cd $SERVER_PATH
        if [ -d \"backups\" ]; then
            # 创建备份
            tar -czf \"backups/$backup_name\" --exclude=\"backups\" . 2>/dev/null || true
            
            # 清理旧备份（保留最新的MAX_BACKUPS个）
            cd backups
            ls -t *.tar.gz 2>/dev/null | tail -n +$((MAX_BACKUPS + 1)) | xargs -r rm
            
            echo \"备份创建完成: $backup_name\"
        else
            echo \"备份目录不存在，跳过备份\"
        fi
    " >> "$LOG_FILE" 2>&1
    
    log_success "备份创建完成: $backup_name"
    return 0
}

# 在服务器部署应用
deploy_app() {
    log_info "在服务器部署应用..."
    
    # 启动资源监控
    monitor_resources $$ 60 &
    local monitor_pid=$!
    
    # 创建备份
    create_backup
    
    # 停止现有容器
    log_info "停止现有容器..."
    (
        ssh $SERVER_USER@$SERVER_IP "cd $SERVER_PATH && docker-compose down 2>/dev/null || true"
    ) &
    local stop_pid=$!
    show_spinner $stop_pid "停止容器"
    wait $stop_pid
    
    # 清理旧镜像
    log_info "清理旧镜像..."
    ssh $SERVER_USER@$SERVER_IP "cd $SERVER_PATH && docker image prune -f" >> "$LOG_FILE" 2>&1
    
    # 构建并启动新容器
    log_info "构建并启动新容器..."
    (
        ssh $SERVER_USER@$SERVER_IP "cd $SERVER_PATH && docker-compose up -d --build"
    ) &
    local build_pid=$!
    show_spinner $build_pid "构建并启动容器"
    wait $build_pid
    
    # 停止资源监控
    kill $monitor_pid 2>/dev/null || true
    
    # 记录版本信息
    record_version
    
    log_success "应用部署完成"
    return 0
}

# 记录版本信息
record_version() {
    local version_info="{
        \"deployment_id\": \"$DEPLOYMENT_ID\",
        \"timestamp\": \"$(date -Iseconds)\",
        \"package\": \"$DEPLOY_PACKAGE\",
        \"user\": \"$(whoami)\",
        \"host\": \"$(hostname)\",
        \"os\": \"$OS_TYPE\"
    }"
    
    echo "$version_info" > "$VERSION_FILE"
    ssh $SERVER_USER@$SERVER_IP "echo '$version_info' > $SERVER_PATH/.deploy_version"
    
    log_debug "版本信息已记录"
}

# 错误检测与恢复
detect_and_recover() {
    local error_type=$1
    local retry_count=${2:-3}
    
    log_warning "检测到错误类型: $error_type，尝试恢复..."
    
    case $error_type in
        "connection_error")
            log_info "尝试重新连接服务器..."
            for i in $(seq 1 $retry_count); do
                if ssh -o BatchMode=yes -o ConnectTimeout=5 $SERVER_USER@$SERVER_IP exit 2>/dev/null; then
                    log_success "服务器连接已恢复"
                    return 0
                fi
                log_info "重试连接 ($i/$retry_count)..."
                sleep 5
            done
            log_error "无法恢复服务器连接"
            return 1
            ;;
        "container_error")
            log_info "尝试重启容器..."
            ssh $SERVER_USER@$SERVER_IP "cd $SERVER_PATH && docker-compose restart"
            sleep 10
            return 0
            ;;
        "build_error")
            log_info "尝试清理并重新构建..."
            ssh $SERVER_USER@$SERVER_IP "cd $SERVER_PATH && docker-compose down && docker system prune -f && docker-compose up -d --build"
            return 0
            ;;
        *)
            log_error "未知错误类型，无法自动恢复"
            return 1
            ;;
    esac
}

# 检查应用状态
check_status() {
    log_info "检查应用状态..."
    
    # 获取容器状态
    local container_status=$(ssh $SERVER_USER@$SERVER_IP "cd $SERVER_PATH && docker-compose ps -q" | xargs -I {} ssh $SERVER_USER@$SERVER_IP "docker inspect {} --format '{{.State.Status}}'" 2>/dev/null)
    
    if [ -z "$container_status" ]; then
        log_error "未找到运行中的容器"
        detect_and_recover "container_error"
        return 1
    fi
    
    log_info "容器状态: $container_status"
    
    # 检查端口状态
    local port_status=$(ssh $SERVER_USER@$SERVER_IP "cd $SERVER_PATH && docker-compose port flask-app 5000" 2>/dev/null | cut -d':' -f2)
    
    if [ -n "$port_status" ]; then
        log_info "应用端口: $port_status"
        
        # 检查HTTP响应
        local http_status=$(ssh $SERVER_USER@$SERVER_IP "curl -s -o /dev/null -w '%{http_code}' http://localhost:$port_status" 2>/dev/null || echo "failed")
        
        if [ "$http_status" = "200" ]; then
            log_success "应用运行正常 (HTTP状态码: $http_status)"
            return 0
        else
            log_warning "应用响应异常 (HTTP状态码: $http_status)"
            detect_and_recover "container_error"
            return 1
        fi
    else
        log_error "无法获取应用端口"
        return 1
    fi
}

# 回滚到上一个版本
rollback() {
    log_info "开始回滚到上一个版本..."
    
    # 获取最新备份
    local latest_backup=$(ssh $SERVER_USER@$SERVER_IP "ls -t $BACKUP_DIR/*.tar.gz 2>/dev/null | head -n 1")
    
    if [ -z "$latest_backup" ]; then
        log_error "未找到可用的备份文件"
        return 1
    fi
    
    local backup_name=$(basename "$latest_backup")
    log_info "使用备份文件: $backup_name"
    
    # 停止当前容器
    ssh $SERVER_USER@$SERVER_IP "cd $SERVER_PATH && docker-compose down"
    
    # 恢复备份
    ssh $SERVER_USER@$SERVER_IP "
        cd $SERVER_PATH
        # 备份当前版本（以防回滚失败）
        if [ -d \"current_broken\" ]; then
            rm -rf current_broken
        fi
        mkdir current_broken
        find . -maxdepth 1 -not -name \".\" -not -name \"..\" -not -name \"backups\" -not -name \"current_broken\" -exec mv {} current_broken/ \;
        
        # 解压备份
        tar -xzf \"$BACKUP_DIR/$backup_name\"
        
        # 启动服务
        docker-compose up -d
    "
    
    # 检查回滚后的状态
    sleep 10
    if check_status; then
        log_success "回滚成功"
        return 0
    else
        log_error "回滚失败，尝试恢复当前版本"
        # 恢复当前版本
        ssh $SERVER_USER@$SERVER_IP "
            cd $SERVER_PATH
            docker-compose down
            rm -rf ./*
            mv current_broken/* ./
            rmdir current_broken
            docker-compose up -d
        "
        return 1
    fi
}

# 查看部署历史
show_history() {
    log_info "查看部署历史..."
    
    echo "本地部署历史:"
    if [ -f "$VERSION_FILE" ]; then
        cat "$VERSION_FILE" | jq '.' 2>/dev/null || cat "$VERSION_FILE"
    else
        echo "无本地部署记录"
    fi
    
    echo ""
    echo "服务器部署历史:"
    ssh $SERVER_USER@$SERVER_IP "
        if [ -f '$SERVER_PATH/.deploy_version' ]; then
            cat '$SERVER_PATH/.deploy_version' | jq '.' 2>/dev/null || cat '$SERVER_PATH/.deploy_version'
        else
            echo '无服务器部署记录'
        fi
    "
    
    echo ""
    echo "可用备份:"
    ssh $SERVER_USER@$SERVER_IP "
        if [ -d '$BACKUP_DIR' ]; then
            ls -la '$BACKUP_DIR'/*.tar.gz 2>/dev/null || echo '无备份文件'
        else
            echo '备份目录不存在'
        fi
    "
}

# 清理资源
cleanup() {
    log_info "清理资源..."
    
    # 清理临时目录
    if [ -n "$TEMP_DIR" ] && [ -d "$TEMP_DIR" ]; then
        rm -rf "$TEMP_DIR"
        log_debug "已清理临时目录: $TEMP_DIR"
    fi
    
    # 清理本地部署包
    if [ -f "$LOCAL_PATH/$DEPLOY_PACKAGE" ]; then
        rm "$LOCAL_PATH/$DEPLOY_PACKAGE"
        log_debug "已清理本地部署包: $DEPLOY_PACKAGE"
    fi
    
    # 清理服务器旧镜像
    ssh $SERVER_USER@$SERVER_IP "docker image prune -f" >> "$LOG_FILE" 2>&1
    
    log_success "资源清理完成"
}

# 显示帮助信息
show_help() {
    echo "Google Maps Spider 优化一键部署脚本"
    echo ""
    echo "用法: $0 [选项]"
    echo ""
    echo "主要选项:"
    echo "  deploy              完整部署 (默认: 打包 -> 上传 -> 部署)"
    echo "  upload              仅上传代码包"
    echo "  update              仅更新服务器代码并重启容器"
    echo "  status              检查服务器应用状态"
    echo "  logs                查看应用日志"
    echo "  rollback            回滚到上一个版本"
    echo "  history             查看部署历史"
    echo ""
    echo "高级选项:"
    echo "  monitor             启动资源监控"
    echo "  cleanup             清理本地和服务器资源"
    echo "  test                测试部署环境"
    echo ""
    echo "其他选项:"
    echo "  help                显示此帮助信息"
    echo ""
    echo "示例:"
    echo "  $0                  # 执行完整部署"
    echo "  $0 deploy           # 执行完整部署"
    echo "  $0 upload           # 仅上传代码"
    echo "  $0 update           # 仅更新并重启"
    echo "  $0 status           # 检查状态"
    echo "  $0 rollback         # 回滚到上一版本"
    echo ""
    echo "环境变量:"
    echo "  SERVER_IP           服务器IP地址 (当前: $SERVER_IP)"
    echo "  SERVER_USER         服务器用户名 (当前: $SERVER_USER)"
    echo "  SERVER_PATH         服务器部署路径 (当前: $SERVER_PATH)"
    echo "  MAX_BACKUPS         最大备份数量 (当前: $MAX_BACKUPS)"
}

# 测试部署环境
test_env() {
    log_info "测试部署环境..."
    
    # 检查本地环境
    if ! check_local_env; then
        log_error "本地环境测试失败"
        return 1
    fi
    
    # 测试服务器Docker环境
    log_info "测试服务器Docker环境..."
    local docker_version=$(ssh $SERVER_USER@$SERVER_IP "docker --version" 2>/dev/null)
    local compose_version=$(ssh $SERVER_USER@$SERVER_IP "docker-compose --version" 2>/dev/null)
    
    if [ -n "$docker_version" ]; then
        log_success "Docker版本: $docker_version"
    else
        log_error "无法获取Docker版本"
        return 1
    fi
    
    if [ -n "$compose_version" ]; then
        log_success "Docker Compose版本: $compose_version"
    else
        log_error "无法获取Docker Compose版本"
        return 1
    fi
    
    # 测试磁盘空间
    local disk_space=$(ssh $SERVER_USER@$SERVER_IP "df -h $SERVER_PATH | tail -1 | awk '{print \$4}'")
    log_info "服务器可用磁盘空间: $disk_space"
    
    # 测试内存
    local mem_info=$(ssh $SERVER_USER@$SERVER_IP "free -h | grep Mem")
    log_info "服务器内存状态: $mem_info"
    
    log_success "部署环境测试通过"
    return 0
}

# 主函数
main() {
    local command=${1:-deploy}
    
    # 初始化日志
    init_logging
    
    # 记录开始时间
    local start_time=$(date +%s)
    
    # 捕获退出信号
    trap 'log_error "部署过程中断"; cleanup; exit 1' INT TERM
    
    case $command in
        "deploy")
            log_info "开始完整部署流程..."
            if check_local_env && package_code && upload_code && deploy_app; then
                sleep 5  # 等待容器启动
                if check_status; then
                    local end_time=$(date +%s)
                    local duration=$((end_time - start_time))
                    log_success "完整部署完成! 耗时: ${duration}秒"
                else
                    log_error "部署后状态检查失败"
                    exit 1
                fi
            else
                log_error "部署失败"
                exit 1
            fi
            ;;
        "upload")
            log_info "开始上传代码..."
            if check_local_env && package_code && upload_code; then
                local end_time=$(date +%s)
                local duration=$((end_time - start_time))
                log_success "代码上传完成! 耗时: ${duration}秒"
            else
                log_error "代码上传失败"
                exit 1
            fi
            ;;
        "update")
            log_info "开始更新代码..."
            if check_local_env && package_code && upload_code; then
                # 重启容器
                log_info "重启容器..."
                ssh $SERVER_USER@$SERVER_IP "cd $SERVER_PATH && docker-compose restart"
                sleep 3  # 等待容器重启
                if check_status; then
                    local end_time=$(date +%s)
                    local duration=$((end_time - start_time))
                    log_success "代码更新完成! 耗时: ${duration}秒"
                else
                    log_error "更新后状态检查失败"
                    exit 1
                fi
            else
                log_error "代码更新失败"
                exit 1
            fi
            ;;
        "status")
            check_status
            ;;
        "logs")
            log_info "查看应用日志..."
            ssh $SERVER_USER@$SERVER_IP "cd $SERVER_PATH && docker-compose logs -f --tail=50"
            ;;
        "rollback")
            rollback
            ;;
        "history")
            show_history
            ;;
        "monitor")
            log_info "启动资源监控 (60秒)..."
            monitor_resources $$ 60
            ;;
        "cleanup")
            cleanup
            ;;
        "test")
            test_env
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
    
    # 清理资源
    cleanup
}

# 执行主函数
main "$@"