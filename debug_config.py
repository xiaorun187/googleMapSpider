# 调试日志配置
import logging
import os
from datetime import datetime

# 确保日志目录存在
os.makedirs('logs', exist_ok=True)

# 配置日志格式
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
LOG_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

# 创建调试日志文件
DEBUG_LOG_FILE = f'logs/debug_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'

# 配置根日志记录器
logging.basicConfig(
    level=logging.DEBUG,
    format=LOG_FORMAT,
    datefmt=LOG_DATE_FORMAT,
    handlers=[
        logging.FileHandler(DEBUG_LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# 创建特定模块的日志记录器
app_logger = logging.getLogger('app')
scraper_logger = logging.getLogger('scraper')
chrome_logger = logging.getLogger('chrome_driver')
db_logger = logging.getLogger('db')

# 设置日志级别
app_logger.setLevel(logging.DEBUG)
scraper_logger.setLevel(logging.DEBUG)
chrome_logger.setLevel(logging.DEBUG)
db_logger.setLevel(logging.DEBUG)

# 调试函数
def log_function_call(func_name, args=None, kwargs=None):
    """记录函数调用"""
    app_logger.debug(f"调用函数: {func_name}")
    if args:
        app_logger.debug(f"  位置参数: {args}")
    if kwargs:
        app_logger.debug(f"  关键字参数: {kwargs}")

def log_variable_value(var_name, value):
    """记录变量值"""
    app_logger.debug(f"变量 {var_name}: {value}")

def log_exception(func_name, exception):
    """记录异常"""
    app_logger.error(f"函数 {func_name} 发生异常: {type(exception).__name__}: {str(exception)}")

def log_websocket_event(event_name, data):
    """记录WebSocket事件"""
    app_logger.debug(f"WebSocket事件: {event_name}, 数据: {data}")

def log_database_operation(operation, table, data=None):
    """记录数据库操作"""
    if data:
        db_logger.debug(f"数据库操作: {operation} 表: {table}, 数据: {data}")
    else:
        db_logger.debug(f"数据库操作: {operation} 表: {table}")

def log_selenium_action(action, element=None, url=None):
    """记录Selenium操作"""
    if element:
        chrome_logger.debug(f"Selenium操作: {action}, 元素: {element}")
    if url:
        chrome_logger.debug(f"Selenium操作: {action}, URL: {url}")
    if not element and not url:
        chrome_logger.debug(f"Selenium操作: {action}")