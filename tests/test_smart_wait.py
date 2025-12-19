"""
SmartWaitStrategy 属性测试
使用 Hypothesis 进行属性测试，验证 SmartWaitStrategy 的正确性

**Feature: data-collection-optimization**
"""
import pytest
from hypothesis import given, strategies as st, settings
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.smart_wait import SmartWaitStrategy


# ============================================================================
# Property 12: Exponential Backoff Calculation
# **Feature: data-collection-optimization, Property 12: Exponential Backoff Calculation**
# **Validates: Requirements 3.3**
# ============================================================================

class TestExponentialBackoffCalculation:
    """Property 12: 指数退避计算"""
    
    @given(attempt=st.integers(min_value=0, max_value=10))
    @settings(max_examples=100)
    def test_backoff_delay_formula(self, attempt):
        """
        *For any* retry attempt number n (starting from 0),
        the calculated backoff delay SHALL equal base_delay * (2^n).
        **Feature: data-collection-optimization, Property 12: Exponential Backoff Calculation**
        **Validates: Requirements 3.3**
        """
        strategy = SmartWaitStrategy()
        base_delay = strategy.BASE_BACKOFF_DELAY  # 0.1 seconds
        
        calculated = strategy.calculate_backoff_delay(attempt)
        expected = base_delay * (2 ** attempt)
        
        assert calculated == expected, \
            f"Backoff delay for attempt {attempt}: expected {expected}, got {calculated}"
    
    @given(
        attempt=st.integers(min_value=0, max_value=10),
        base_delay=st.floats(min_value=0.01, max_value=10.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100)
    def test_backoff_with_custom_base_delay(self, attempt, base_delay):
        """
        *For any* retry attempt and custom base delay,
        the calculated backoff delay SHALL equal base_delay * (2^n).
        **Feature: data-collection-optimization, Property 12: Exponential Backoff Calculation**
        **Validates: Requirements 3.3**
        """
        strategy = SmartWaitStrategy()
        
        calculated = strategy.calculate_backoff_delay(attempt, base_delay)
        expected = base_delay * (2 ** attempt)
        
        assert abs(calculated - expected) < 1e-9, \
            f"Backoff delay with base {base_delay} for attempt {attempt}: expected {expected}, got {calculated}"
    
    @given(attempt=st.integers(min_value=0, max_value=2))
    @settings(max_examples=100)
    def test_backoff_within_max_retries(self, attempt):
        """
        *For any* attempt within max retries (0, 1, 2),
        the backoff delay SHALL be calculated correctly.
        **Feature: data-collection-optimization, Property 12: Exponential Backoff Calculation**
        **Validates: Requirements 3.3**
        """
        strategy = SmartWaitStrategy()
        
        # 验证在最大重试次数内的退避延迟
        assert attempt < strategy.MAX_RETRIES
        
        delay = strategy.calculate_backoff_delay(attempt)
        
        # 验证延迟是正数
        assert delay > 0
        
        # 验证延迟随尝试次数增加
        if attempt > 0:
            prev_delay = strategy.calculate_backoff_delay(attempt - 1)
            assert delay > prev_delay


# ============================================================================
# 指数退避序列测试
# ============================================================================

class TestBackoffSequence:
    """指数退避序列测试"""
    
    def test_default_backoff_sequence(self):
        """测试默认退避序列：0.1s, 0.2s, 0.4s"""
        strategy = SmartWaitStrategy()
        
        delays = [strategy.calculate_backoff_delay(i) for i in range(3)]
        
        assert delays[0] == 0.1  # 100ms
        assert delays[1] == 0.2  # 200ms
        assert delays[2] == 0.4  # 400ms
    
    def test_backoff_doubles_each_attempt(self):
        """每次尝试延迟应该翻倍"""
        strategy = SmartWaitStrategy()
        
        for i in range(5):
            current = strategy.calculate_backoff_delay(i)
            next_delay = strategy.calculate_backoff_delay(i + 1)
            
            assert next_delay == current * 2, \
                f"Delay should double: {current} * 2 != {next_delay}"


# ============================================================================
# 边界情况测试
# ============================================================================

class TestEdgeCases:
    """边界情况测试"""
    
    def test_zero_attempt(self):
        """第0次尝试应该返回基础延迟"""
        strategy = SmartWaitStrategy()
        delay = strategy.calculate_backoff_delay(0)
        assert delay == strategy.BASE_BACKOFF_DELAY
    
    def test_max_retries_constant(self):
        """最大重试次数应该是3"""
        strategy = SmartWaitStrategy()
        assert strategy.MAX_RETRIES == 3
    
    def test_default_timeout(self):
        """默认超时应该是15秒"""
        strategy = SmartWaitStrategy()
        assert strategy.DEFAULT_TIMEOUT == 15
    
    def test_custom_timeout(self):
        """应该支持自定义超时"""
        strategy = SmartWaitStrategy(default_timeout=30)
        assert strategy.default_timeout == 30
    
    def test_network_idle_threshold(self):
        """网络空闲阈值应该是500ms"""
        strategy = SmartWaitStrategy()
        assert strategy.NETWORK_IDLE_THRESHOLD == 0.5
