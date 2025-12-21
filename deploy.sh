#!/bin/bash

# Google Maps Spider 一键部署脚本
# 基于成功的部署经验编写
# 适用于服务器 155.138.226.211

set -e  # 遇到错误时退出

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

# 配置参数
SERVER_IP="155.138.226.211"
SERVER_USER="root"
SERVER_PATH="/opt"
DEPLOY_PACKAGE="google-maps-spider.zip"
DEPLOY_DIR="google-maps-spider"
APP_PORT="8088"

# 显示开始信息
echo "========================================="
echo "    Google Maps Spider 一键部署脚本"
echo "========================================="
echo "目标服务器: $SERVER_IP"
echo "部署目录: $SERVER_PATH/$DEPLOY_DIR"
echo "应用端口: $APP_PORT"
echo "========================================="

# 步骤1: 构建部署包
build_deployment_package() {
    log_info "步骤1: 构建部署包"
    
    # 清理旧的部署包
    if [ -f "$DEPLOY_PACKAGE" ]; then
        rm -f "$DEPLOY_PACKAGE"
        log_info "已清理旧的部署包: $DEPLOY_PACKAGE"
    fi
    
    # 创建部署包，排除不必要的文件
    log_info "创建部署包..."
    zip -r "$DEPLOY_PACKAGE" app.py requirements.txt docker-compose.yml Dockerfile docker-entrypoint.sh templates static config models utils validators *.py init_ai_config.py diagnose_ai_config.py server_diagnose.py -x "*.git*" "*node_modules*" "*.env*" "*logs*" "*__pycache__*" "*.pyc" ".DS_Store" "*venv*" > /dev/null 2>&1
    
    # 校验文件完整性
    if [ -f "$DEPLOY_PACKAGE" ]; then
        file_size=$(ls -lh "$DEPLOY_PACKAGE" | awk '{print $5}')
        log_success "部署包创建成功: $DEPLOY_PACKAGE (大小: $file_size)"
        return 0
    else
        log_error "部署包创建失败"
        return 1
    fi
}

# 步骤2: 安全传输部署包
transfer_deployment_package() {
    log_info "步骤2: 安全传输部署包"
    
    # 获取本地文件大小
    local_size=$(ls -l "$DEPLOY_PACKAGE" | awk '{print $5}')
    log_info "本地文件大小: $local_size 字节"
    
    # 传输部署包
    log_info "传输部署包到服务器..."
    if scp -P 22 "$DEPLOY_PACKAGE" "$SERVER_USER@$SERVER_IP:$SERVER_PATH/" > /dev/null 2>&1; then
        log_success "部署包传输成功"
        
        # 验证服务器上的文件
        log_info "验证服务器上的文件..."
        remote_info=$(ssh -p 22 -o ConnectTimeout=5 "$SERVER_USER@$SERVER_IP" "ls -l $SERVER_PATH/$DEPLOY_PACKAGE" 2>/dev/null)
        
        if [ $? -eq 0 ]; then
            log_success "服务器文件验证成功"
            
            # 获取远程文件大小
            remote_size=$(echo "$remote_info" | awk '{print $5}')
            
            # 比较文件大小
            if [ "$local_size" = "$remote_size" ]; then
                log_success "文件大小校验通过: $remote_size 字节"
                return 0
            else
                log_warning "文件大小不匹配 - 本地: $local_size, 远程: $remote_size"
                return 1
            fi
        else
            log_error "无法验证服务器上的文件"
            return 1
        fi
    else
        log_error "部署包传输失败"
        return 1
    fi
}

# 步骤3: 服务器端部署流程
server_deployment() {
    log_info "步骤3: 服务器端部署流程"
    
    # 解压部署包
    log_info "解压部署包..."
    if ssh -p 22 -o ConnectTimeout=5 "$SERVER_USER@$SERVER_IP" "cd $SERVER_PATH && unzip -o $DEPLOY_PACKAGE -d $DEPLOY_DIR" > /dev/null 2>&1; then
        log_success "部署包解压成功"
    else
        log_error "部署包解压失败"
        return 1
    fi
    
    # 停止旧容器
    log_info "停止旧容器..."
    ssh -p 22 -o ConnectTimeout=5 "$SERVER_USER@$SERVER_IP" "cd $SERVER_PATH/$DEPLOY_DIR && docker-compose down" > /dev/null 2>&1 || true
    
    # 启动新容器
    log_info "构建并启动新容器..."
    if ssh -p 22 -o ConnectTimeout=5 "$SERVER_USER@$SERVER_IP" "cd $SERVER_PATH/$DEPLOY_DIR && docker-compose up -d --build" > /dev/null 2>&1; then
        log_success "容器启动成功"
    else
        log_error "容器启动失败"
        return 1
    fi
    
    # 检查容器状态
    log_info "检查容器状态..."
    container_status=$(ssh -p 22 -o ConnectTimeout=5 "$SERVER_USER@$SERVER_IP" "cd $SERVER_PATH/$DEPLOY_DIR && docker-compose ps" 2>/dev/null)
    
    if echo "$container_status" | grep -q "Up"; then
        log_success "容器状态检查通过"
        echo "$container_status"
        
        # 初始化AI配置
        log_info "初始化AI配置..."
        if ssh -p 22 -o ConnectTimeout=5 "$SERVER_USER@$SERVER_IP" "cd $SERVER_PATH/$DEPLOY_DIR && python init_ai_config.py" > /dev/null 2>&1; then
            log_success "AI配置初始化成功"
        else
            log_warning "AI配置初始化失败，可能需要手动配置"
        fi
        
        return 0
    else
        log_error "容器状态检查失败"
        echo "$container_status"
        return 1
    fi
}

# 步骤4: 部署验证
verify_deployment() {
    log_info "步骤4: 部署验证"
    
    # 等待应用启动
    log_info "等待应用启动..."
    sleep 15
    
    # 检查应用是否响应
    log_info "检查应用响应..."
    if curl -I --connect-timeout 10 "http://$SERVER_IP:$APP_PORT" 2>/dev/null | grep -q "HTTP"; then
        log_success "应用响应正常"
        
        # 检查登录页面
        if curl -I --connect-timeout 10 "http://$SERVER_IP:$APP_PORT/login" 2>/dev/null | grep -q "200 OK"; then
            log_success "登录页面响应正常"
            return 0
        else
            log_warning "登录页面响应异常"
            return 1
        fi
    else
        log_error "应用无响应"
        return 1
    fi
}

# 主函数
main() {
    # 执行部署步骤
    if build_deployment_package; then
        if transfer_deployment_package; then
            if server_deployment; then
                if verify_deployment; then
                    log_success "部署完成！应用可通过 http://$SERVER_IP:$APP_PORT 访问"
                    
                    # 清理本地部署包
                    rm -f "$DEPLOY_PACKAGE"
                    log_info "已清理本地部署包"
                    
                    echo "========================================="
                    echo "           部署成功完成"
                    echo "========================================="
                    echo "应用地址: http://$SERVER_IP:$APP_PORT"
                    echo "登录页面: http://$SERVER_IP:$APP_PORT/login"
                    echo "========================================="
                    
                    exit 0
                else
                    log_error "部署验证失败"
                fi
            else
                log_error "服务器端部署失败"
            fi
        else
            log_error "部署包传输失败"
        fi
    else
        log_error "部署包构建失败"
    fi
    
    # 清理本地部署包
    rm -f "$DEPLOY_PACKAGE" 2>/dev/null || true
    exit 1
}

# 执行主函数
main "$@"