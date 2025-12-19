#!/bin/bash

# 增强的部署状态检查脚本
# 用于检查Docker容器和应用的详细运行状态，支持健康检查和性能监控

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 配置变量
SERVER_IP="155.138.226.211"
SERVER_USER="root"
SERVER_PATH="/opt/google-maps-spider"
LOG_DIR="$SERVER_PATH/logs"
HEALTH_CHECK_ENDPOINT="/health"
PERFORMANCE_CHECK_INTERVAL=30
ALERT_THRESHOLD_CPU=80
ALERT_THRESHOLD_MEMORY=85
ALERT_THRESHOLD_DISK=90

# 日志函数
log_info() {
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${BLUE}[INFO $timestamp]${NC} $1"
}

log_success() {
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${GREEN}[SUCCESS $timestamp]${NC} $1"
}

log_warning() {
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${YELLOW}[WARNING $timestamp]${NC} $1"
}

log_error() {
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${RED}[ERROR $timestamp]${NC} $1"
}

log_debug() {
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${PURPLE}[DEBUG $timestamp]${NC} $1"
}

# 显示帮助信息
show_help() {
    echo "增强的部署状态检查脚本"
    echo ""
    echo "用法: $0 [选项] [容器名称]"
    echo ""
    echo "主要选项:"
    echo "  status [容器名]     检查容器状态"
    echo "  health [容器名]      检查应用健康状态"
    echo "  performance [容器名]  检查应用性能指标"
    echo "  logs [容器名]        查看容器日志"
    echo "  monitor [容器名]     持续监控应用状态"
    echo "  diagnose [容器名]     诊断应用问题"
    echo ""
    echo "系统选项:"
    echo "  system              检查服务器系统状态"
    echo "  resources           检查服务器资源使用情况"
    echo "  network             检查网络连接状态"
    echo ""
    echo "其他选项:"
    echo "  help                显示此帮助信息"
    echo ""
    echo "示例:"
    echo "  $0 status           # 检查默认容器状态"
    echo "  $0 health myapp     # 检查指定容器健康状态"
    echo "  $0 monitor          # 持续监控应用"
    echo "  $0 system           # 检查服务器系统状态"
}

# 获取容器名称
get_container_name() {
    local container_name=${1:-$(ssh $SERVER_USER@$SERVER_IP "cd $SERVER_PATH && docker-compose ps -q" | xargs -I {} ssh $SERVER_USER@$SERVER_IP "docker inspect {} --format '{{.Name}}' | sed 's/\///'" 2>/dev/null)}
    
    if [ -z "$container_name" ]; then
        log_error "未找到运行中的容器"
        return 1
    fi
    
    echo "$container_name"
}

# 检查容器状态
check_container_status() {
    local container_name=$(get_container_name "$1")
    
    if [ $? -ne 0 ]; then
        return 1
    fi
    
    log_info "检查容器状态: $container_name"
    
    # 获取容器基本信息
    local status=$(ssh $SERVER_USER@$SERVER_IP "docker inspect '$container_name' --format '{{.State.Status}}'")
    local started_at=$(ssh $SERVER_USER@$SERVER_IP "docker inspect '$container_name' --format '{{.State.StartedAt}}'")
    local image=$(ssh $SERVER_USER@$SERVER_IP "docker inspect '$container_name' --format '{{.Config.Image}}'")
    
    echo -e "${CYAN}基本信息:${NC}"
    echo "  状态: $status"
    echo "  启动时间: $started_at"
    echo "  镜像: $image"
    
    # 获取健康状态（如果有）
    local health=$(ssh $SERVER_USER@$SERVER_IP "docker inspect '$container_name' --format '{{.State.Health.Status}}' 2>/dev/null || echo 'no_healthcheck'")
    if [ "$health" != "no_healthcheck" ]; then
        echo "  健康状态: $health"
    fi
    
    # 获取容器网络信息
    local container_ip=$(ssh $SERVER_USER@$SERVER_IP "docker inspect '$container_name' --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}'")
    local ports=$(ssh $SERVER_USER@$SERVER_IP "docker port '$container_name' 2>/dev/null || echo '无端口映射'")
    
    echo -e "${CYAN}网络信息:${NC}"
    echo "  容器IP: $container_ip"
    if [ "$ports" != "无端口映射" ]; then
        echo "  端口映射: $ports"
        
        # 检查端口状态
        local host_port=$(echo "$ports" | grep -o '0.0.0.0:[0-9]*' | cut -d':' -f2)
        if [ -n "$host_port" ]; then
            local port_status=$(ssh $SERVER_USER@$SERVER_IP "nc -z localhost $host_port && echo 'open' || echo 'closed'")
            echo "  端口状态: $port_status"
            
            # 检查HTTP响应
            if [ "$port_status" = "open" ]; then
                local http_status=$(ssh $SERVER_USER@$SERVER_IP "curl -s -o /dev/null -w '%{http_code}' http://localhost:$host_port 2>/dev/null || echo 'failed'")
                if [ "$http_status" != "failed" ]; then
                    echo "  HTTP状态码: $http_status"
                    
                    if [ "$http_status" = "200" ]; then
                        log_success "应用运行正常"
                    elif [[ "$http_status" =~ ^3[0-9][0-9]$ ]]; then
                        log_warning "应用可能需要重定向 (HTTP状态码: $http_status)"
                    else
                        log_warning "应用响应异常 (HTTP状态码: $http_status)"
                    fi
                else
                    log_error "无法连接到应用"
                fi
            fi
        fi
    else
        echo "  无端口映射"
    fi
    
    # 获取资源使用情况
    local stats=$(ssh $SERVER_USER@$SERVER_IP "docker stats --no-stream --format 'table {{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}\t{{.BlockIO}}' '$container_name'")
    echo -e "${CYAN}资源使用:${NC}"
    echo "$stats"
    
    return 0
}

