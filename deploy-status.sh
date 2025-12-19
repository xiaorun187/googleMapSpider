#!/bin/bash

# 部署状态检查脚本
# 用于检查Docker容器和应用的运行状态

set -e

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
    echo "部署状态检查脚本"
    echo ""
    echo "用法: $0 [选项] [容器名称]"
    echo ""
    echo "选项:"
    echo "  status [容器名]     检查容器状态"
    echo "  logs [容器名]       查看容器日志"
    echo "  health [容器名]     检查应用健康状态"
    echo "  help                显示此帮助信息"
    echo ""
    echo "如果不指定容器名称，将自动检测第一个运行的容器"
}

# 检查容器状态
check_container_status() {
    local container_name=${1:-$(docker ps --format "table {{.Names}}" | grep -v NAMES | head -n 1)}
    
    if [ -z "$container_name" ]; then
        log_error "未找到运行中的容器"
        return 1
    fi
    
    log_info "检查容器状态: $container_name"
    
    # 获取容器状态
    local status=$(docker inspect "$container_name" --format '{{.State.Status}}')
    log_info "容器状态: $status"
    
    # 获取健康状态（如果有）
    local health=$(docker inspect "$container_name" --format '{{.State.Health.Status}}' 2>/dev/null || echo "no_healthcheck")
    log_info "健康状态: $health"
    
    # 获取容器IP
    local container_ip=$(docker inspect "$container_name" --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}')
    log_info "容器IP: $container_ip"
    
    # 检查端口
    local ports=$(docker port "$container_name" 2>/dev/null || echo "无端口映射")
    if [ "$ports" != "无端口映射" ]; then
        log_info "端口映射: $ports"
        
        # 提取主机端口
        local host_port=$(echo "$ports" | grep -o '0.0.0.0:[0-9]*' | cut -d':' -f2)
        if [ -n "$host_port" ]; then
            # 检查端口是否开放
            if nc -z localhost "$host_port" 2>/dev/null; then
                log_info "端口状态: open"
                
                # 检查HTTP响应
                local http_status=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:$host_port" 2>/dev/null || echo "failed")
                if [ "$http_status" != "failed" ]; then
                    log_info "HTTP状态码: $http_status"
                    
                    if [ "$http_status" = "200" ]; then
                        log_success "应用运行正常"
                    elif [ "$http_status" = "302" ]; then
                        log_warning "应用可能存在问题 (HTTP状态码: $http_status)"
                    else
                        log_warning "应用响应异常 (HTTP状态码: $http_status)"
                    fi
                else
                    log_error "无法连接到应用"
                fi
            else
                log_error "端口未开放"
            fi
        fi
    else
        log_warning "无端口映射"
    fi
    
    return 0
}

# 查看容器日志
show_container_logs() {
    local container_name=${1:-$(docker ps --format "table {{.Names}}" | grep -v NAMES | head -n 1)}
    
    if [ -z "$container_name" ]; then
        log_error "未找到运行中的容器"
        return 1
    fi
    
    log_info "查看容器日志: $container_name"
    docker logs --tail 50 -f "$container_name"
}

# 检查应用健康状态
check_app_health() {
    local container_name=${1:-$(docker ps --format "table {{.Names}}" | grep -v NAMES | head -n 1)}
    
    if [ -z "$container_name" ]; then
        log_error "未找到运行中的容器"
        return 1
    fi
    
    log_info "检查应用健康状态: $container_name"
    
    # 提取主机端口
    local ports=$(docker port "$container_name" 2>/dev/null)
    local host_port=$(echo "$ports" | grep -o '0.0.0.0:[0-9]*' | cut -d':' -f2)
    
    if [ -n "$host_port" ]; then
        # 检查HTTP响应
        local http_status=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:$host_port" 2>/dev/null || echo "failed")
        
        if [ "$http_status" = "200" ]; then
            log_success "应用健康状态: 正常"
            return 0
        elif [ "$http_status" = "302" ]; then
            log_warning "应用健康状态: 可能需要重定向"
            return 1
        else
            log_error "应用健康状态: 异常 (HTTP状态码: $http_status)"
            return 2
        fi
    else
        log_error "应用健康状态: 无端口映射"
        return 3
    fi
}

# 主函数
main() {
    local command=${1:-help}
    local container_name=${2:-}
    
    case $command in
        "status")
            check_container_status "$container_name"
            ;;
        "logs")
            show_container_logs "$container_name"
            ;;
        "health")
            check_app_health "$container_name"
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