"""
BatchProcessor 属性测试
使用 Hypothesis 进行属性测试，验证 BatchProcessor 的正确性

**Feature: data-collection-optimization**
"""
import pytest
from hypothesis import given, strategies as st, settings, assume
import string
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.batch_processor import BatchProcessor
from models.business_record import BusinessRecord


# ============================================================================
# 测试策略（Generators）
# ============================================================================

@st.composite
def business_record(draw):
    """生成商家记录"""
    return BusinessRecord(
        name=draw(st.text(min_size=1, max_size=20)),
        email=draw(st.one_of(
            st.none(),
            st.text(alphabet=string.ascii_lowercase, min_size=5, max_size=15).map(
                lambda s: f"{s}@test.com" if s else None
            )
        ))
    )


@st.composite
def record_sequence(draw, min_size=1, max_size=30):
    """生成商家记录序列"""
    count = draw(st.integers(min_value=min_size, max_value=max_size))
    return [draw(business_record()) for _ in range(count)]


# ============================================================================
# Property 13: Batch Threshold Trigger
# **Feature: data-collection-optimization, Property 13: Batch Threshold Trigger**
# **Validates: Requirements 4.1**
# ============================================================================

class TestBatchThresholdTrigger:
    """Property 13: 批量阈值触发"""
    
    @given(records=record_sequence(min_size=10, max_size=30))
    @settings(max_examples=100)
    def test_batch_triggers_at_threshold(self, records):
        """
        *For any* sequence of records added to BatchProcessor,
        a batch insert SHALL be triggered when the buffer size reaches 10 records.
        **Feature: data-collection-optimization, Property 13: Batch Threshold Trigger**
        **Validates: Requirements 4.1**
        """
        flush_count = 0
        flushed_records = []
        
        def flush_callback(batch):
            nonlocal flush_count, flushed_records
            flush_count += 1
            flushed_records.extend(batch)
            return len(batch)
        
        processor = BatchProcessor(flush_callback=flush_callback)
        
        for i, record in enumerate(records):
            processor.add(record)
            
            # 每添加10条记录应该触发一次flush
            expected_flushes = (i + 1) // 10
            assert flush_count == expected_flushes, \
                f"After {i+1} records: expected {expected_flushes} flushes, got {flush_count}"
    
    @given(count=st.integers(min_value=1, max_value=9))
    @settings(max_examples=100)
    def test_no_flush_below_threshold(self, count):
        """
        *For any* number of records below 10,
        no batch insert SHALL be triggered.
        **Feature: data-collection-optimization, Property 13: Batch Threshold Trigger**
        **Validates: Requirements 4.1**
        """
        flush_count = 0
        
        def flush_callback(batch):
            nonlocal flush_count
            flush_count += 1
            return len(batch)
        
        processor = BatchProcessor(flush_callback=flush_callback)
        
        for _ in range(count):
            processor.add(BusinessRecord(name='Test'))
        
        assert flush_count == 0, \
            f"Flush triggered with only {count} records (threshold is 10)"
        assert processor.get_buffer_size() == count
    
    @given(count=st.integers(min_value=10, max_value=50))
    @settings(max_examples=100)
    def test_flush_count_matches_threshold_crossings(self, count):
        """
        *For any* number of records,
        the number of flushes SHALL equal floor(count / 10).
        **Feature: data-collection-optimization, Property 13: Batch Threshold Trigger**
        **Validates: Requirements 4.1**
        """
        flush_count = 0
        
        def flush_callback(batch):
            nonlocal flush_count
            flush_count += 1
            return len(batch)
        
        processor = BatchProcessor(flush_callback=flush_callback)
        
        for _ in range(count):
            processor.add(BusinessRecord(name='Test'))
        
        expected_flushes = count // 10
        assert flush_count == expected_flushes, \
            f"For {count} records: expected {expected_flushes} flushes, got {flush_count}"


# ============================================================================
# Property 14: Position Save Interval
# **Feature: data-collection-optimization, Property 14: Position Save Interval**
# **Validates: Requirements 4.4**
# ============================================================================

class TestPositionSaveInterval:
    """Property 14: 位置保存间隔"""
    
    @given(count=st.integers(min_value=10, max_value=50))
    @settings(max_examples=100)
    def test_position_saved_every_10_records(self, count):
        """
        *For any* sequence of processed records,
        position save SHALL occur every 10 records.
        **Feature: data-collection-optimization, Property 14: Position Save Interval**
        **Validates: Requirements 4.4**
        """
        save_count = 0
        saved_positions = []
        
        def position_save_callback(position):
            nonlocal save_count, saved_positions
            save_count += 1
            saved_positions.append(position)
        
        def flush_callback(batch):
            return len(batch)
        
        processor = BatchProcessor(
            flush_callback=flush_callback,
            position_save_callback=position_save_callback
        )
        
        for _ in range(count):
            processor.add(BusinessRecord(name='Test'))
        
        expected_saves = count // 10
        assert save_count == expected_saves, \
            f"For {count} records: expected {expected_saves} position saves, got {save_count}"
    
    @given(count=st.integers(min_value=1, max_value=9))
    @settings(max_examples=100)
    def test_no_position_save_below_interval(self, count):
        """
        *For any* number of records below 10,
        no position save SHALL occur.
        **Feature: data-collection-optimization, Property 14: Position Save Interval**
        **Validates: Requirements 4.4**
        """
        save_count = 0
        
        def position_save_callback(position):
            nonlocal save_count
            save_count += 1
        
        processor = BatchProcessor(position_save_callback=position_save_callback)
        
        for _ in range(count):
            processor.add(BusinessRecord(name='Test'))
        
        assert save_count == 0, \
            f"Position saved with only {count} records (interval is 10)"


# ============================================================================
# 边界情况测试
# ============================================================================

class TestEdgeCases:
    """边界情况测试"""
    
    def test_default_batch_size(self):
        """默认批量大小应该是10"""
        processor = BatchProcessor()
        assert processor.batch_size == 10
    
    def test_default_position_save_interval(self):
        """默认位置保存间隔应该是10"""
        processor = BatchProcessor()
        assert processor.position_save_interval == 10
    
    def test_custom_batch_size(self):
        """应该支持自定义批量大小"""
        processor = BatchProcessor(batch_size=5)
        assert processor.batch_size == 5
    
    def test_finalize_flushes_remaining(self):
        """finalize应该刷新剩余缓冲区"""
        flushed = []
        
        def flush_callback(batch):
            flushed.extend(batch)
            return len(batch)
        
        processor = BatchProcessor(flush_callback=flush_callback)
        
        # 添加5条记录（不触发自动flush）
        for i in range(5):
            processor.add(BusinessRecord(name=f'Test{i}'))
        
        assert len(flushed) == 0
        
        # finalize应该刷新剩余的5条
        processor.finalize()
        assert len(flushed) == 5
    
    def test_clear_resets_state(self):
        """clear应该重置所有状态"""
        processor = BatchProcessor()
        
        for _ in range(5):
            processor.add(BusinessRecord(name='Test'))
        
        assert processor.get_buffer_size() == 5
        assert processor.get_total_processed() == 5
        
        processor.clear()
        
        assert processor.get_buffer_size() == 0
        assert processor.get_total_processed() == 0
    
    def test_total_processed_count(self):
        """总处理数应该正确累计"""
        processor = BatchProcessor()
        
        for i in range(25):
            processor.add(BusinessRecord(name=f'Test{i}'))
        
        assert processor.get_total_processed() == 25
