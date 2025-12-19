"""
PerformanceMetrics - 性能指标类
实现提取时间记录、成功率计算、平均处理时间和处理速度计算
"""
import time
from dataclasses import dataclass, field
from typing import List, Dict
from datetime import datetime


@dataclass
class ExtractionMetrics:
    """
    提取指标数据类
    
    Attributes:
        total_records: 总记录数
        successful_records: 成功记录数
        failed_records: 失败记录数
        total_time_seconds: 总耗时（秒）
        extraction_times: 每条记录的提取时间列表
        errors_by_type: 按类型分类的错误统计
    """
    total_records: int = 0
    successful_records: int = 0
    failed_records: int = 0
    total_time_seconds: float = 0.0
    extraction_times: List[float] = field(default_factory=list)
    errors_by_type: Dict[str, int] = field(default_factory=dict)
    
    @property
    def success_rate(self) -> float:
        """
        计算成功率
        
        Returns:
            float: 成功率（0-1）
        """
        if self.total_records == 0:
            return 0.0
        return self.successful_records / self.total_records
    
    @property
    def average_time_per_record(self) -> float:
        """
        计算平均每条记录的处理时间
        
        Returns:
            float: 平均处理时间（秒）
        """
        if not self.extraction_times:
            return 0.0
        return sum(self.extraction_times) / len(self.extraction_times)
    
    @property
    def processing_speed(self) -> float:
        """
        计算处理速度（条/分钟）
        
        Returns:
            float: 处理速度
        """
        if self.total_time_seconds == 0:
            return 0.0
        return (self.successful_records / self.total_time_seconds) * 60
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'total_records': self.total_records,
            'successful_records': self.successful_records,
            'failed_records': self.failed_records,
            'total_time_seconds': self.total_time_seconds,
            'success_rate': self.success_rate,
            'average_time_per_record': self.average_time_per_record,
            'processing_speed': self.processing_speed,
            'errors_by_type': self.errors_by_type
        }


class PerformanceMetrics:
    """
    性能指标收集器
    
    Features:
    - 提取时间记录
    - 成功率计算
    - 平均处理时间计算
    - 处理速度计算
    """
    
    def __init__(self):
        """初始化性能指标收集器"""
        self._metrics = ExtractionMetrics()
        self._start_time: float = 0
        self._current_record_start: float = 0
        self._is_running: bool = False
    
    def start_session(self) -> None:
        """开始采集会话"""
        self._start_time = time.time()
        self._is_running = True
        self._metrics = ExtractionMetrics()
    
    def end_session(self) -> ExtractionMetrics:
        """
        结束采集会话
        
        Returns:
            ExtractionMetrics: 最终指标
        """
        if self._is_running:
            self._metrics.total_time_seconds = time.time() - self._start_time
            self._is_running = False
        return self._metrics
    
    def start_record(self) -> None:
        """开始记录单条数据的处理"""
        self._current_record_start = time.time()
    
    def end_record(self, success: bool = True, error_type: str = None) -> float:
        """
        结束记录单条数据的处理
        
        Args:
            success: 是否成功
            error_type: 错误类型（如果失败）
            
        Returns:
            float: 处理时间（秒）
        """
        elapsed = time.time() - self._current_record_start
        self._metrics.extraction_times.append(elapsed)
        self._metrics.total_records += 1
        
        if success:
            self._metrics.successful_records += 1
        else:
            self._metrics.failed_records += 1
            if error_type:
                self._metrics.errors_by_type[error_type] = \
                    self._metrics.errors_by_type.get(error_type, 0) + 1
        
        return elapsed
    
    def record_error(self, error_type: str) -> None:
        """
        记录错误
        
        Args:
            error_type: 错误类型
        """
        self._metrics.errors_by_type[error_type] = \
            self._metrics.errors_by_type.get(error_type, 0) + 1
    
    def get_current_metrics(self) -> ExtractionMetrics:
        """
        获取当前指标
        
        Returns:
            ExtractionMetrics: 当前指标
        """
        if self._is_running:
            self._metrics.total_time_seconds = time.time() - self._start_time
        return self._metrics
    
    def get_progress_info(self) -> dict:
        """
        获取进度信息（用于WebSocket更新）
        
        Returns:
            dict: 进度信息
        """
        metrics = self.get_current_metrics()
        
        # 计算预计完成时间
        eta_seconds = 0
        if metrics.average_time_per_record > 0 and metrics.total_records > 0:
            remaining = metrics.total_records - metrics.successful_records - metrics.failed_records
            eta_seconds = remaining * metrics.average_time_per_record
        
        return {
            'processed': metrics.successful_records + metrics.failed_records,
            'successful': metrics.successful_records,
            'failed': metrics.failed_records,
            'success_rate': round(metrics.success_rate * 100, 1),
            'speed': round(metrics.processing_speed, 1),
            'eta_seconds': round(eta_seconds, 0),
            'elapsed_seconds': round(metrics.total_time_seconds, 0)
        }
    
    def generate_report(self) -> dict:
        """
        生成完整报告
        
        Returns:
            dict: 完整报告
        """
        metrics = self.get_current_metrics()
        
        return {
            'summary': {
                'total_records': metrics.total_records,
                'successful_records': metrics.successful_records,
                'failed_records': metrics.failed_records,
                'success_rate': f"{metrics.success_rate * 100:.1f}%",
                'total_time': f"{metrics.total_time_seconds:.1f}s",
                'average_time_per_record': f"{metrics.average_time_per_record:.2f}s",
                'processing_speed': f"{metrics.processing_speed:.1f} records/min"
            },
            'errors': metrics.errors_by_type,
            'timestamp': datetime.now().isoformat()
        }
