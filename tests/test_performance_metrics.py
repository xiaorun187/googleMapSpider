"""
PerformanceMetrics 属性测试
使用 Hypothesis 进行属性测试，验证 PerformanceMetrics 的正确性

**Feature: data-collection-optimization**
"""
import pytest
from hypothesis import given, strategies as st, settings, assume
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.performance_metrics import PerformanceMetrics, ExtractionMetrics


# ============================================================================
# Property 16: Statistics Calculation
# **Feature: data-collection-optimization, Property 16: Statistics Calculation**
# **Validates: Requirements 6.3**
# ============================================================================

class TestStatisticsCalculation:
    """Property 16: 统计计算"""
    
    @given(
        successful=st.integers(min_value=0, max_value=100),
        failed=st.integers(min_value=0, max_value=100)
    )
    @settings(max_examples=100)
    def test_success_rate_calculation(self, successful, failed):
        """
        *For any* success/failure counts,
        the success rate SHALL be mathematically correct.
        **Feature: data-collection-optimization, Property 16: Statistics Calculation**
        **Validates: Requirements 6.3**
        """
        total = successful + failed
        
        metrics = ExtractionMetrics(
            total_records=total,
            successful_records=successful,
            failed_records=failed
        )
        
        if total == 0:
            assert metrics.success_rate == 0.0
        else:
            expected_rate = successful / total
            assert abs(metrics.success_rate - expected_rate) < 1e-9, \
                f"Success rate: expected {expected_rate}, got {metrics.success_rate}"
    
    @given(times=st.lists(
        st.floats(min_value=0.01, max_value=10.0, allow_nan=False, allow_infinity=False),
        min_size=1,
        max_size=50
    ))
    @settings(max_examples=100)
    def test_average_time_calculation(self, times):
        """
        *For any* list of extraction times,
        the average time SHALL be mathematically correct.
        **Feature: data-collection-optimization, Property 16: Statistics Calculation**
        **Validates: Requirements 6.3**
        """
        metrics = ExtractionMetrics(extraction_times=times)
        
        expected_avg = sum(times) / len(times)
        assert abs(metrics.average_time_per_record - expected_avg) < 1e-9, \
            f"Average time: expected {expected_avg}, got {metrics.average_time_per_record}"
    
    @given(
        successful=st.integers(min_value=1, max_value=100),
        total_time=st.floats(min_value=1.0, max_value=3600.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100)
    def test_processing_speed_calculation(self, successful, total_time):
        """
        *For any* successful count and total time,
        the processing speed SHALL be mathematically correct.
        **Feature: data-collection-optimization, Property 16: Statistics Calculation**
        **Validates: Requirements 6.3**
        """
        metrics = ExtractionMetrics(
            successful_records=successful,
            total_time_seconds=total_time
        )
        
        expected_speed = (successful / total_time) * 60  # records per minute
        assert abs(metrics.processing_speed - expected_speed) < 1e-6, \
            f"Processing speed: expected {expected_speed}, got {metrics.processing_speed}"
    
    def test_empty_metrics(self):
        """空指标应该返回零值"""
        metrics = ExtractionMetrics()
        
        assert metrics.success_rate == 0.0
        assert metrics.average_time_per_record == 0.0
        assert metrics.processing_speed == 0.0


# ============================================================================
# Property 17: Error Categorization
# **Feature: data-collection-optimization, Property 17: Error Categorization**
# **Validates: Requirements 6.4**
# ============================================================================

class TestErrorCategorization:
    """Property 17: 错误分类"""
    
    @given(error_counts=st.dictionaries(
        keys=st.text(min_size=1, max_size=20),
        values=st.integers(min_value=1, max_value=100),
        min_size=1,
        max_size=10
    ))
    @settings(max_examples=100)
    def test_error_categorization_accuracy(self, error_counts):
        """
        *For any* sequence of errors,
        the error categorization SHALL correctly count errors by type.
        **Feature: data-collection-optimization, Property 17: Error Categorization**
        **Validates: Requirements 6.4**
        """
        metrics = PerformanceMetrics()
        
        # 记录错误
        for error_type, count in error_counts.items():
            for _ in range(count):
                metrics.record_error(error_type)
        
        # 验证计数
        current = metrics.get_current_metrics()
        for error_type, expected_count in error_counts.items():
            actual_count = current.errors_by_type.get(error_type, 0)
            assert actual_count == expected_count, \
                f"Error '{error_type}': expected {expected_count}, got {actual_count}"
    
    @given(error_types=st.lists(
        st.text(min_size=1, max_size=10),
        min_size=1,
        max_size=50
    ))
    @settings(max_examples=100)
    def test_error_frequency_statistics(self, error_types):
        """
        *For any* sequence of errors,
        the error frequency statistics SHALL be accurate.
        **Feature: data-collection-optimization, Property 17: Error Categorization**
        **Validates: Requirements 6.4**
        """
        metrics = PerformanceMetrics()
        
        # 计算预期频率
        expected_counts = {}
        for error_type in error_types:
            expected_counts[error_type] = expected_counts.get(error_type, 0) + 1
        
        # 记录错误
        for error_type in error_types:
            metrics.record_error(error_type)
        
        # 验证频率
        current = metrics.get_current_metrics()
        assert current.errors_by_type == expected_counts


# ============================================================================
# 边界情况测试
# ============================================================================

class TestEdgeCases:
    """边界情况测试"""
    
    def test_zero_total_records(self):
        """零记录时成功率应该是0"""
        metrics = ExtractionMetrics(total_records=0)
        assert metrics.success_rate == 0.0
    
    def test_zero_time(self):
        """零时间时处理速度应该是0"""
        metrics = ExtractionMetrics(
            successful_records=10,
            total_time_seconds=0
        )
        assert metrics.processing_speed == 0.0
    
    def test_empty_extraction_times(self):
        """空提取时间列表时平均时间应该是0"""
        metrics = ExtractionMetrics(extraction_times=[])
        assert metrics.average_time_per_record == 0.0
    
    def test_100_percent_success_rate(self):
        """100%成功率"""
        metrics = ExtractionMetrics(
            total_records=100,
            successful_records=100,
            failed_records=0
        )
        assert metrics.success_rate == 1.0
    
    def test_0_percent_success_rate(self):
        """0%成功率"""
        metrics = ExtractionMetrics(
            total_records=100,
            successful_records=0,
            failed_records=100
        )
        assert metrics.success_rate == 0.0
    
    def test_to_dict_contains_all_fields(self):
        """to_dict应该包含所有字段"""
        metrics = ExtractionMetrics(
            total_records=10,
            successful_records=8,
            failed_records=2,
            total_time_seconds=60.0,
            extraction_times=[1.0, 2.0, 3.0],
            errors_by_type={'NetworkError': 2}
        )
        
        data = metrics.to_dict()
        
        assert 'total_records' in data
        assert 'successful_records' in data
        assert 'failed_records' in data
        assert 'total_time_seconds' in data
        assert 'success_rate' in data
        assert 'average_time_per_record' in data
        assert 'processing_speed' in data
        assert 'errors_by_type' in data
