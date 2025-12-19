# Google Maps Spider 快速部署指南

## 一键部署脚本使用说明

本项目提供了 `quick-deploy.sh` 脚本，用于快速部署应用到服务器。

### 基本用法

```bash
# 查看帮助信息
./quick-deploy.sh help

# 完整部署（推荐首次使用）
./quick-deploy.sh deploy

# 仅上传代码（不部署）
./quick-deploy.sh upload

# 更新代码并重启容器（适合代码更新）
./quick-deploy.sh update

# 检查应用状态
./quick-deploy.sh status

# 查看应用日志
./quick-deploy.sh logs
```

### 常见使用场景

#### 1. 首次部署
```bash
./quick-deploy.sh deploy
```

#### 2. 代码更新后部署
```bash
# 方式1：完整重新部署
./quick-deploy.sh deploy

# 方式2：仅更新代码并重启（更快）
./quick-deploy.sh update
```

#### 3. 检查应用状态
```bash
./quick-deploy.sh status
```

#### 4. 查看应用日志
```bash
./quick-deploy.sh logs
```

### 脚本功能说明

- **自动打包**：自动打包必要文件到部署包
- **环境检查**：检查本地环境和SSH连接
- **自动上传**：通过SCP上传代码到服务器
- **自动部署**：在服务器上执行Docker Compose部署
- **状态检查**：部署后自动检查应用状态
- **日志查看**：实时查看应用日志

### 注意事项

1. 确保已配置SSH密钥认证，能够无密码登录服务器
2. 确保本地有必要的文件：Dockerfile, docker-compose.yml等
3. 脚本会自动清理临时文件
4. 部署过程中会停止现有容器，请谨慎操作

### 服务器信息

- IP地址：155.138.226.211
- 部署路径：/opt/google-maps-spider
- 访问地址：http://155.138.226.211:8088

### 故障排除

如果部署失败，可以：

1. 检查SSH连接：`ssh root@155.138.226.211`
2. 查看服务器日志：`./quick-deploy.sh logs`
3. 手动部署：登录服务器执行 `cd /opt/google-maps-spider && docker-compose up -d`
4. 检查容器状态：`docker ps -a`