# 检查应用健康状态
check_app_health() {
    local container_name=$(get_container_name "$1")
    
    if [ $? -ne 0 ]; then
        return 1
    fi
    
    log_info "检查应用健康状态: $container_name"
    
    # 获取容器状态
    local status=$(ssh $SERVER_USER@$SERVER_IP "docker inspect '$container_name' --format '{{.State.Status}}'")
    if [ "$status" != "running" ]; then
        log_error "容器未运行 (状态: $status)"
        return 1
    fi
    
    # 获取端口
    local ports=$(ssh $SERVER_USER@$SERVER_IP "docker port '$container_name' 2>/dev/null")
    local host_port=$(echo "$ports" | grep -o '0.0.0.0:[0-9]*' | cut -d':' -f2)
    
    if [ -z "$host_port" ]; then
        log_error "无端口映射"
        return 2
    fi
    
    # 检查HTTP响应
    local http_status=$(ssh $SERVER_USER@$SERVER_IP "curl -s -o /dev/null -w '%{http_code}' http://localhost:$host_port 2>/dev/null || echo 'failed'")
    
    if [ "$http_status" = "200" ]; then
        log_success "应用健康状态: 正常"
        
        # 检查响应时间
        local response_time=$(ssh $SERVER_USER@$SERVER_IP "curl -s -o /dev/null -w '%{time_total}' http://localhost:$host_port 2>/dev/null || echo 'failed'")
        if [ "$response_time" != "failed" ]; then
            echo "响应时间: ${response_time}秒"
        fi
        
        return 0
    elif [[ "$http_status" =~ ^3[0-9][0-9]$ ]]; then
        log_warning "应用健康状态: 重定向 (HTTP状态码: $http_status)"
        return 1
    else
        log_error "应用健康状态: 异常 (HTTP状态码: $http_status)"
        return 2
    fi
}

# 检查应用性能指标
check_app_performance() {
    local container_name=$(get_container_name "$1")
    
    if [ $? -ne 0 ]; then
        return 1
    fi
    
    log_info "检查应用性能指标: $container_name"
    
    # 获取容器资源使用情况
    local stats=$(ssh $SERVER_USER@$SERVER_IP "docker stats --no-stream --format '{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.NetIO}}\t{{.BlockIO}}' '$container_name'")
    
    if [ -n "$stats" ]; then
        echo -e "${CYAN}当前资源使用:${NC}"
        echo "$stats"
        
        # 解析资源使用率
        local cpu_usage=$(echo "$stats" | awk '{print $1}' | sed 's/%//')
        local mem_usage=$(echo "$stats" | awk '{print $3}' | sed 's/%//')
        
        # 检查是否超过阈值
        if (( $(echo "$cpu_usage > $ALERT_THRESHOLD_CPU" | bc -l) )); then
            log_warning "CPU使用率过高: ${cpu_usage}% (阈值: ${ALERT_THRESHOLD_CPU}%)"
        fi
        
        if (( $(echo "$mem_usage > $ALERT_THRESHOLD_MEMORY" | bc -l) )); then
            log_warning "内存使用率过高: ${mem_usage}% (阈值: ${ALERT_THRESHOLD_MEMORY}%)"
        fi
    fi
    
    # 获取容器日志中的错误信息
    local error_count=$(ssh $SERVER_USER@$SERVER_IP "docker logs '$container_name' --since=1h 2>&1 | grep -i error | wc -l")
    local warning_count=$(ssh $SERVER_USER@$SERVER_IP "docker logs '$container_name' --since=1h 2>&1 | grep -i warning | wc -l")
    
    echo -e "${CYAN}日志统计 (最近1小时):${NC}"
    echo "  错误数量: $error_count"
    echo "  警告数量: $warning_count"
    
    # 检查最近的错误
    if [ "$error_count" -gt 0 ]; then
        echo -e "${CYAN}最近的错误:${NC}"
        ssh $SERVER_USER@$SERVER_IP "docker logs '$container_name' --since=1h 2>&1 | grep -i error | tail -5"
    fi
    
    return 0
}

