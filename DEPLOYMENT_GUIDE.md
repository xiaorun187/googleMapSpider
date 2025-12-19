# Google Maps Spider 优化部署系统使用指南

## 概述

本优化部署系统包含三个主要组件：
1. `optimized-deploy.sh` - 优化的一键部署脚本
2. `enhanced-status.sh` - 增强的状态检查脚本
3. `deploy.conf` - 部署配置文件

这些组件共同提供了一个高效、可靠、用户友好的部署解决方案，具备并行处理、详细日志、错误恢复、版本控制和资源监控等功能。

## 主要功能

### 1. 并行处理
- 文件复制和上传过程并行化，显著减少部署时间
- 智能任务分配，最大化资源利用率

### 2. 详细日志记录
- 完整的部署过程日志，包含时间戳和详细状态
- 日志文件自动保存到 `logs/` 目录
- 支持不同日志级别（DEBUG, INFO, WARNING, ERROR）

### 3. 错误检测与恢复
- 自动检测常见部署错误
- 智能错误恢复机制
- 失败时自动回滚到上一个稳定版本

### 4. 用户交互优化
- 彩色输出，清晰区分不同类型的信息
- 进度条和旋转动画，提供实时反馈
- 详细的帮助信息和错误提示

### 5. 跨平台兼容性
- 支持 Linux、macOS 和 Windows (WSL)
- 自动检测操作系统并调整命令

### 6. 版本控制与回滚
- 自动创建部署备份
- 支持一键回滚到上一个稳定版本
- 保留部署历史记录

### 7. 资源监控
- 实时监控 CPU、内存和磁盘使用情况
- 资源使用超过阈值时自动告警
- 部署过程中资源消耗跟踪

## 快速开始

### 1. 基本部署

```bash
# 执行完整部署（打包 -> 上传 -> 部署）
./optimized-deploy.sh

# 或者明确指定
./optimized-deploy.sh deploy
```

### 2. 检查应用状态

```bash
# 检查容器和应用状态
./enhanced-status.sh status

# 检查应用健康状态
./enhanced-status.sh health

# 持续监控应用状态
./enhanced-status.sh monitor
```

## 详细使用说明

### optimized-deploy.sh 命令选项

#### 主要选项
- `deploy` - 完整部署（默认）
- `upload` - 仅上传代码包
- `update` - 仅更新服务器代码并重启容器
- `status` - 检查服务器应用状态
- `logs` - 查看应用日志
- `rollback` - 回滚到上一个版本
- `history` - 查看部署历史

#### 高级选项
- `monitor` - 启动资源监控
- `cleanup` - 清理本地和服务器资源
- `test` - 测试部署环境

#### 使用示例

```bash
# 完整部署
./optimized-deploy.sh deploy

# 仅上传代码
./optimized-deploy.sh upload

# 更新代码并重启
./optimized-deploy.sh update

# 回滚到上一版本
./optimized-deploy.sh rollback

# 查看部署历史
./optimized-deploy.sh history

# 测试部署环境
./optimized-deploy.sh test
```

### enhanced-status.sh 命令选项

#### 应用状态检查
- `status [容器名]` - 检查容器状态
- `health [容器名]` - 检查应用健康状态
- `performance [容器名]` - 检查应用性能指标
- `logs [容器名]` - 查看容器日志
- `monitor [容器名]` - 持续监控应用状态
- `diagnose [容器名]` - 诊断应用问题

#### 系统状态检查
- `system` - 检查服务器系统状态
- `resources` - 检查服务器资源使用情况
- `network` - 检查网络连接状态

#### 使用示例

```bash
# 检查默认容器状态
./enhanced-status.sh status

# 检查指定容器健康状态
./enhanced-status.sh health myapp

# 持续监控应用状态
./enhanced-status.sh monitor

# 诊断应用问题
./enhanced-status.sh diagnose

# 检查系统资源
./enhanced-status.sh resources
```

### 配置文件 (deploy.conf)

可以通过修改 `deploy.conf` 文件来自定义部署参数：

