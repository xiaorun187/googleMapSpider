"""
日志配置模块
为定时任务配置独立的日志文件
"""

import logging
import os
from logging.handlers import RotatingFileHandler

# 确保日志目录存在
LOGS_DIR = os.environ.get('LOGS_DIR', 'logs')
os.makedirs(LOGS_DIR, exist_ok=True)


def setup_scheduler_logging():
    """
    配置定时任务专用日志记录器
    
    特性:
    - 独立的日志文件 (logs/scheduled_tasks.log)
    - 自动轮转 (最大 10MB，保留 5 个备份)
    - 详细的日志格式（时间、级别、模块、消息）
    """
    # 创建定时任务专用日志记录器
    scheduler_logger = logging.getLogger('scheduled_tasks')
    scheduler_logger.setLevel(logging.INFO)
    
    # 避免重复添加处理器
    if scheduler_logger.handlers:
        return scheduler_logger
    
    # 创建文件处理器（带轮转）
    log_file = os.path.join(LOGS_DIR, 'scheduled_tasks.log')
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.INFO)
    
    # 创建控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # 设置日志格式
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # 添加处理器
    scheduler_logger.addHandler(file_handler)
    scheduler_logger.addHandler(console_handler)
    
    return scheduler_logger


def setup_app_logging():
    """
    配置应用主日志记录器
    
    特性:
    - 应用主日志文件 (logs/app.log)
    - 自动轮转 (最大 20MB，保留 10 个备份)
    - 详细的日志格式
    """
    # 创建应用日志记录器
    app_logger = logging.getLogger('app')
    app_logger.setLevel(logging.INFO)
    
    # 避免重复添加处理器
    if app_logger.handlers:
        return app_logger
    
    # 创建文件处理器（带轮转）
    log_file = os.path.join(LOGS_DIR, 'app.log')
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=20 * 1024 * 1024,  # 20MB
        backupCount=10,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.INFO)
    
    # 创建控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # 设置日志格式
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # 添加处理器
    app_logger.addHandler(file_handler)
    app_logger.addHandler(console_handler)
    
    return app_logger


def get_scheduler_logger():
    """获取定时任务日志记录器"""
    return logging.getLogger('scheduled_tasks')


def get_app_logger():
    """获取应用日志记录器"""
    return logging.getLogger('app')


# 在模块导入时自动初始化日志配置
setup_scheduler_logging()
setup_app_logging()