# 查看容器日志
show_container_logs() {
    local container_name=$(get_container_name "$1")
    
    if [ $? -ne 0 ]; then
        return 1
    fi
    
    log_info "查看容器日志: $container_name"
    ssh $SERVER_USER@$SERVER_IP "docker logs --tail 100 -f '$container_name'"
}

# 持续监控应用状态
monitor_app() {
    local container_name=$(get_container_name "$1")
    
    if [ $? -ne 0 ]; then
        return 1
    fi
    
    log_info "开始持续监控应用状态: $container_name (按Ctrl+C退出)"
    
    while true; do
        clear
        echo "=========================================="
        echo "应用监控 - $(date '+%Y-%m-%d %H:%M:%S')"
        echo "容器: $container_name"
        echo "=========================================="
        
        # 检查容器状态
        check_container_status "$container_name"
        echo ""
        
        # 检查应用健康状态
        check_app_health "$container_name"
        echo ""
        
        # 检查性能指标
        check_app_performance "$container_name"
        echo ""
        
        # 检查系统资源
        check_system_resources
        
        sleep $PERFORMANCE_CHECK_INTERVAL
    done
}

# 诊断应用问题
diagnose_app() {
    local container_name=$(get_container_name "$1")
    
    if [ $? -ne 0 ]; then
        return 1
    fi
    
    log_info "诊断应用问题: $container_name"
    
    echo -e "${CYAN}=== 基础信息 ===${NC}"
    check_container_status "$container_name"
    echo ""
    
    echo -e "${CYAN}=== 健康检查 ===${NC}"
    check_app_health "$container_name"
    echo ""
    
    echo -e "${CYAN}=== 性能指标 ===${NC}"
    check_app_performance "$container_name"
    echo ""
    
    echo -e "${CYAN}=== 系统资源 ===${NC}"
    check_system_resources
    echo ""
    
    echo -e "${CYAN}=== 最近日志 ===${NC}"
    ssh $SERVER_USER@$SERVER_IP "docker logs '$container_name' --tail 20"
    echo ""
    
    echo -e "${CYAN}=== 容器事件 ===${NC}"
    ssh $SERVER_USER@$SERVER_IP "docker events --since=1h --filter container='$container_name' --format '{{.Status}}: {{.Time}}'"
    echo ""
    
    echo -e "${CYAN}=== 诊断建议 ===${NC}"
    
    # 获取容器状态
    local status=$(ssh $SERVER_USER@$SERVER_IP "docker inspect '$container_name' --format '{{.State.Status}}'")
    
    if [ "$status" != "running" ]; then
        echo "• 容器未运行，尝试重启: docker restart $container_name"
    fi
    
    # 获取资源使用情况
    local stats=$(ssh $SERVER_USER@$SERVER_IP "docker stats --no-stream --format '{{.CPUPerc}}\t{{.MemPerc}}' '$container_name'")
    local cpu_usage=$(echo "$stats" | awk '{print $1}' | sed 's/%//')
    local mem_usage=$(echo "$stats" | awk '{print $2}' | sed 's/%//')
    
    if (( $(echo "$cpu_usage > $ALERT_THRESHOLD_CPU" | bc -l) )); then
        echo "• CPU使用率过高，考虑增加资源或优化应用"
    fi
    
    if (( $(echo "$mem_usage > $ALERT_THRESHOLD_MEMORY" | bc -l) )); then
        echo "• 内存使用率过高，考虑增加内存或检查内存泄漏"
    fi
    
    # 检查错误日志
    local error_count=$(ssh $SERVER_USER@$SERVER_IP "docker logs '$container_name' --since=1h 2>&1 | grep -i error | wc -l")
    if [ "$error_count" -gt 0 ]; then
        echo "• 发现 $error_count 个错误，请检查应用日志"
    fi
    
    return 0
}

