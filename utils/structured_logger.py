"""
StructuredLogger - 结构化日志器
实现请求日志、提取日志、错误日志记录和爬取报告生成
"""
import json
import sys
from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import Optional, List, Dict
import os


@dataclass
class ScraperLogEntry:
    """
    爬虫日志条目
    
    Attributes:
        timestamp: 时间戳
        level: 日志级别 (INFO, WARNING, ERROR)
        event_type: 事件类型 (REQUEST, EXTRACT, ERROR, PROGRESS)
        url: URL
        status_code: HTTP状态码
        data_count: 数据数量
        error_message: 错误信息
        duration_ms: 耗时（毫秒）
        metadata: 元数据
    """
    timestamp: str
    level: str
    event_type: str
    url: Optional[str] = None
    status_code: Optional[int] = None
    data_count: Optional[int] = None
    error_message: Optional[str] = None
    duration_ms: Optional[float] = None
    metadata: Optional[Dict] = None
    
    def to_json(self) -> str:
        """序列化为JSON"""
        data = asdict(self)
        # 移除None值
        data = {k: v for k, v in data.items() if v is not None}
        return json.dumps(data, ensure_ascii=False)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'ScraperLogEntry':
        """从JSON反序列化"""
        data = json.loads(json_str)
        return cls(**data)
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return asdict(self)


class StructuredLogger:
    """
    结构化日志记录器
    
    Features:
    - 请求日志记录
    - 提取日志记录
    - 错误日志记录
    - 错误分类统计
    - 爬取报告生成
    """
    
    def __init__(self, log_file: str = 'scraper.log', log_dir: str = 'logs'):
        """
        初始化结构化日志器
        
        Args:
            log_file: 日志文件名
            log_dir: 日志目录
        """
        self.log_dir = log_dir
        self.log_file = os.path.join(log_dir, log_file)
        self.entries: List[ScraperLogEntry] = []
        self._errors_by_type: Dict[str, int] = {}
        
        # 确保日志目录存在
        os.makedirs(log_dir, exist_ok=True)
    
    def _create_entry(
        self,
        level: str,
        event_type: str,
        url: str = None,
        status_code: int = None,
        data_count: int = None,
        error_message: str = None,
        duration_ms: float = None,
        metadata: dict = None
    ) -> ScraperLogEntry:
        """创建日志条目"""
        return ScraperLogEntry(
            timestamp=datetime.now().isoformat(),
            level=level,
            event_type=event_type,
            url=url,
            status_code=status_code,
            data_count=data_count,
            error_message=error_message,
            duration_ms=duration_ms,
            metadata=metadata
        )
    
    def _write(self, entry: ScraperLogEntry) -> None:
        """写入日志条目"""
        self.entries.append(entry)
        
        # 写入文件
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(entry.to_json() + '\n')
        except Exception as e:
            print(f"写入日志文件失败: {e}", file=sys.stderr)
        
        # 同时输出到控制台
        log_msg = f"[{entry.level}] {entry.event_type}"
        if entry.url:
            log_msg += f" - {entry.url}"
        if entry.error_message:
            log_msg += f" - {entry.error_message}"
        if entry.data_count is not None:
            log_msg += f" - {entry.data_count} records"
        if entry.duration_ms is not None:
            log_msg += f" - {entry.duration_ms:.0f}ms"
        
        print(log_msg, file=sys.stderr)
    
    def log_request(self, url: str, status_code: int, duration_ms: float) -> None:
        """
        记录请求日志
        
        Args:
            url: 请求URL
            status_code: HTTP状态码
            duration_ms: 耗时（毫秒）
        """
        entry = self._create_entry(
            level='INFO',
            event_type='REQUEST',
            url=url,
            status_code=status_code,
            duration_ms=duration_ms
        )
        self._write(entry)
    
    def log_extraction(self, url: str, data_count: int, duration_ms: float) -> None:
        """
        记录提取日志
        
        Args:
            url: 页面URL
            data_count: 提取的数据数量
            duration_ms: 耗时（毫秒）
        """
        entry = self._create_entry(
            level='INFO',
            event_type='EXTRACT',
            url=url,
            data_count=data_count,
            duration_ms=duration_ms
        )
        self._write(entry)
    
    def log_error(
        self, 
        url: str, 
        error_message: str, 
        error_type: str = 'UNKNOWN',
        metadata: dict = None
    ) -> None:
        """
        记录错误日志
        
        Args:
            url: 相关URL
            error_message: 错误信息
            error_type: 错误类型
            metadata: 元数据
        """
        # 更新错误统计
        self._errors_by_type[error_type] = self._errors_by_type.get(error_type, 0) + 1
        
        entry = self._create_entry(
            level='ERROR',
            event_type='ERROR',
            url=url,
            error_message=error_message,
            metadata={'error_type': error_type, **(metadata or {})}
        )
        self._write(entry)
    
    def log_warning(self, message: str, url: str = None, metadata: dict = None) -> None:
        """
        记录警告日志
        
        Args:
            message: 警告信息
            url: 相关URL
            metadata: 元数据
        """
        entry = self._create_entry(
            level='WARNING',
            event_type='WARNING',
            url=url,
            error_message=message,
            metadata=metadata
        )
        self._write(entry)
    
    def log_progress(
        self, 
        current: int, 
        total: int, 
        message: str = None
    ) -> None:
        """
        记录进度日志
        
        Args:
            current: 当前进度
            total: 总数
            message: 进度消息
        """
        entry = self._create_entry(
            level='INFO',
            event_type='PROGRESS',
            data_count=current,
            metadata={'total': total, 'message': message}
        )
        self._write(entry)
    
    def get_errors_by_type(self) -> Dict[str, int]:
        """
        获取按类型分类的错误统计
        
        Returns:
            Dict[str, int]: 错误类型及其数量
        """
        return self._errors_by_type.copy()
    
    def generate_report(self) -> dict:
        """
        生成爬取报告
        
        Returns:
            dict: 爬取报告
        """
        request_entries = [e for e in self.entries if e.event_type == 'REQUEST']
        extract_entries = [e for e in self.entries if e.event_type == 'EXTRACT']
        error_entries = [e for e in self.entries if e.event_type == 'ERROR']
        
        # 计算平均耗时
        request_durations = [e.duration_ms for e in request_entries if e.duration_ms]
        extract_durations = [e.duration_ms for e in extract_entries if e.duration_ms]
        
        avg_request_duration = sum(request_durations) / len(request_durations) if request_durations else 0
        avg_extract_duration = sum(extract_durations) / len(extract_durations) if extract_durations else 0
        
        # 计算成功率
        total_extractions = len(extract_entries)
        total_errors = len(error_entries)
        success_rate = total_extractions / (total_extractions + total_errors) if (total_extractions + total_errors) > 0 else 0
        
        return {
            'summary': {
                'total_requests': len(request_entries),
                'total_extractions': len(extract_entries),
                'total_errors': len(error_entries),
                'success_rate': f"{success_rate * 100:.1f}%",
                'average_request_duration_ms': round(avg_request_duration, 0),
                'average_extract_duration_ms': round(avg_extract_duration, 0)
            },
            'errors_by_type': self._errors_by_type,
            'timestamp': datetime.now().isoformat()
        }
    
    def clear(self) -> None:
        """清空日志"""
        self.entries.clear()
        self._errors_by_type.clear()
    
    def get_entry_count(self) -> int:
        """获取日志条目数量"""
        return len(self.entries)
