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
    log_info "创建部署包 (排除大文件和缓存)..."
    
    # 使用 git archive 创建部署包（自动排除 .gitignore 中的文件）
    if git archive --format=zip --output="$DEPLOY_PACKAGE" HEAD; then
        # 校验文件完整性
        if [ -f "$DEPLOY_PACKAGE" ]; then
            file_size=$(ls -lh "$DEPLOY_PACKAGE" | awk '{print $5}')
            file_count=$(unzip -l "$DEPLOY_PACKAGE" 2>/dev/null | tail -1 | awk '{print $2}')
            log_success "部署包创建成功: $DEPLOY_PACKAGE"
            log_info "  - 大小: $file_size"
            log_info "  - 文件数: $file_count"
            return 0
        else
            log_error "部署包创建失败"
            return 1
        fi
    else
        log_error "git archive 命令执行失败"
        
        # 备用方案：使用 zip 命令
        log_info "尝试使用 zip 命令创建部署包..."
        zip -r "$DEPLOY_PACKAGE" . \
            -x "*.git*" \
            -x "*venv*" \
            -x "*.venv*" \
            -x "*__pycache__*" \
            -x "*.pyc" \
            -x "*node_modules*" \
            -x "*.db" \
            -x "*.db-*" \
            -x "*htmlcov*" \
            -x "*.coverage*" \
            -x "*logs/*" \
            -x "*output/*" \
            -x "*progress/*" \
            -x "*.hypothesis*" \
            -x "*.pytest_cache*" \
            -x "*.idea*" \
            -x "*.vscode*" \
            -x "*.trae*" \
            -x "*.DS_Store" \
            > /dev/null 2>&1
        
        if [ -f "$DEPLOY_PACKAGE" ]; then
            file_size=$(ls -lh "$DEPLOY_PACKAGE" | awk '{print $5}')
            log_success "部署包创建成功 (zip): $DEPLOY_PACKAGE (大小: $file_size)"
            return 0
        else
            log_error "部署包创建失败"
            return 1
        fi
    fi
}

# 步骤2: 安全传输部署包
transfer_deployment_package() {
    log_info "步骤2: 安全传输部署包"
    
    # 获取本地文件大小
    local_size=$(ls -l "$DEPLOY_PACKAGE" | awk '{print $5}')
    local_size_human=$(ls -lh "$DEPLOY_PACKAGE" | awk '{print $5}')
    log_info "本地文件大小: $local_size 字节 ($local_size_human)"
    
    # 计算本地文件MD5校验和
    if command -v md5sum &> /dev/null; then
        local_md5=$(md5sum "$DEPLOY_PACKAGE" | awk '{print $1}')
    else
        local_md5=$(md5 -q "$DEPLOY_PACKAGE")
    fi
    log_info "本地文件MD5: $local_md5"
    
    # 传输部署包 - 增加超时和压缩选项
    log_info "传输部署包到服务器 (使用压缩传输)..."
    
    # 最多重试3次
    max_retries=3
    retry_count=0
    
    while [ $retry_count -lt $max_retries ]; do
        retry_count=$((retry_count + 1))
        log_info "传输尝试 $retry_count/$max_retries..."
        
        # 使用 -C 启用压缩，-o 设置超时选项
        if scp -C -o ConnectTimeout=30 -o ServerAliveInterval=15 -o ServerAliveCountMax=3 \
            "$DEPLOY_PACKAGE" "$SERVER_USER@$SERVER_IP:$SERVER_PATH/"; then
            
            log_success "部署包传输完成"
            
            # 验证服务器上的文件
            log_info "验证服务器上的文件..."
            remote_info=$(ssh -o ConnectTimeout=10 "$SERVER_USER@$SERVER_IP" "ls -l $SERVER_PATH/$DEPLOY_PACKAGE" 2>/dev/null)
            
            if [ $? -eq 0 ]; then
                # 获取远程文件大小
                remote_size=$(echo "$remote_info" | awk '{print $5}')
                
                # 比较文件大小
                if [ "$local_size" = "$remote_size" ]; then
                    log_success "文件大小校验通过: $remote_size 字节"
                    
                    # 验证MD5校验和
                    log_info "验证MD5校验和..."
                    remote_md5=$(ssh -o ConnectTimeout=10 "$SERVER_USER@$SERVER_IP" "md5sum $SERVER_PATH/$DEPLOY_PACKAGE 2>/dev/null | awk '{print \$1}'" 2>/dev/null)
                    
                    if [ "$local_md5" = "$remote_md5" ]; then
                        log_success "MD5校验通过: $remote_md5"
                        return 0
                    else
                        log_warning "MD5校验失败 - 本地: $local_md5, 远程: $remote_md5"
                        # 删除损坏的文件
                        ssh -o ConnectTimeout=10 "$SERVER_USER@$SERVER_IP" "rm -f $SERVER_PATH/$DEPLOY_PACKAGE" 2>/dev/null
                    fi
                else
                    log_warning "文件大小不匹配 - 本地: $local_size, 远程: $remote_size"
                    # 删除不完整的文件
                    ssh -o ConnectTimeout=10 "$SERVER_USER@$SERVER_IP" "rm -f $SERVER_PATH/$DEPLOY_PACKAGE" 2>/dev/null
                fi
            else
                log_error "无法验证服务器上的文件"
            fi
        else
            log_warning "传输失败，准备重试..."
        fi
        
        if [ $retry_count -lt $max_retries ]; then
            log_info "等待5秒后重试..."
            sleep 5
        fi
    done
    
    log_error "部署包传输失败，已重试 $max_retries 次"
    return 1
}

