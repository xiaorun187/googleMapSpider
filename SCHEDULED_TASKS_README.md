# 定时任务功能说明

## 功能概述

定时任务功能允许系统自动在指定时间执行联系信息提取任务，无需手动触发。系统会自动查找所有有网站但没有邮箱的商家记录，并尝试从其网站提取联系方式。

## 主要特性

- ✅ **自动执行**: 每天在指定时间自动运行联系信息提取任务
- ✅ **灵活配置**: 可自定义执行时间（小时和分钟）
- ✅ **启用/禁用**: 可随时启用或禁用定时任务
- ✅ **手动触发**: 支持立即手动执行任务
- ✅ **执行历史**: 记录每次任务执行的详细信息
- ✅ **实时进度**: 通过 WebSocket 实时推送任务执行进度
- ✅ **并发控制**: 确保同时只有一个任务在运行

## 使用方法

### 1. 访问配置界面

登录系统后，在"数据提取"页面的左侧控制面板底部，可以看到"⏰ 定时任务配置"区域。

### 2. 配置执行时间

- 选择执行的**小时**（0-23）
- 选择执行的**分钟**（0-59）
- 勾选或取消"启用定时任务"复选框
- 点击"💾 保存配置"按钮

**示例**：设置为每天凌晨 2:00 执行
- 小时：02
- 分钟：00
- 启用定时任务：✓

### 3. 手动触发任务

如果需要立即执行任务而不等待定时触发，可以点击"▶️ 立即执行"按钮。

### 4. 查看执行历史

在配置区域下方的"最近执行历史"表格中，可以查看：
- 任务开始时间
- 执行状态（完成/失败/运行中）
- 成功/失败的记录数

## 技术实现

### 核心组件

1. **调度器**: 使用 APScheduler BackgroundScheduler 实现非阻塞式定时调度
2. **数据库**: SQLite 存储任务配置和执行历史
3. **WebSocket**: 实时推送任务执行进度
4. **并发控制**: 使用线程锁确保任务不会重复执行

### 数据库表

#### scheduled_tasks（任务配置表）
```sql
CREATE TABLE scheduled_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_name TEXT NOT NULL UNIQUE,
    task_type TEXT NOT NULL,
    schedule_hour INTEGER NOT NULL DEFAULT 2,
    schedule_minute INTEGER NOT NULL DEFAULT 0,
    enabled BOOLEAN NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### task_execution_history（执行历史表）
```sql
CREATE TABLE task_execution_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_name TEXT NOT NULL,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,
    status TEXT NOT NULL,  -- 'running', 'completed', 'failed'
    records_processed INTEGER DEFAULT 0,
    records_success INTEGER DEFAULT 0,
    records_failed INTEGER DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### API 接口

#### GET /api/scheduled-tasks/config
获取当前任务配置

**响应示例**:
```json
{
  "status": "success",
  "config": {
    "task_name": "contact_extraction",
    "schedule_hour": 2,
    "schedule_minute": 0,
    "enabled": true,
    "next_run_time": "2025-12-30T02:00:00"
  }
}
```

#### PUT /api/scheduled-tasks/config
更新任务配置

**请求示例**:
```json
{
  "schedule_hour": 3,
  "schedule_minute": 30,
  "enabled": true
}
```

#### POST /api/scheduled-tasks/trigger
手动触发任务

**响应示例**:
```json
{
  "status": "success",
  "message": "任务已启动",
  "execution_id": 123
}
```

#### GET /api/scheduled-tasks/history?limit=10
查询任务执行历史

**响应示例**:
```json
{
  "status": "success",
  "history": [
    {
      "id": 123,
      "task_name": "contact_extraction",
      "start_time": "2025-12-29T02:00:00",
      "end_time": "2025-12-29T02:15:30",
      "status": "completed",
      "records_processed": 150,
      "records_success": 145,
      "records_failed": 5,
      "duration_seconds": 930
    }
  ]
}
```

## 注意事项

1. **时区设置**: 确保服务器时区设置正确，定时任务将按照服务器时区执行
2. **资源占用**: 任务执行期间会启动浏览器进程，请确保服务器有足够的资源
3. **并发限制**: 系统确保同时只有一个联系信息提取任务在运行
4. **历史记录**: 系统自动保留最近 100 条执行历史记录

## 故障排查

### 任务没有按时执行

1. 检查任务是否启用（"启用定时任务"复选框是否勾选）
2. 检查服务器时区设置
3. 查看服务器日志中的调度器相关信息

### 任务执行失败

1. 查看执行历史中的错误信息
2. 检查数据库中是否有需要提取联系方式的记录
3. 确认浏览器驱动（ChromeDriver）是否正常工作
4. 检查网络连接是否正常

### 手动触发无响应

1. 检查是否有任务正在执行（同时只能运行一个任务）
2. 查看浏览器控制台是否有错误信息
3. 检查服务器日志

## 开发和测试

### 运行测试

```bash
python test_scheduled_tasks.py
```

测试脚本会验证：
- 数据库迁移是否成功
- 任务配置管理功能
- 执行历史记录功能
- 调度器初始化和关闭

### 依赖项

```
APScheduler>=3.10.0
```

## 未来改进

- [ ] 支持多种类型的定时任务
- [ ] 添加任务执行通知（邮件/Webhook）
- [ ] 支持更复杂的调度规则（每周、每月等）
- [ ] 添加任务执行超时控制
- [ ] 支持任务优先级和队列管理
