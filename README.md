# Google Map Spider & Contact Extractor

这是一个基于 Flask 和 Selenium 的全栈爬虫应用，用于自动化从 Google Maps 提取商家信息，并进一步挖掘（如 Facebook 页面）以获取邮箱等联系方式。

本项目采用 **Flask + Gevent + SocketIO** 架构，支持高并发异步操作，并提供了完整的 Docker 部署方案。

## 🚀 主要功能

- **Google Maps 商家采集**: 根据关键词自动采集商家的名称、地址、网站、电话等信息。
- **深度联系方式挖掘**: 自动访问商家网站或 Facebook 页面，智能提取邮箱地址。
- **实时进度监控**: 通过 WebSocket (Socket.IO) 在前端实时展示采集进度和日志。
- **数据管理**: 支持历史记录查询、Excel 导出 (.xlsx)。
- **邮件发送**: 集成邮件发送功能，可直接对采集到的客户发送营销邮件。
- **可视化界面**: 提供友好的 Web 操作界面。

## 🛠 技术栈

- **后端**: Python 3.10, Flask, Flask-SocketIO
- **服务器**: Gevent (异步高性能模式)
- **爬虫**: Selenium, Chrome/ChromeDriver (无头模式)
- **数据库**: SQLite (轻量级存储)
- **部署**: Docker, Docker Compose

## 📦 快速开始 (Docker 部署 - 推荐)

我们对 Docker 镜像进行了深度优化，支持层级缓存（Layer Caching），构建速度极快。

### 1. 环境准备
- 确保服务器已安装 `Docker` 和 `Docker Compose`。
- 建议服务器配置：2GB RAM 以上（Selenium 较为耗内存）。

### 2. 部署步骤

```bash
# 1. 构建并后台运行
docker-compose up --build -d

# 2. 查看容器状态
docker ps

# 3. 访问应用
# 打开浏览器访问 http://<服务器IP>:<端口> (默认端口见 docker-compose.yml，通常为 8088 或 5000)
```

### 3. 查看日志
如果需要排查问题：
```bash
docker logs -f <容器ID>
```

## 💻 本地开发运行

如果您需要在本地进行开发或调试：

1. **安装依赖**:
   ```bash
   pip install -r requirements.txt
   ```
   *注意: 本地运行可能需要手动配置 Chrome 和 ChromeDriver 的路径，或者依靠 `webdriver-manager` 自动管理。*

2. **运行应用**:
   ```bash
   python app.py
   ```

## ☁️ 服务器端完整部署流程

### 1. 本地打包
在本地项目根目录下运行以下命令生成部署包：
```bash
# 生成 deploy.zip (自动排除无关文件)
zip -r deploy.zip . -x "venv/*" -x "__pycache__/*" -x ".git/*" -x "*.DS_Store" -x "deploy_*.zip" -x "output/*"
```

### 2. 上传至服务器
使用 `scp` 或 FTP 工具将 `deploy.zip` 上传到服务器。
例如：
```bash
scp deploy.zip root@<服务器IP>:/root/
```

### 3. 服务器端操作
登录服务器并执行部署：
```bash
# 1. 进入目录并解压 (覆盖更新)
cd /root
unzip -o deploy_v13.zip -d google_map_spider/

# 2. 停止旧容器并重新构建启动
cd google_map_spider/ && docker-compose down && docker-compose up --build -d

# 3. 验证运行状态
docker ps
```

## ⚠️ 常见问题与优化

### 内存不足
爬虫运行时会启动 Chrome 浏览器实例，这比较消耗内存。如果您的服务器内存较小（如 1GB），可能会导致进程被系统杀掉 (OOM Kill)。
**解决方案**: 增加服务器的 swap (虚拟内存)。
```bash
# 创建 2G 的 swap 文件
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
# 设置永久生效
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

### 端口访问不通
如果容器启动正常 (Up 状态) 但外部无法访问，请检查：
1. 云服务器的**安全组/防火墙**是否放行了对应端口 (如 8088)。
2. 本地防火墙设置。

## 📝 更新日志

- **v1.0**: 初始版本，基础采集功能。
- **v1.1**: 引入 Gevent 和 Docker 优化，解决 502 错误和依赖冲突，提升并发稳定性。
