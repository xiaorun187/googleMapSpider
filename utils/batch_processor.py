"""
BatchProcessor - 批量处理组件
负责批量执行数据库操作以提升效率
"""
import sys
from typing import List, Callable, Optional, Any

sys.path.insert(0, '.')
from models.business_record import BusinessRecord


class BatchProcessor:
    """
    批量处理组件，负责批量执行数据库操作
    
    Features:
    - 记录缓冲区管理
    - 批量插入触发逻辑（10条触发）
    - 位置保存间隔控制（每10条保存）
    """
    
    BATCH_SIZE: int = 10
    POSITION_SAVE_INTERVAL: int = 10
    
    def __init__(
        self, 
        batch_size: int = None,
        position_save_interval: int = None,
        flush_callback: Callable[[List[BusinessRecord]], int] = None,
        position_save_callback: Callable[[int], None] = None
    ):
        """
        初始化批量处理器
        
        Args:
            batch_size: 批量大小
            position_save_interval: 位置保存间隔
            flush_callback: 批量插入回调函数
            position_save_callback: 位置保存回调函数
        """
        self.batch_size = batch_size or self.BATCH_SIZE
        self.position_save_interval = position_save_interval or self.POSITION_SAVE_INTERVAL
        self._buffer: List[BusinessRecord] = []
        self._position_counter: int = 0
        self._total_processed: int = 0
        self._flush_callback = flush_callback
        self._position_save_callback = position_save_callback
    
    def add(self, record: BusinessRecord) -> Optional[int]:
        """
        添加记录到缓冲区
        
        Args:
            record: 商家记录
            
        Returns:
            Optional[int]: 如果触发了批量插入，返回插入的记录数
        """
        self._buffer.append(record)
        self._position_counter += 1
        self._total_processed += 1
        
        result = None
        
        # 检查是否应该执行批量插入
        if self.should_flush():
            result = self.flush()
        
        # 检查是否应该保存位置
        if self.should_save_position():
            self._save_position()
        
        return result
    
    def should_flush(self) -> bool:
        """
        检查是否应该执行批量插入
        
        Returns:
            bool: 是否应该执行批量插入
        """
        return len(self._buffer) >= self.batch_size
    
    def flush(self) -> int:
        """
        执行批量插入，返回插入的记录数
        
        Returns:
            int: 插入的记录数
        """
        if not self._buffer:
            return 0
        
        count = len(self._buffer)
        
        if self._flush_callback:
            try:
                count = self._flush_callback(self._buffer)
            except Exception as e:
                print(f"批量插入失败: {e}", file=sys.stderr)
                # 尝试单条插入
                count = self._retry_individual_inserts()
        
        self._buffer.clear()
        return count
    
    def _retry_individual_inserts(self) -> int:
        """
        单条重试插入
        
        Returns:
            int: 成功插入的记录数
        """
        success_count = 0
        failed_records = []
        
        for record in self._buffer:
            try:
                if self._flush_callback:
                    self._flush_callback([record])
                    success_count += 1
            except Exception as e:
                print(f"单条插入失败: {record.name}, 错误: {e}", file=sys.stderr)
                failed_records.append(record)
        
        return success_count
    
    def should_save_position(self) -> bool:
        """
        检查是否应该保存位置
        
        Returns:
            bool: 是否应该保存位置
        """
        return self._position_counter >= self.position_save_interval
    
    def _save_position(self) -> None:
        """保存当前位置"""
        if self._position_save_callback:
            try:
                self._position_save_callback(self._total_processed)
            except Exception as e:
                print(f"保存位置失败: {e}", file=sys.stderr)
        
        self._position_counter = 0
    
    def get_buffer_size(self) -> int:
        """
        获取当前缓冲区大小
        
        Returns:
            int: 缓冲区中的记录数
        """
        return len(self._buffer)
    
    def get_total_processed(self) -> int:
        """
        获取总处理记录数
        
        Returns:
            int: 总处理记录数
        """
        return self._total_processed
    
    def finalize(self) -> int:
        """
        完成处理，刷新剩余缓冲区并保存最终位置
        
        Returns:
            int: 最后一批插入的记录数
        """
        count = self.flush()
        
        if self._position_save_callback:
            self._position_save_callback(self._total_processed)
        
        return count
    
    def clear(self) -> None:
        """清空缓冲区和计数器"""
        self._buffer.clear()
        self._position_counter = 0
        self._total_processed = 0
