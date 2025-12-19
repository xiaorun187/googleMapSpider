# Google Map Spider & Contact Extractor

这是一个基于 Flask 和 Selenium 的全栈爬虫应用，用于自动化从 Google Maps 提取商家信息，并进一步挖掘（如 Facebook 页面）以获取邮箱等联系方式。

本项目采用 **Flask + Gevent + SocketIO** 架构，支持高并发异步操作，并提供了完整的 Docker 部署方案。

## 📋 目录

- [主要功能](#-主要功能)
- [技术栈](#-技术栈)
- [环境要求](#-环境要求)
- [部署方式](#-部署方式)
  - [一键部署脚本（推荐）](#一键部署脚本推荐)
  - [手动Docker部署](#手动docker部署)
  - [服务器完整部署流程](#-服务器完整部署流程)
- [配置说明](#-配置说明)
- [常见问题解决](#-常见问题解决)
- [项目结构](#-项目结构)
- [更新日志](#-更新日志)

## 🚀 主要功能

- **Google Maps 商家采集**: 根据关键词自动采集商家的名称、地址、网站、电话等信息。
- **深度联系方式挖掘**: 自动访问商家网站或 Facebook 页面，智能提取邮箱地址。
- **实时进度监控**: 通过 WebSocket (Socket.IO) 在前端实时展示采集进度和日志。
- **数据管理**: 支持历史记录查询、Excel 导出 (.xlsx)。
- **邮件发送**: 集成邮件发送功能，可直接对采集到的客户发送营销邮件。
- **可视化界面**: 提供友好的 Web 操作界面。

## 🛠 技术栈

- **后端**: Python 3.13, Flask, Flask-SocketIO
- **服务器**: Gevent (异步高性能模式)
- **爬虫**: Selenium, Chrome/ChromeDriver (无头模式)
- **数据库**: SQLite (轻量级存储)
- **部署**: Docker, Docker Compose

## 🔧 环境要求

### 服务器要求
- **操作系统**: Linux (推荐 Ubuntu 20.04+ 或 CentOS 7+)
- **内存**: 最低 2GB RAM (推荐 4GB+，Selenium 较为耗内存)
- **存储**: 至少 10GB 可用空间
- **网络**: 稳定的互联网连接，能够访问 Google Maps

### 软件依赖
- **Docker**: 20.10+
- **Docker Compose**: 1.29+
- **SSH**: 用于远程部署（如使用一键部署脚本）

### 本地开发环境
- **Python**: 3.13
- **Chrome浏览器**: 最新版本
- **ChromeDriver**: 与Chrome版本匹配

## 🚀 部署方式

### 一键部署脚本（推荐）

我们提供了自动化部署脚本 `quick-deploy.sh`，可以一键完成代码上传和部署。

#### 1. 准备工作
```bash
# 确保脚本有执行权限
chmod +x quick-deploy.sh

# 配置SSH密钥认证（避免每次输入密码）
ssh-copy-id root@<服务器IP>
```

#### 2. 部署命令
```bash
# 完整部署（首次使用）
./quick-deploy.sh deploy

# 代码更新后快速部署
./quick-deploy.sh update

# 仅上传代码
./quick-deploy.sh upload

# 检查应用状态
./quick-deploy.sh status

# 查看应用日志
./quick-deploy.sh logs

# 查看帮助
./quick-deploy.sh help
```

#### 3. 访问应用
部署成功后，通过浏览器访问：`http://<服务器IP>:8088`

### 手动Docker部署

#### 1. 环境准备
```bash
# 安装Docker（Ubuntu）
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# 安装Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

#### 2. 部署步骤
```bash
# 1. 克隆或上传项目代码到服务器
scp -r . root@<服务器IP>:/opt/google-maps-spider/

# 2. 登录服务器并进入项目目录
ssh root@<服务器IP>
cd /opt/google-maps-spider

# 3. 构建并启动容器
docker-compose up --build -d

# 4. 查看容器状态
docker-compose ps

# 5. 查看日志（可选）
docker-compose logs -f
```

#### 3. 验证部署
```bash
# 检查容器状态
docker ps

# 检查端口监听
netstat -tlnp | grep 8088

# 测试HTTP响应
curl -I http://localhost:8088
```

### 服务器完整部署流程

#### 1. 本地准备
```bash
# 生成部署包（自动排除无关文件）
zip -r deploy.zip . -x ".hypothesis/*" ".kiro/*" "tests/*" ".git/*" "__pycache__/*" "*.pyc" ".DS_Store" "business.db-shm" "business.db-wal" "progress/*" ".venv/*" ".vscode/*" ".idea/*"
```

#### 2. 上传到服务器
```bash
# 上传部署包
scp deploy.zip root@<服务器IP>:/root/

# 登录服务器
ssh root@<服务器IP>
```

#### 3. 服务器部署
```bash
# 创建部署目录
mkdir -p /opt/google-maps-spider
cd /opt/google-maps-spider

# 解压部署包
unzip -o /root/deploy.zip

# 停止旧容器（如果存在）
docker-compose down 2>/dev/null || true

# 构建并启动新容器
docker-compose up --build -d

# 验证部署
docker-compose ps
```

## ⚙️ 配置说明

### 环境变量配置
在 `docker-compose.yml` 中可以配置以下环境变量：

```yaml
environment:
  - FLASK_ENV=production        # 运行环境：production/development
  - DATABASE_URL=sqlite:///app.db  # 数据库连接字符串
  - SECRET_KEY=your-secret-key  # Flask会话密钥
  - DEBUG=False                 # 调试模式
  - PORT=5000                   # 容器内端口
```

### 端口配置
默认端口映射为 `8088:5000`（宿主机:容器），可在 `docker-compose.yml` 中修改：

```yaml
ports:
  - "8088:5000"  # 修改宿主机端口
```

### 数据持久化
以下目录已配置为持久化卷：
- `./output:/app/output` - 导出文件存储
- `./progress:/app/progress` - 进度文件存储

### 邮件配置
如需使用邮件发送功能，请在 `config/email_config.py` 中配置SMTP信息：

```python
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USERNAME = "your-email@gmail.com"
SMTP_PASSWORD = "your-app-password"
```

## 🔧 常见问题解决

### 1. 内存不足问题
**症状**: 容器频繁重启或被系统杀死
**解决方案**: 增加swap空间
```bash
# 创建2GB swap文件
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# 设置永久生效
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# 查看swap状态
swapon --show
```

### 2. 端口访问问题
**症状**: 容器运行正常但无法从外部访问
**解决方案**:
```bash
# 检查防火墙状态
sudo ufw status

# 开放端口
sudo ufw allow 8088

# 检查云服务器安全组设置
# 确保在云服务商控制台中开放了8088端口
```

### 3. Chrome/ChromeDriver问题
**症状**: Selenium启动失败
**解决方案**:
```bash
# 查看容器内Chrome版本
docker exec -it <容器ID> google-chrome --version

# 查看ChromeDriver版本
docker exec -it <容器ID> chromedriver --version

# 如版本不匹配，更新Dockerfile中的版本号
```

### 4. 数据库问题
**症状**: 数据丢失或损坏
**解决方案**:
```bash
# 备份数据库
docker exec <容器ID> cp /app/app.db /backup/app-$(date +%Y%m%d).db

# 恢复数据库
docker cp /backup/app-20231219.db <容器ID>:/app/app.db
docker-compose restart
```

### 5. 应用无响应
**诊断步骤**:
```bash
# 1. 检查容器状态
docker-compose ps

# 2. 查看容器日志
docker-compose logs -f

# 3. 进入容器调试
docker exec -it <容器ID> /bin/bash

# 4. 检查应用进程
ps aux | grep python

# 5. 重启容器
docker-compose restart
```

## 📁 项目结构

```
google-maps-spider/
├── app.py                 # 主应用文件
├── db.py                  # 数据库操作
├── scraper.py             # 爬虫核心逻辑
├── contact_scraper.py     # 联系方式提取
├── chrome_driver.py       # Chrome驱动管理
├── requirements.txt       # Python依赖
├── Dockerfile            # Docker镜像构建文件
├── docker-compose.yml    # Docker Compose配置
├── docker-entrypoint.sh  # 容器启动脚本
├── deploy.sh             # 部署脚本
├── quick-deploy.sh       # 一键部署脚本
├── deploy-status.sh      # 状态监控脚本
├── static/               # 静态文件
│   ├── css/
│   ├── js/
│   └── images/
├── templates/            # HTML模板
├── output/               # 导出文件目录
├── progress/             # 进度文件目录
└── config/               # 配置文件目录
```

## 📝 更新日志

- **v1.0**: 初始版本，基础采集功能
- **v1.1**: 引入 Gevent 和 Docker 优化，解决 502 错误和依赖冲突
- **v1.2**: 添加一键部署脚本和状态监控功能
- **v1.3**: 优化内存使用和错误处理机制

## 📄 许可证

本项目采用 MIT 许可证。详情请参阅 LICENSE 文件。

## 🤝 贡献

欢迎提交 Issue 和 Pull Request 来改进项目。

## 📞 支持

如遇到问题，请：
1. 查看本文档的常见问题部分
2. 检查项目的 Issues 页面
3. 提交新的 Issue 描述问题