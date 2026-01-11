"""
企业级日志模块 (Enterprise Logger)
实现统一的结构化日志记录、敏感信息脱敏和业务场景日志

基于日志方案设计规范，支持以下功能：
- 基础元数据（log_id, timestamp, service_name 等）
- 业务场景维度（HTTP、数据库、定时任务等）
- 错误追踪维度（error_code, stack_trace, biz_context）
- 敏感信息自动脱敏
- JSON 格式输出
"""

import json
import logging
import os
import re
import socket
import threading
import traceback
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from logging.handlers import RotatingFileHandler
from typing import Any, Dict, Optional, List


# ============================================================================
# 日志级别枚举
# ============================================================================
class LogLevel(Enum):
    """日志级别枚举"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"
    FATAL = "FATAL"
    
    def to_logging_level(self) -> int:
        """转换为 Python logging 级别"""
        mapping = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARN": logging.WARNING,
            "ERROR": logging.ERROR,
            "FATAL": logging.CRITICAL
        }
        return mapping.get(self.value, logging.INFO)


# ============================================================================
# 敏感信息脱敏器
# ============================================================================
class DataMasker:
    """
    敏感信息脱敏器
    
    支持脱敏类型：
    - 手机号：138****1234
    - 邮箱：t***@example.com
    - 银行卡：6222********1234
    - 身份证：110***********1234
    - 密码：完全移除
    """
    
    # 预编译正则表达式
    PHONE_PATTERN = re.compile(r'(\d{3})\d{4}(\d{4})')
    EMAIL_PATTERN = re.compile(r'([a-zA-Z0-9])[a-zA-Z0-9.]*@([a-zA-Z0-9.-]+)')
    BANK_CARD_PATTERN = re.compile(r'(\d{4})\d{8,12}(\d{4})')
    ID_CARD_PATTERN = re.compile(r'(\d{3})\d{11,12}(\d{4})')
    
    # 敏感字段名列表
    SENSITIVE_FIELDS = {'password', 'passwd', 'pwd', 'secret', 'token', 'api_key', 'apikey'}
    
    @classmethod
    def mask_phone(cls, phone: str) -> str:
        """脱敏手机号"""
        if not phone:
            return phone
        return cls.PHONE_PATTERN.sub(r'\1****\2', str(phone))
    
    @classmethod
    def mask_email(cls, email: str) -> str:
        """脱敏邮箱"""
        if not email:
            return email
        return cls.EMAIL_PATTERN.sub(r'\1***@\2', str(email))
    
    @classmethod
    def mask_bank_card(cls, card: str) -> str:
        """脱敏银行卡号"""
        if not card:
            return card
        return cls.BANK_CARD_PATTERN.sub(r'\1********\2', str(card))
    
    @classmethod
    def mask_id_card(cls, id_card: str) -> str:
        """脱敏身份证号"""
        if not id_card:
            return id_card
        return cls.ID_CARD_PATTERN.sub(r'\1***********\2', str(id_card))
    
    @classmethod
    def mask_dict(cls, data: Dict[str, Any], deep: bool = True) -> Dict[str, Any]:
        """
        脱敏字典中的敏感信息
        
        Args:
            data: 待脱敏的字典
            deep: 是否深度处理嵌套字典
        
        Returns:
            脱敏后的字典
        """
        if not isinstance(data, dict):
            return data
        
        result = {}
        for key, value in data.items():
            key_lower = key.lower()
            
            # 移除敏感字段
            if key_lower in cls.SENSITIVE_FIELDS:
                result[key] = "***MASKED***"
                continue
            
            # 处理嵌套字典
            if deep and isinstance(value, dict):
                result[key] = cls.mask_dict(value, deep)
            elif isinstance(value, str):
                # 自动检测并脱敏
                masked = value
                if 'phone' in key_lower or 'mobile' in key_lower:
                    masked = cls.mask_phone(value)
                elif 'email' in key_lower or 'mail' in key_lower:
                    masked = cls.mask_email(value)
                elif 'card' in key_lower:
                    masked = cls.mask_bank_card(value)
                elif 'id_card' in key_lower or 'idcard' in key_lower:
                    masked = cls.mask_id_card(value)
                result[key] = masked
            else:
                result[key] = value
        
        return result


# ============================================================================
# 日志条目数据类
# ============================================================================
@dataclass
class LogEntry:
    """
    日志条目
    
    包含基础元数据、业务场景字段和错误追踪字段
    """
    # 基础元数据（必选）
    log_id: str
    timestamp: str
    service_name: str
    level: str
    message: str
    
    # 基础元数据（可选）
    service_ip: Optional[str] = None
    service_port: Optional[int] = None
    env: Optional[str] = None
    thread_name: Optional[str] = None
    
    # 业务场景字段
    event_type: Optional[str] = None
    
    # HTTP接口日志
    request_id: Optional[str] = None
    method: Optional[str] = None
    path: Optional[str] = None
    status_code: Optional[int] = None
    request_params: Optional[Dict] = None
    response_result: Optional[str] = None
    duration_ms: Optional[float] = None
    
    # 数据库操作日志
    db_type: Optional[str] = None
    db_instance: Optional[str] = None
    sql: Optional[str] = None
    db_duration_ms: Optional[float] = None
    affect_rows: Optional[int] = None
    
    # 定时任务日志
    task_name: Optional[str] = None
    task_cron: Optional[str] = None
    task_status: Optional[str] = None
    task_duration_ms: Optional[float] = None
    
    # 爬虫业务日志
    url: Optional[str] = None
    data_count: Optional[int] = None
    
    # 错误追踪字段
    error_code: Optional[str] = None
    error_msg: Optional[str] = None
    stack_trace: Optional[str] = None
    biz_context: Optional[Dict] = None
    
    # 扩展元数据
    metadata: Optional[Dict] = field(default_factory=dict)
    
    def to_json(self, indent: Optional[int] = None) -> str:
        """序列化为 JSON"""
        data = asdict(self)
        # 移除 None 值以减少日志体积
        data = {k: v for k, v in data.items() if v is not None}
        return json.dumps(data, ensure_ascii=False, indent=indent)
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        data = asdict(self)
        return {k: v for k, v in data.items() if v is not None}


# ============================================================================
# JSON 格式化器
# ============================================================================
class JsonFormatter(logging.Formatter):
    """JSON 格式化器，用于 Python logging 集成"""
    
    def __init__(self, service_name: str, env: str = "dev"):
        super().__init__()
        self.service_name = service_name
        self.env = env
        self._service_ip = self._get_local_ip()
    
    @staticmethod
    def _get_local_ip() -> str:
        """获取本机 IP"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"
    
    def format(self, record: logging.LogRecord) -> str:
        """格式化日志记录为 JSON"""
        log_data = {
            "log_id": str(uuid.uuid4()),
            "timestamp": datetime.now().isoformat(),
            "service_name": self.service_name,
            "service_ip": self._service_ip,
            "env": self.env,
            "level": record.levelname,
            "thread_name": threading.current_thread().name,
            "message": record.getMessage(),
            "module": record.module,
            "func_name": record.funcName,
            "line_no": record.lineno
        }
        
        # 添加异常信息
        if record.exc_info:
            log_data["stack_trace"] = self.formatException(record.exc_info)
        
        # 添加额外字段
        if hasattr(record, 'extra_data') and record.extra_data:
            log_data.update(record.extra_data)
        
        return json.dumps(log_data, ensure_ascii=False)


