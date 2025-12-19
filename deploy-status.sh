#!/bin/bash

# 部署状态监控脚本
# 用于监控Docker容器部署状态并提供反馈

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

# 获取容器状态
get_container_status() {
    local container_name=$1
    if command -v docker >/dev/null 2>&1; then
        docker inspect --format='{{.State.Status}}' "$container_name" 2>/dev/null || echo "not_found"
    else
        echo "docker_not_available"
    fi
}

# 获取容器健康状态
get_container_health() {
    local container_name=$1
    if command -v docker >/dev/null 2>&1; then
        docker inspect --format='{{.State.Health.Status}}' "$container_name" 2>/dev/null || echo "no_healthcheck"
    else
        echo "docker_not_available"
    fi
}

# 获取容器IP地址
get_container_ip() {
    local container_name=$1
    if command -v docker >/dev/null 2>&1; then
        docker inspect --format='{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$container_name" 2>/dev/null || echo "no_ip"
    else
        echo "docker_not_available"
    fi
}

# 检查应用端口是否开放
check_port() {
    local host=${1:-"localhost"}
    local port=${2:-5000}
    local timeout=${3:-5}
    
    if command -v nc >/dev/null 2>&1; then
        nc -z -w$timeout "$host" "$port" 2>/dev/null && echo "open" || echo "closed"
    elif command -v telnet >/dev/null 2>&1; then
        timeout $timeout bash -c "</dev/tcp/$host/$port" 2>/dev/null && echo "open" || echo "closed"
    else
        echo "check_not_available"
    fi
}

# 检查应用HTTP响应
check_http_response() {
    local url=${1:-"http://localhost:5000"}
    local timeout=${2:-10}
    
    if command -v curl >/dev/null 2>&1; then
        local status_code=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout $timeout "$url" 2>/dev/null || echo "000")
        echo "$status_code"
    else
        echo "curl_not_available"
    fi
}

# 显示容器状态信息
show_container_status() {
    local container_name=${1:-"gooogleMapSpider-flask-app"}
    
    log_info "检查容器状态: $container_name"
    
    local status=$(get_container_status "$container_name")
    log_info "容器状态: $status"
    
    if [ "$status" = "running" ]; then
        local health=$(get_container_health "$container_name")
        log_info "健康状态: $health"
        
        local ip=$(get_container_ip "$container_name")
        log_info "容器IP: $ip"
        
        local port_status=$(check_port "$ip" 5000)
        log_info "端口状态: $port_status"
        
        if [ "$port_status" = "open" ]; then
            local http_status=$(check_http_response "http://$ip:5000")
            log_info "HTTP状态码: $http_status"
            
            if [ "$http_status" = "200" ]; then
                log_success "应用运行正常"
                return 0
            else
                log_warning "应用可能存在问题 (HTTP状态码: $http_status)"
                return 1
            fi
        else
            log_warning "应用端口未开放"
            return 1
        fi
    else
        log_error "容器未运行"
        return 1
    fi
}

# 显示本地应用状态（非Docker环境）
show_local_status() {
    log_info "检查本地应用状态"
    
    local port_status=$(check_port "localhost" 5000)
    log_info "端口状态: $port_status"
    
    if [ "$port_status" = "open" ]; then
        local http_status=$(check_http_response "http://localhost:5000")
        log_info "HTTP状态码: $http_status"
        
        if [ "$http_status" = "200" ]; then
            log_success "应用运行正常"
            return 0
        else
            log_warning "应用可能存在问题 (HTTP状态码: $http_status)"
            return 1
        fi
    else
        log_warning "应用端口未开放"
        return 1
    fi
}

# 显示系统资源使用情况
show_resource_usage() {
    local container_name=${1:-"gooogleMapSpider-flask-app"}
    
    log_info "检查资源使用情况"
    
    if command -v docker >/dev/null 2>&1; then
        local status=$(get_container_status "$container_name")
        if [ "$status" = "running" ]; then
            log_info "容器资源使用:"
            docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}\t{{.BlockIO}}" "$container_name" 2>/dev/null || log_warning "无法获取容器资源使用情况"
        fi
    fi
    
    # 显示系统资源
    if command -v free >/dev/null 2>&1; then
        log_info "系统内存使用:"
        free -h 2>/dev/null || log_warning "无法获取内存使用情况"
    fi
    
    if command -v df >/dev/null 2>&1; then
        log_info "磁盘使用:"
        df -h /app 2>/dev/null || log_warning "无法获取磁盘使用情况"
    fi
}

# 显示应用日志
show_logs() {
    local container_name=${1:-"gooogleMapSpider-flask-app"}
    local lines=${2:-20}
    
    log_info "显示最近 $lines 行应用日志"
    
    if command -v docker >/dev/null 2>&1; then
        local status=$(get_container_status "$container_name")
        if [ "$status" = "running" ]; then
            docker logs --tail "$lines" "$container_name" 2>/dev/null || log_warning "无法获取容器日志"
        fi
    fi
    
    # 显示本地日志
    if [ -f "logs/scraper.log" ]; then
        log_info "本地日志:"
        tail -n "$lines" logs/scraper.log 2>/dev/null || log_warning "无法读取本地日志"
    fi
}

# 主函数
main() {
    local command=${1:-"status"}
    local container_name=${2:-"gooogleMapSpider-flask-app"}
    
    case "$command" in
        "status")
            if [ -f /.dockerenv ] || grep -q 'docker\|lxc' /proc/1/cgroup 2>/dev/null; then
                show_local_status
            else
                show_container_status "$container_name"
            fi
            ;;
        "resources")
            show_resource_usage "$container_name"
            ;;
        "logs")
            local lines=${3:-20}
            show_logs "$container_name" "$lines"
            ;;
        "all")
            show_container_status "$container_name"
            echo ""
            show_resource_usage "$container_name"
            echo ""
            show_logs "$container_name"
            ;;
        *)
            echo "用法: $0 {status|resources|logs|all} [容器名称] [日志行数]"
            echo "  status   - 显示应用状态"
            echo "  resources - 显示资源使用情况"
            echo "  logs     - 显示应用日志"
            echo "  all      - 显示所有信息"
            exit 1
            ;;
    esac
}

# 脚本入口点
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi