# Docker部署指南

本项目已更新为支持Docker容器环境部署，提供了完整的部署脚本和状态监控工具。

## 文件说明

### 部署脚本
- `deploy.sh` - Docker兼容部署脚本，适用于Docker容器环境和本地环境
- `docker-entrypoint.sh` - Docker容器专用启动脚本
- `deploy-status.sh` - 部署状态监控脚本
- `test-docker.sh` - Docker测试脚本

### Docker配置
- `Dockerfile` - Docker镜像构建配置
- `docker-compose.yml` - Docker Compose配置
- `.dockerignore` - Docker构建忽略文件

## 使用方法

### 1. 本地部署

```bash
# 直接运行部署脚本
./deploy.sh
```

### 2. Docker部署

#### 使用Docker Compose（推荐）

```bash
# 构建并启动服务
docker-compose up -d

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

#### 使用Docker命令

```bash
# 构建镜像
docker build -t google-maps-spider .

# 运行容器
docker run -d --name google-maps-spider -p 8088:5000 google-maps-spider
```

### 3. 部署状态监控

```bash
# 检查应用状态
./deploy-status.sh status

# 检查资源使用情况
./deploy-status.sh resources

# 查看应用日志
./deploy-status.sh logs

# 查看所有信息
./deploy-status.sh all
```

### 4. 测试Docker部署

```bash
# 执行完整测试流程
./test-docker.sh test

# 单独测试步骤
./test-docker.sh build
./test-docker.sh run
./test-docker.sh health
./test-docker.sh cleanup
```

## 环境变量

可以通过环境变量自定义应用行为：

```bash
# Flask环境
FLASK_ENV=production  # 或 development
PORT=5000

# Chrome相关
CHROME_BIN=/usr/bin/google-chrome
CHROMEDRIVER_PATH=/usr/local/bin/chromedriver

# Docker环境
IS_DOCKER=true
PYTHONPATH=/app
```

## 目录结构

```
/Users/hanglu/gooogleMapSpider/
├── app.py                 # Flask应用主文件
├── db.py                  # 数据库操作
├── deploy.sh              # Docker兼容部署脚本
├── docker-entrypoint.sh   # Docker容器启动脚本
├── deploy-status.sh       # 部署状态监控脚本
├── test-docker.sh         # Docker测试脚本
├── Dockerfile             # Docker镜像构建配置
├── docker-compose.yml     # Docker Compose配置
├── .dockerignore          # Docker构建忽略文件
├── requirements.txt       # Python依赖
├── output/                # 输出目录
├── logs/                  # 日志目录
└── temp/                  # 临时文件目录
```

## 故障排除

### 容器启动失败

1. 检查容器日志：
   ```bash
   docker logs <容器名称>
   ```

2. 检查容器状态：
   ```bash
   docker ps -a
   ```

3. 检查资源使用：
   ```bash
   docker stats
   ```

### 应用无法访问

1. 检查端口映射：
   ```bash
   docker port <容器名称>
   ```

2. 检查防火墙设置

3. 检查应用日志：
   ```bash
   ./deploy-status.sh logs
   ```

### 数据库问题

1. 检查数据库文件权限：
   ```bash
   ls -la google_maps_data.db
   ```

2. 重新初始化数据库：
   ```bash
   rm google_maps_data.db
   docker-compose restart
   ```

## 性能优化

1. 使用多阶段构建减少镜像大小
2. 优化依赖安装顺序
3. 使用.dockerignore排除不必要文件
4. 设置适当的资源限制

## 安全注意事项

1. 不要在生产环境中使用root用户运行应用
2. 定期更新基础镜像和依赖
3. 使用环境变量管理敏感信息
4. 限制容器资源使用

## 更新日志

- 重新开发了适用于Docker容器环境的部署脚本
- 添加了错误处理和状态反馈功能
- 清理了之前的临时文件和缓存
- 提供了完整的测试和监控工具