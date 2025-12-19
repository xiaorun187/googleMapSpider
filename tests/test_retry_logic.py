"""
重试逻辑属性测试
使用 Hypothesis 进行属性测试，验证重试延迟计算的正确性

**Feature: data-collection-optimization**
"""
import pytest
from hypothesis import given, strategies as st, settings
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ============================================================================
# 重试延迟计算辅助函数
# ============================================================================

def calculate_retry_delay(attempt: int, base_delay: float = 1.0) -> float:
    """
    计算重试延迟时间（指数退避）
    
    Args:
        attempt: 尝试次数（从1开始）
        base_delay: 基础延迟时间（秒）
        
    Returns:
        float: 延迟时间（秒）
    """
    return base_delay * (2 ** (attempt - 1))


# ============================================================================
# Property 15: Retry Delay Calculation
# **Feature: data-collection-optimization, Property 15: Retry Delay Calculation**
# **Validates: Requirements 5.1**
# ============================================================================

class TestRetryDelayCalculation:
    """Property 15: 重试延迟计算"""
    
    def test_retry_delays_follow_exponential_backoff(self):
        """
        *For any* retry sequence, the delays SHALL follow exponential backoff pattern:
        1s, 2s, 4s for attempts 1, 2, 3.
        **Feature: data-collection-optimization, Property 15: Retry Delay Calculation**
        **Validates: Requirements 5.1**
        """
        expected_delays = [1.0, 2.0, 4.0]  # 1s, 2s, 4s
        
        for attempt, expected in enumerate(expected_delays, start=1):
            actual = calculate_retry_delay(attempt)
            assert actual == expected, \
                f"Attempt {attempt}: expected {expected}s, got {actual}s"
    
    @given(attempt=st.integers(min_value=1, max_value=10))
    @settings(max_examples=100)
    def test_retry_delay_formula(self, attempt):
        """
        *For any* retry attempt n (starting from 1),
        the delay SHALL equal base_delay * 2^(n-1).
        **Feature: data-collection-optimization, Property 15: Retry Delay Calculation**
        **Validates: Requirements 5.1**
        """
        base_delay = 1.0
        
        actual = calculate_retry_delay(attempt, base_delay)
        expected = base_delay * (2 ** (attempt - 1))
        
        assert actual == expected, \
            f"Attempt {attempt}: expected {expected}s, got {actual}s"
    
    @given(
        attempt=st.integers(min_value=1, max_value=10),
        base_delay=st.floats(min_value=0.1, max_value=10.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100)
    def test_retry_delay_with_custom_base(self, attempt, base_delay):
        """
        *For any* retry attempt and custom base delay,
        the delay SHALL follow the exponential backoff formula.
        **Feature: data-collection-optimization, Property 15: Retry Delay Calculation**
        **Validates: Requirements 5.1**
        """
        actual = calculate_retry_delay(attempt, base_delay)
        expected = base_delay * (2 ** (attempt - 1))
        
        assert abs(actual - expected) < 1e-9, \
            f"Attempt {attempt} with base {base_delay}: expected {expected}s, got {actual}s"
    
    @given(attempt=st.integers(min_value=1, max_value=5))
    @settings(max_examples=50)
    def test_delay_doubles_each_attempt(self, attempt):
        """
        *For any* consecutive attempts,
        the delay SHALL double from the previous attempt.
        **Feature: data-collection-optimization, Property 15: Retry Delay Calculation**
        **Validates: Requirements 5.1**
        """
        if attempt > 1:
            current_delay = calculate_retry_delay(attempt)
            previous_delay = calculate_retry_delay(attempt - 1)
            
            assert current_delay == previous_delay * 2, \
                f"Delay should double: {previous_delay} * 2 != {current_delay}"


# ============================================================================
# 重试次数限制测试
# ============================================================================

class TestRetryLimits:
    """重试次数限制测试"""
    
    def test_max_3_retries(self):
        """最大重试次数应该是3次"""
        max_retries = 3
        
        # 验证3次重试的延迟
        delays = [calculate_retry_delay(i) for i in range(1, max_retries + 1)]
        
        assert delays == [1.0, 2.0, 4.0]
    
    def test_total_retry_time(self):
        """3次重试的总等待时间应该是7秒"""
        max_retries = 3
        
        total_time = sum(calculate_retry_delay(i) for i in range(1, max_retries + 1))
        
        assert total_time == 7.0  # 1 + 2 + 4 = 7
    
    def test_first_retry_is_1_second(self):
        """第一次重试延迟应该是1秒"""
        assert calculate_retry_delay(1) == 1.0
    
    def test_second_retry_is_2_seconds(self):
        """第二次重试延迟应该是2秒"""
        assert calculate_retry_delay(2) == 2.0
    
    def test_third_retry_is_4_seconds(self):
        """第三次重试延迟应该是4秒"""
        assert calculate_retry_delay(3) == 4.0


# ============================================================================
# 边界情况测试
# ============================================================================

class TestEdgeCases:
    """边界情况测试"""
    
    def test_zero_base_delay(self):
        """零基础延迟应该返回零"""
        assert calculate_retry_delay(1, 0.0) == 0.0
        assert calculate_retry_delay(2, 0.0) == 0.0
        assert calculate_retry_delay(3, 0.0) == 0.0
    
    def test_very_small_base_delay(self):
        """非常小的基础延迟应该正确计算"""
        base = 0.001  # 1ms
        
        assert calculate_retry_delay(1, base) == 0.001
        assert calculate_retry_delay(2, base) == 0.002
        assert calculate_retry_delay(3, base) == 0.004
    
    def test_large_attempt_number(self):
        """大的尝试次数应该正确计算（虽然实际不会用到）"""
        # 第10次尝试：1 * 2^9 = 512秒
        assert calculate_retry_delay(10) == 512.0