# ============================================================================
# 企业级日志类
# ============================================================================
class EnterpriseLogger:
    """
    企业级日志记录器
    
    Features:
    - 统一的 JSON 格式输出
    - 自动生成 log_id 用于链路追踪
    - 支持多种业务场景日志
    - 敏感信息自动脱敏
    - 错误分类统计
    """
    
    def __init__(
        self,
        service_name: str = "google-map-spider",
        log_dir: str = "logs",
        env: Optional[str] = None,
        service_port: int = 5000,
        max_bytes: int = 20 * 1024 * 1024,
        backup_count: int = 10,
        level: LogLevel = LogLevel.INFO,
        enable_console: bool = True,
        enable_file: bool = True,
        mask_sensitive: bool = True
    ):
        """
        初始化企业级日志器
        
        Args:
            service_name: 服务名称
            log_dir: 日志目录
            env: 环境标识（dev/test/pre/prod）
            service_port: 服务端口
            max_bytes: 日志文件最大大小
            backup_count: 日志备份数量
            level: 日志级别
            enable_console: 是否输出到控制台
            enable_file: 是否输出到文件
            mask_sensitive: 是否启用敏感信息脱敏
        """
        self.service_name = service_name
        self.log_dir = log_dir
        self.env = env or os.environ.get("ENV", "dev")
        self.service_port = service_port
        self.level = level
        self.mask_sensitive = mask_sensitive
        
        # 获取本机 IP
        self._service_ip = self._get_local_ip()
        
        # 错误统计
        self._errors_by_type: Dict[str, int] = {}
        self._lock = threading.Lock()
        
        # 确保日志目录存在
        os.makedirs(log_dir, exist_ok=True)
        
        # 设置 Python logging
        self._logger = logging.getLogger(service_name)
        self._logger.setLevel(level.to_logging_level())
        self._logger.handlers.clear()  # 清除已有 handlers
        
        # JSON 格式化器
        self._formatter = JsonFormatter(service_name, self.env)
        
        # 文件处理器
        if enable_file:
            log_file = os.path.join(log_dir, f"{service_name}.log")
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding='utf-8'
            )
            file_handler.setFormatter(self._formatter)
            self._logger.addHandler(file_handler)
        
        # 控制台处理器
        if enable_console:
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(self._formatter)
            self._logger.addHandler(console_handler)
    
    @staticmethod
    def _get_local_ip() -> str:
        """获取本机 IP"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"
    
    def _create_entry(
        self,
        level: LogLevel,
        message: str,
        **kwargs
    ) -> LogEntry:
        """创建日志条目"""
        # 处理业务上下文脱敏
        biz_context = kwargs.get('biz_context')
        if biz_context and self.mask_sensitive:
            kwargs['biz_context'] = DataMasker.mask_dict(biz_context)
        
        return LogEntry(
            log_id=str(uuid.uuid4()),
            timestamp=datetime.now().isoformat(),
            service_name=self.service_name,
            service_ip=self._service_ip,
            service_port=self.service_port,
            env=self.env,
            level=level.value,
            thread_name=threading.current_thread().name,
            message=message,
            **kwargs
        )
    
    def _log(self, level: LogLevel, message: str, **kwargs) -> LogEntry:
        """内部日志方法"""
        entry = self._create_entry(level, message, **kwargs)
        
        # 使用标准 logging 输出
        log_record = self._logger.makeRecord(
            self._logger.name,
            level.to_logging_level(),
            "",  # filename
            0,   # lineno
            message,
            (),  # args
            None # exc_info
        )
        log_record.extra_data = entry.to_dict()
        self._logger.handle(log_record)
        
        return entry
    
    # ========================================================================
    # 标准日志级别方法
    # ========================================================================
    
    def debug(self, message: str, **kwargs) -> LogEntry:
        """DEBUG 级别日志"""
        return self._log(LogLevel.DEBUG, message, **kwargs)
    
    def info(self, message: str, **kwargs) -> LogEntry:
        """INFO 级别日志"""
        return self._log(LogLevel.INFO, message, **kwargs)
    
    def warn(self, message: str, **kwargs) -> LogEntry:
        """WARN 级别日志"""
        return self._log(LogLevel.WARN, message, **kwargs)
    
    def error(
        self,
        message: str,
        error: Optional[Exception] = None,
        error_code: Optional[str] = None,
        **kwargs
    ) -> LogEntry:
        """
        ERROR 级别日志
        
        Args:
            message: 错误消息
            error: 异常对象
            error_code: 错误码
        """
        if error:
            kwargs['error_msg'] = str(error)
            kwargs['stack_trace'] = traceback.format_exc()
            
            # 统计错误类型
            error_type = error_code or type(error).__name__
            with self._lock:
                self._errors_by_type[error_type] = self._errors_by_type.get(error_type, 0) + 1
        
        kwargs['error_code'] = error_code
        return self._log(LogLevel.ERROR, message, **kwargs)
    
    def fatal(
        self,
        message: str,
        error: Optional[Exception] = None,
        error_code: Optional[str] = None,
        **kwargs
    ) -> LogEntry:
        """FATAL 级别日志"""
        if error:
            kwargs['error_msg'] = str(error)
            kwargs['stack_trace'] = traceback.format_exc()
        
        kwargs['error_code'] = error_code
        return self._log(LogLevel.FATAL, message, **kwargs)
    
    # ========================================================================
    # 业务场景快捷方法
    # ========================================================================
    
    def log_http_request(
        self,
        message: str,
        method: str,
        path: str,
        status_code: int,
        duration_ms: float,
        request_id: Optional[str] = None,
        request_params: Optional[Dict] = None,
        response_result: Optional[str] = None,
        **kwargs
    ) -> LogEntry:
        """记录 HTTP 请求日志"""
        level = LogLevel.INFO if status_code < 400 else LogLevel.ERROR
        
        # 脱敏请求参数
        if request_params and self.mask_sensitive:
            request_params = DataMasker.mask_dict(request_params)
        
        return self._log(
            level,
            message,
            event_type="HTTP_REQUEST",
            method=method,
            path=path,
            status_code=status_code,
            duration_ms=duration_ms,
            request_id=request_id or str(uuid.uuid4()),
            request_params=request_params,
            response_result=response_result,
            **kwargs
        )
    
    def log_db_operation(
        self,
        message: str,
        db_type: str,
        sql: str,
        duration_ms: float,
        db_instance: Optional[str] = None,
        affect_rows: Optional[int] = None,
        **kwargs
    ) -> LogEntry:
        """记录数据库操作日志"""
        return self._log(
            LogLevel.INFO,
            message,
            event_type="DB_OPERATION",
            db_type=db_type,
            db_instance=db_instance,
            sql=sql[:500] if len(sql) > 500 else sql,  # SQL 截断
            db_duration_ms=duration_ms,
            affect_rows=affect_rows,
            **kwargs
        )
    
    def log_scheduled_task(
        self,
        message: str,
        task_name: str,
        task_status: str,
        duration_ms: Optional[float] = None,
        task_cron: Optional[str] = None,
        **kwargs
    ) -> LogEntry:
        """记录定时任务日志"""
        level = LogLevel.INFO if task_status == "SUCCESS" else LogLevel.ERROR
        return self._log(
            level,
            message,
            event_type="SCHEDULED_TASK",
            task_name=task_name,
            task_status=task_status,
            task_duration_ms=duration_ms,
            task_cron=task_cron,
            **kwargs
        )
    
    def log_scraper(
        self,
        message: str,
        url: Optional[str] = None,
        data_count: Optional[int] = None,
        duration_ms: Optional[float] = None,
        level: LogLevel = LogLevel.INFO,
        **kwargs
    ) -> LogEntry:
        """记录爬虫操作日志"""
        return self._log(
            level,
            message,
            event_type="SCRAPER",
            url=url,
            data_count=data_count,
            duration_ms=duration_ms,
            **kwargs
        )
    
    def log_progress(
        self,
        current: int,
        total: int,
        message: str = "",
        **kwargs
    ) -> LogEntry:
        """记录进度日志"""
        progress_pct = (current / total * 100) if total > 0 else 0
        return self._log(
            LogLevel.INFO,
            message or f"进度: {current}/{total} ({progress_pct:.1f}%)",
            event_type="PROGRESS",
            data_count=current,
            metadata={"total": total, "progress_pct": progress_pct, **(kwargs.get('metadata', {}))},
            **kwargs
        )
    
    def log_extraction(
        self,
        url: str,
        success_count: int,
        fail_count: int,
        duration_ms: float = 0,
        **kwargs
    ) -> LogEntry:
        """记录数据提取日志"""
        level = LogLevel.INFO if fail_count == 0 else LogLevel.WARN
        return self._log(
            level,
            f"提取完成: 成功 {success_count}, 失败 {fail_count}",
            event_type="EXTRACTION",
            url=url,
            data_count=success_count,
            duration_ms=duration_ms,
            metadata={"fail_count": fail_count, **(kwargs.get('metadata', {}))},
            **kwargs
        )
    
    def log_request(
        self,
        url: str,
        status_code: int,
        duration_ms: float,
        **kwargs
    ) -> LogEntry:
        """记录请求日志（兼容旧接口）"""
        return self._log(
            LogLevel.INFO,
            f"请求完成: {status_code}",
            event_type="REQUEST",
            url=url,
            status_code=status_code,
            duration_ms=duration_ms,
            **kwargs
        )
    
    def log_warning(
        self,
        message: str,
        url: Optional[str] = None,
        **kwargs
    ) -> LogEntry:
        """记录警告日志（兼容旧接口）"""
        return self.warn(message, url=url, event_type="WARNING", **kwargs)
    
    # ========================================================================
    # 统计与报告
    # ========================================================================
    
    def get_errors_by_type(self) -> Dict[str, int]:
        """获取按类型分类的错误统计"""
        with self._lock:
            return self._errors_by_type.copy()
    
    def reset_stats(self):
        """重置统计信息"""
        with self._lock:
            self._errors_by_type.clear()


# ============================================================================
# 全局日志实例
# ============================================================================
_default_logger: Optional[EnterpriseLogger] = None


def get_logger(
    service_name: str = "google-map-spider",
    **kwargs
) -> EnterpriseLogger:
    """
    获取全局日志实例（单例模式）
    
    Args:
        service_name: 服务名称
        **kwargs: 其他配置参数
    
    Returns:
        EnterpriseLogger 实例
    """
    global _default_logger
    if _default_logger is None:
        _default_logger = EnterpriseLogger(service_name=service_name, **kwargs)
    return _default_logger


def create_logger(
    service_name: str,
    **kwargs
) -> EnterpriseLogger:
    """
    创建新的日志实例
    
    Args:
        service_name: 服务名称
        **kwargs: 其他配置参数
    
    Returns:
        新的 EnterpriseLogger 实例
    """
    return EnterpriseLogger(service_name=service_name, **kwargs)
