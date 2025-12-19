"""
StructuredLogger 属性测试
使用 Hypothesis 进行属性测试，验证 StructuredLogger 的正确性

**Feature: data-collection-optimization**
"""
import pytest
from hypothesis import given, strategies as st, settings
import sys
import os
import tempfile
import shutil

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.structured_logger import StructuredLogger, ScraperLogEntry


# ============================================================================
# Property 17: Error Categorization
# **Feature: data-collection-optimization, Property 17: Error Categorization**
# **Validates: Requirements 6.4**
# ============================================================================

class TestErrorCategorization:
    """Property 17: 错误分类"""
    
    @pytest.fixture(autouse=True)
    def setup_temp_dir(self):
        """创建临时目录用于测试"""
        self.temp_dir = tempfile.mkdtemp()
        yield
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @given(error_counts=st.dictionaries(
        keys=st.text(alphabet='abcdefghijklmnopqrstuvwxyz', min_size=3, max_size=15),
        values=st.integers(min_value=1, max_value=20),
        min_size=1,
        max_size=5
    ))
    @settings(max_examples=50)
    def test_error_categorization_by_type(self, error_counts):
        """
        *For any* sequence of errors,
        the error categorization SHALL correctly count errors by type.
        **Feature: data-collection-optimization, Property 17: Error Categorization**
        **Validates: Requirements 6.4**
        """
        logger = StructuredLogger(log_dir=self.temp_dir)
        
        # 记录错误
        for error_type, count in error_counts.items():
            for i in range(count):
                logger.log_error(
                    url=f'http://test.com/{error_type}/{i}',
                    error_message=f'Test error {i}',
                    error_type=error_type
                )
        
        # 验证错误统计
        errors_by_type = logger.get_errors_by_type()
        
        for error_type, expected_count in error_counts.items():
            actual_count = errors_by_type.get(error_type, 0)
            assert actual_count == expected_count, \
                f"Error type '{error_type}': expected {expected_count}, got {actual_count}"
    
    @given(error_types=st.lists(
        st.text(alphabet='abcdefghijklmnopqrstuvwxyz', min_size=3, max_size=10),
        min_size=1,
        max_size=30
    ))
    @settings(max_examples=50)
    def test_error_frequency_statistics(self, error_types):
        """
        *For any* sequence of errors,
        the error frequency statistics SHALL be accurate.
        **Feature: data-collection-optimization, Property 17: Error Categorization**
        **Validates: Requirements 6.4**
        """
        logger = StructuredLogger(log_dir=self.temp_dir)
        
        # 计算预期频率
        expected_counts = {}
        for error_type in error_types:
            expected_counts[error_type] = expected_counts.get(error_type, 0) + 1
        
        # 记录错误
        for i, error_type in enumerate(error_types):
            logger.log_error(
                url=f'http://test.com/{i}',
                error_message=f'Error {i}',
                error_type=error_type
            )
        
        # 验证频率
        errors_by_type = logger.get_errors_by_type()
        assert errors_by_type == expected_counts


# ============================================================================
# 日志条目测试
# ============================================================================

class TestScraperLogEntry:
    """日志条目测试"""
    
    @given(
        level=st.sampled_from(['INFO', 'WARNING', 'ERROR']),
        event_type=st.sampled_from(['REQUEST', 'EXTRACT', 'ERROR', 'PROGRESS']),
        url=st.one_of(st.none(), st.text(min_size=5, max_size=50)),
        status_code=st.one_of(st.none(), st.integers(min_value=100, max_value=599)),
        data_count=st.one_of(st.none(), st.integers(min_value=0, max_value=1000)),
        duration_ms=st.one_of(st.none(), st.floats(min_value=0, max_value=10000, allow_nan=False))
    )
    @settings(max_examples=50)
    def test_log_entry_json_round_trip(self, level, event_type, url, status_code, data_count, duration_ms):
        """日志条目JSON序列化往返"""
        entry = ScraperLogEntry(
            timestamp='2024-01-01T00:00:00',
            level=level,
            event_type=event_type,
            url=url,
            status_code=status_code,
            data_count=data_count,
            duration_ms=duration_ms
        )
        
        # 序列化
        json_str = entry.to_json()
        
        # 反序列化
        restored = ScraperLogEntry.from_json(json_str)
        
        # 验证关键字段
        assert restored.level == entry.level
        assert restored.event_type == entry.event_type


# ============================================================================
# 报告生成测试
# ============================================================================

class TestReportGeneration:
    """报告生成测试"""
    
    @pytest.fixture(autouse=True)
    def setup_temp_dir(self):
        """创建临时目录用于测试"""
        self.temp_dir = tempfile.mkdtemp()
        yield
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_report_contains_required_fields(self):
        """报告应该包含所有必需字段"""
        logger = StructuredLogger(log_dir=self.temp_dir)
        
        # 添加一些日志
        logger.log_request('http://test.com', 200, 100)
        logger.log_extraction('http://test.com', 5, 200)
        logger.log_error('http://test.com', 'Test error', 'NetworkError')
        
        report = logger.generate_report()
        
        assert 'summary' in report
        assert 'errors_by_type' in report
        assert 'timestamp' in report
        
        summary = report['summary']
        assert 'total_requests' in summary
        assert 'total_extractions' in summary
        assert 'total_errors' in summary
        assert 'success_rate' in summary
    
    @given(
        request_count=st.integers(min_value=0, max_value=20),
        extract_count=st.integers(min_value=0, max_value=20),
        error_count=st.integers(min_value=0, max_value=20)
    )
    @settings(max_examples=50)
    def test_report_counts_are_accurate(self, request_count, extract_count, error_count):
        """报告中的计数应该准确"""
        logger = StructuredLogger(log_dir=self.temp_dir)
        
        for i in range(request_count):
            logger.log_request(f'http://test.com/req/{i}', 200, 100)
        
        for i in range(extract_count):
            logger.log_extraction(f'http://test.com/ext/{i}', 5, 200)
        
        for i in range(error_count):
            logger.log_error(f'http://test.com/err/{i}', f'Error {i}', 'TestError')
        
        report = logger.generate_report()
        
        assert report['summary']['total_requests'] == request_count
        assert report['summary']['total_extractions'] == extract_count
        assert report['summary']['total_errors'] == error_count


# ============================================================================
# 边界情况测试
# ============================================================================

class TestEdgeCases:
    """边界情况测试"""
    
    @pytest.fixture(autouse=True)
    def setup_temp_dir(self):
        """创建临时目录用于测试"""
        self.temp_dir = tempfile.mkdtemp()
        yield
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_empty_logger(self):
        """空日志器应该正常工作"""
        logger = StructuredLogger(log_dir=self.temp_dir)
        
        assert logger.get_entry_count() == 0
        assert logger.get_errors_by_type() == {}
        
        report = logger.generate_report()
        assert report['summary']['total_requests'] == 0
        assert report['summary']['total_extractions'] == 0
        assert report['summary']['total_errors'] == 0
    
    def test_clear_resets_state(self):
        """clear应该重置所有状态"""
        logger = StructuredLogger(log_dir=self.temp_dir)
        
        logger.log_request('http://test.com', 200, 100)
        logger.log_error('http://test.com', 'Error', 'TestError')
        
        assert logger.get_entry_count() > 0
        assert len(logger.get_errors_by_type()) > 0
        
        logger.clear()
        
        assert logger.get_entry_count() == 0
        assert logger.get_errors_by_type() == {}