```bash
# 服务器连接配置
SERVER_IP="155.138.226.211"
SERVER_USER="root"
SERVER_PATH="/opt/google-maps-spider"

# 部署选项
MAX_BACKUPS=5                    # 最大保留备份数量
PARALLEL_UPLOADS=3               # 并行上传数量
RESOURCE_MONITOR_INTERVAL=5      # 资源监控间隔(秒)

# 资源限制
MAX_CPU_USAGE=80                 # 最大CPU使用率(%)
MAX_MEMORY_USAGE=85              # 最大内存使用率(%)
MIN_DISK_SPACE=1024              # 最小磁盘空间(MB)

# 部署策略
ENABLE_AUTO_ROLLBACK=true        # 是否启用自动回滚
ENABLE_BACKUP=true               # 是否创建备份
```

## 工作流程

### 完整部署流程

1. **环境检查** - 检查本地和服务器环境
2. **代码打包** - 并行复制和打包代码文件
3. **代码上传** - 并行上传代码到服务器
4. **创建备份** - 在服务器创建当前版本备份
5. **应用部署** - 停止旧容器，构建并启动新容器
6. **状态检查** - 验证应用是否正常运行
7. **资源清理** - 清理临时文件和旧镜像

### 错误恢复流程

1. **错误检测** - 自动识别常见错误类型
2. **错误分析** - 分析错误原因和影响范围
3. **恢复尝试** - 根据错误类型尝试自动恢复
4. **回滚机制** - 恢复失败时自动回滚到上一版本
5. **状态报告** - 生成详细的错误报告和恢复日志

## 最佳实践

### 1. 部署前检查

在执行部署前，建议先运行环境检查：

```bash
./optimized-deploy.sh test
```

### 2. 监控部署过程

部署过程中，可以通过另一个终端监控资源使用：

```bash
./enhanced-status.sh monitor
```

### 3. 定期清理

定期清理不需要的备份和镜像：

```bash
./optimized-deploy.sh cleanup
```

### 4. 版本管理

定期检查部署历史，保留必要的版本：

```bash
./optimized-deploy.sh history
```

## 故障排除

### 常见问题

1. **SSH连接失败**
   - 检查服务器IP和用户名是否正确
   - 确认SSH密钥已正确配置
   - 验证服务器防火墙设置

2. **Docker构建失败**
   - 检查Dockerfile语法是否正确
   - 确认所有依赖文件已包含
   - 查看构建日志定位具体错误

3. **容器启动失败**
   - 检查容器日志：`./enhanced-status.sh logs`
   - 验证端口映射是否正确
   - 确认环境变量配置

4. **应用响应异常**
   - 运行诊断：`./enhanced-status.sh diagnose`
   - 检查应用日志中的错误信息
   - 验证应用配置文件

### 日志分析

部署日志保存在 `logs/` 目录下，文件名格式为 `deploy-YYYYMMDD-HHMMSS.log`。

查看最新部署日志：
```bash
ls -lt logs/ | head -1
cat logs/deploy-$(date +%Y%m%d-*.log | tail -1)
```

### 回滚操作

如果部署后出现问题，可以快速回滚：

```bash
./optimized-deploy.sh rollback
```

## 高级用法

### 自定义部署脚本

可以通过修改 `optimized-deploy.sh` 中的函数来自定义部署流程：

- `check_local_env()` - 本地环境检查
- `package_code()` - 代码打包
- `upload_code()` - 代码上传
- `deploy_app()` - 应用部署
- `check_status()` - 状态检查

### 集成CI/CD

可以将脚本集成到CI/CD流水线中：

```yaml
# 示例 GitHub Actions 工作流
- name: Deploy to Production
  run: |
    chmod +x optimized-deploy.sh
    ./optimized-deploy.sh deploy
```

### 多环境部署

可以通过环境变量或配置文件支持多环境部署：

```bash
# 开发环境
SERVER_IP="dev.server.com" ./optimized-deploy.sh deploy

# 生产环境
SERVER_IP="prod.server.com" ./optimized-deploy.sh deploy
```

## 总结

这个优化的部署系统提供了完整的部署解决方案，具备以下优势：

1. **高效** - 并行处理显著减少部署时间
2. **可靠** - 错误检测和自动恢复机制
3. **易用** - 友好的用户界面和详细的帮助信息
4. **灵活** - 可配置的参数和可扩展的架构
5. **安全** - 版本控制和回滚功能

通过遵循本指南，您可以充分利用这个部署系统的所有功能，实现高效、可靠的应用部署。