# 检查系统状态
check_system_status() {
    log_info "检查服务器系统状态"
    
    # 系统信息
    local uptime=$(ssh $SERVER_USER@$SERVER_IP "uptime")
    local kernel=$(ssh $SERVER_USER@$SERVER_IP "uname -r")
    local os_info=$(ssh $SERVER_USER@$SERVER_IP "cat /etc/os-release | grep PRETTY_NAME | cut -d'=' -f2 | tr -d '\"'")
    
    echo -e "${CYAN}系统信息:${NC}"
    echo "  操作系统: $os_info"
    echo "  内核版本: $kernel"
    echo "  运行时间: $uptime"
    
    # 检查Docker状态
    local docker_version=$(ssh $SERVER_USER@$SERVER_IP "docker --version")
    local docker_running=$(ssh $SERVER_USER@$SERVER_IP "systemctl is-active docker" 2>/dev/null || echo "unknown")
    
    echo -e "${CYAN}Docker状态:${NC}"
    echo "  版本: $docker_version"
    echo "  服务状态: $docker_running"
    
    # 检查磁盘空间
    local disk_usage=$(ssh $SERVER_USER@$SERVER_IP "df -h | grep -E '^/dev/' | awk '{print \$5 \"\t\" \$6}'")
    
    echo -e "${CYAN}磁盘使用:${NC}"
    echo "$disk_usage"
    
    # 检查是否有空间不足的分区
    local disk_full=$(ssh $SERVER_USER@$SERVER_IP "df -h | grep -E '^/dev/' | awk '{gsub(/%/, \"\", \$5); if (\$5 > 90) print \$6}'")
    if [ -n "$disk_full" ]; then
        log_warning "以下分区空间不足: $disk_full"
    fi
    
    return 0
}

# 检查系统资源
check_system_resources() {
    # CPU使用率
    local cpu_usage=$(ssh $SERVER_USER@$SERVER_IP "top -bn1 | grep 'Cpu(s)' | awk '{print \$2}' | cut -d'%' -f1")
    local load_avg=$(ssh $SERVER_USER@$SERVER_IP "uptime | awk -F'load average:' '{print \$2}'")
    
    # 内存使用情况
    local mem_info=$(ssh $SERVER_USER@$SERVER_IP "free -h | grep Mem")
    local mem_usage=$(ssh $SERVER_USER@$SERVER_IP "free -m | awk 'NR==2{printf \"%.1f\", \$3*100/\$2}'")
    
    # 交换分区使用情况
    local swap_info=$(ssh $SERVER_USER@$SERVER_IP "free -h | grep Swap")
    
    echo -e "${CYAN}系统资源:${NC}"
    echo "  CPU使用率: ${cpu_usage}%"
    echo "  负载平均值: $load_avg"
    echo "  内存使用: $mem_info (${mem_usage}%)"
    echo "  交换分区: $swap_info"
    
    # 检查资源是否超过阈值
    if (( $(echo "$cpu_usage > $ALERT_THRESHOLD_CPU" | bc -l) )); then
        log_warning "CPU使用率过高: ${cpu_usage}% (阈值: ${ALERT_THRESHOLD_CPU}%)"
    fi
    
    if (( $(echo "$mem_usage > $ALERT_THRESHOLD_MEMORY" | bc -l) )); then
        log_warning "内存使用率过高: ${mem_usage}% (阈值: ${ALERT_THRESHOLD_MEMORY}%)"
    fi
    
    return 0
}

# 检查网络连接
check_network_status() {
    log_info "检查网络连接状态"
    
    # 检查网络接口
    local interfaces=$(ssh $SERVER_USER@$SERVER_IP "ip addr show | grep -E '^[0-9]+:' | awk '{print \$2}' | tr -d ':'")
    
    echo -e "${CYAN}网络接口:${NC}"
    for interface in $interfaces; do
        local status=$(ssh $SERVER_USER@$SERVER_IP "ip link show $interface | grep -E 'state' | awk '{print \$9}'")
        local ip=$(ssh $SERVER_USER@$SERVER_IP "ip addr show $interface | grep 'inet ' | awk '{print \$2}' | head -1")
        echo "  $interface: $status ($ip)"
    done
    
    # 检查端口监听
    echo -e "${CYAN}端口监听:${NC}"
    ssh $SERVER_USER@$SERVER_IP "netstat -tlnp 2>/dev/null | grep LISTEN | head -10"
    
    # 检查网络连接
    echo -e "${CYAN}活动连接:${NC}"
    local connections=$(ssh $SERVER_USER@$SERVER_IP "netstat -an 2>/dev/null | grep ESTABLISHED | wc -l")
    echo "  活动连接数: $connections"
    
    return 0
}

# 主函数
main() {
    local command=${1:-help}
    local container_name=${2:-}
    
    case $command in
        "status")
            check_container_status "$container_name"
            ;;
        "health")
            check_app_health "$container_name"
            ;;
        "performance")
            check_app_performance "$container_name"
            ;;
        "logs")
            show_container_logs "$container_name"
            ;;
        "monitor")
            monitor_app "$container_name"
            ;;
        "diagnose")
            diagnose_app "$container_name"
            ;;
        "system")
            check_system_status
            ;;
        "resources")
            check_system_resources
            ;;
        "network")
            check_network_status
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

# 执行主函数
main "$@"