# 步骤3: 服务器端部署流程
server_deployment() {
    log_info "步骤3: 服务器端部署流程"
    
    # 先备份现有数据目录
    log_info "备份现有数据目录..."
    ssh -o ConnectTimeout=10 "$SERVER_USER@$SERVER_IP" "
        if [ -d $SERVER_PATH/$DEPLOY_DIR/data ]; then
            cp -r $SERVER_PATH/$DEPLOY_DIR/data $SERVER_PATH/data_backup_\$(date +%Y%m%d_%H%M%S)
            echo '数据目录已备份'
        fi
    "
    
    # 解压部署包
    log_info "解压部署包..."
    ssh_result=$(ssh -o ConnectTimeout=30 "$SERVER_USER@$SERVER_IP" "cd $SERVER_PATH && rm -rf $DEPLOY_DIR.bak && mv $DEPLOY_DIR $DEPLOY_DIR.bak 2>/dev/null; mkdir -p $DEPLOY_DIR && unzip -o $DEPLOY_PACKAGE -d $DEPLOY_DIR" 2>&1)
    
    if [ $? -eq 0 ]; then
        log_success "部署包解压成功"
    else
        log_error "部署包解压失败: $ssh_result"
        return 1
    fi
    
    # 创建数据目录（确保 volume 映射正常）
    log_info "创建数据目录..."
    ssh -o ConnectTimeout=10 "$SERVER_USER@$SERVER_IP" "mkdir -p $SERVER_PATH/$DEPLOY_DIR/data $SERVER_PATH/$DEPLOY_DIR/output $SERVER_PATH/$DEPLOY_DIR/logs $SERVER_PATH/$DEPLOY_DIR/progress"
    
    # 恢复数据库文件（从备份目录恢复）
    log_info "恢复数据文件..."
    ssh -o ConnectTimeout=10 "$SERVER_USER@$SERVER_IP" "
        # 优先从旧部署目录恢复
        if [ -f $SERVER_PATH/$DEPLOY_DIR.bak/data/business.db ]; then
            # 先执行 WAL checkpoint，确保所有数据写入主数据库文件
            echo '执行 WAL checkpoint 确保数据完整性...'
            sqlite3 $SERVER_PATH/$DEPLOY_DIR.bak/data/business.db 'PRAGMA wal_checkpoint(TRUNCATE);' 2>/dev/null || true
            
            # 复制数据库文件（包括 WAL 和 SHM 文件以防万一）
            cp $SERVER_PATH/$DEPLOY_DIR.bak/data/business.db $SERVER_PATH/$DEPLOY_DIR/data/
            # 如果 checkpoint 成功，WAL 文件应该已经清空，但为了安全还是复制
            if [ -f $SERVER_PATH/$DEPLOY_DIR.bak/data/business.db-wal ]; then
                cp $SERVER_PATH/$DEPLOY_DIR.bak/data/business.db-wal $SERVER_PATH/$DEPLOY_DIR/data/ 2>/dev/null || true
            fi
            if [ -f $SERVER_PATH/$DEPLOY_DIR.bak/data/business.db-shm ]; then
                cp $SERVER_PATH/$DEPLOY_DIR.bak/data/business.db-shm $SERVER_PATH/$DEPLOY_DIR/data/ 2>/dev/null || true
            fi
            echo '已从备份目录恢复数据库文件（含 WAL checkpoint）'
        # 否则从最新的备份恢复
        elif ls $SERVER_PATH/data_backup_*/business.db 1>/dev/null 2>&1; then
            latest_backup=\$(ls -td $SERVER_PATH/data_backup_*/ | head -1)
            if [ -f \"\${latest_backup}business.db\" ]; then
                # 对备份文件也执行 checkpoint
                sqlite3 \"\${latest_backup}business.db\" 'PRAGMA wal_checkpoint(TRUNCATE);' 2>/dev/null || true
                cp \"\${latest_backup}business.db\" $SERVER_PATH/$DEPLOY_DIR/data/
                echo \"已从 \$latest_backup 恢复数据库文件\"
            fi
        else
            echo '没有找到数据库备份，将创建新数据库'
        fi
    "
    
    # 停止旧容器
    log_info "停止旧容器..."
    ssh -o ConnectTimeout=30 "$SERVER_USER@$SERVER_IP" "cd $SERVER_PATH/$DEPLOY_DIR && docker-compose down 2>/dev/null" || true
    
    # 启动新容器
    log_info "构建并启动新容器 (可能需要几分钟)..."
    build_result=$(ssh -o ConnectTimeout=300 "$SERVER_USER@$SERVER_IP" "cd $SERVER_PATH/$DEPLOY_DIR && docker-compose up -d --build" 2>&1)
    
    if [ $? -eq 0 ]; then
        log_success "容器启动命令执行成功"
    else
        log_error "容器启动失败: $build_result"
        return 1
    fi
    
    # 等待容器启动
    log_info "等待容器启动..."
    sleep 10
    
    # 检查容器状态
    log_info "检查容器状态..."
    container_status=$(ssh -o ConnectTimeout=10 "$SERVER_USER@$SERVER_IP" "cd $SERVER_PATH/$DEPLOY_DIR && docker-compose ps" 2>/dev/null)
    
    if echo "$container_status" | grep -q "Up"; then
        log_success "容器状态检查通过"
        echo "$container_status"
        
        # 初始化AI配置
        log_info "初始化AI配置..."
        ssh -o ConnectTimeout=30 "$SERVER_USER@$SERVER_IP" "cd $SERVER_PATH/$DEPLOY_DIR && docker-compose exec -T web python init_ai_config.py 2>/dev/null" || log_warning "AI配置初始化跳过"
        
        return 0
    else
        log_error "容器状态检查失败"
        echo "$container_status"
        
        # 显示容器日志帮助调试
        log_info "容器日志:"
        ssh -o ConnectTimeout=10 "$SERVER_USER@$SERVER_IP" "cd $SERVER_PATH/$DEPLOY_DIR && docker-compose logs --tail=50" 2>/dev/null || true
        
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