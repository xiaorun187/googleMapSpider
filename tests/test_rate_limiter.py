"""
RateLimiter 属性测试
使用 Hypothesis 进行属性测试，验证 RateLimiter 的正确性

**Feature: data-collection-optimization**
"""
import pytest
from hypothesis import given, strategies as st, settings
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.rate_limiter import RateLimiter


# ============================================================================
# Property 19: Rate Limiting Interval
# **Feature: data-collection-optimization, Property 19: Rate Limiting Interval**
# **Validates: Requirements 8.1**
# ============================================================================

class TestRateLimitingInterval:
    """Property 19: 请求限流间隔"""
    
    @given(count=st.integers(min_value=1, max_value=20))
    @settings(max_examples=50)
    def test_randomized_delay_within_bounds(self, count):
        """
        *For any* generated delay,
        it SHALL be within the valid range based on min_interval and randomization factor.
        **Feature: data-collection-optimization, Property 19: Rate Limiting Interval**
        **Validates: Requirements 8.1**
        """
        limiter = RateLimiter()
        
        for _ in range(count):
            delay = limiter.get_randomized_delay()
            
            min_expected = limiter.min_interval * (1 - limiter.randomization_factor)
            max_expected = limiter.min_interval * (1 + limiter.randomization_factor)
            
            assert min_expected <= delay <= max_expected, \
                f"Delay {delay} not in range [{min_expected}, {max_expected}]"
    
    def test_minimum_interval_is_2_seconds(self):
        """最小间隔应该是2秒"""
        limiter = RateLimiter()
        assert limiter.MIN_INTERVAL == 2.0
        assert limiter.min_interval == 2.0


# ============================================================================
# Property 20: User-Agent Rotation
# **Feature: data-collection-optimization, Property 20: User-Agent Rotation**
# **Validates: Requirements 8.3**
# ============================================================================

class TestUserAgentRotation:
    """Property 20: User-Agent 轮换"""
    
    def test_all_user_agents_used_after_10_requests(self):
        """
        *For any* sequence of N requests where N >= 10,
        all 10 User-Agent strings SHALL be used at least once.
        **Feature: data-collection-optimization, Property 20: User-Agent Rotation**
        **Validates: Requirements 8.3**
        """
        limiter = RateLimiter()
        
        # 获取10个User-Agent
        for _ in range(10):
            limiter.get_next_user_agent()
        
        # 验证所有UA都被使用
        assert limiter.all_user_agents_used(), \
            "Not all User-Agents used after 10 requests"
    
    @given(count=st.integers(min_value=10, max_value=50))
    @settings(max_examples=50)
    def test_all_user_agents_used_for_n_requests(self, count):
        """
        *For any* sequence of N requests where N >= 10,
        all 10 User-Agent strings SHALL be used at least once.
        **Feature: data-collection-optimization, Property 20: User-Agent Rotation**
        **Validates: Requirements 8.3**
        """
        limiter = RateLimiter()
        
        for _ in range(count):
            limiter.get_next_user_agent()
        
        assert limiter.all_user_agents_used(), \
            f"Not all User-Agents used after {count} requests"
    
    def test_user_agent_rotation_is_sequential(self):
        """User-Agent应该按顺序轮换"""
        limiter = RateLimiter()
        
        # 获取前10个UA
        uas = [limiter.get_next_user_agent() for _ in range(10)]
        
        # 验证是按顺序获取的
        assert uas == limiter.USER_AGENTS
    
    def test_user_agent_rotation_wraps_around(self):
        """User-Agent轮换应该循环"""
        limiter = RateLimiter()
        
        # 获取11个UA
        uas = [limiter.get_next_user_agent() for _ in range(11)]
        
        # 第11个应该和第1个相同
        assert uas[10] == uas[0]
    
    def test_exactly_10_user_agents(self):
        """应该有正好10个User-Agent"""
        limiter = RateLimiter()
        assert len(limiter.USER_AGENTS) == 10


# ============================================================================
# Property 21: Wait Time Randomization
# **Feature: data-collection-optimization, Property 21: Wait Time Randomization**
# **Validates: Requirements 8.4**
# ============================================================================

class TestWaitTimeRandomization:
    """Property 21: 等待时间随机化"""
    
    @given(count=st.integers(min_value=10, max_value=100))
    @settings(max_examples=50)
    def test_randomized_delays_within_30_percent(self, count):
        """
        *For any* generated wait time,
        it SHALL be within ±30% of the base interval.
        **Feature: data-collection-optimization, Property 21: Wait Time Randomization**
        **Validates: Requirements 8.4**
        """
        limiter = RateLimiter()
        base = limiter.min_interval
        
        for _ in range(count):
            delay = limiter.get_randomized_delay()
            
            min_allowed = base * 0.7  # -30%
            max_allowed = base * 1.3  # +30%
            
            assert min_allowed <= delay <= max_allowed, \
                f"Delay {delay} not within ±30% of base {base}"
    
    def test_randomization_factor_is_30_percent(self):
        """随机化因子应该是30%"""
        limiter = RateLimiter()
        assert limiter.RANDOMIZATION_FACTOR == 0.3
    
    @given(count=st.integers(min_value=50, max_value=100))
    @settings(max_examples=20)
    def test_delays_are_actually_randomized(self, count):
        """延迟应该是随机的（不是固定值）"""
        limiter = RateLimiter()
        
        delays = [limiter.get_randomized_delay() for _ in range(count)]
        unique_delays = set(delays)
        
        # 应该有多个不同的延迟值
        assert len(unique_delays) > 1, \
            "Delays are not randomized - all values are the same"


# ============================================================================
# 连续封禁检测测试
# ============================================================================

class TestConsecutiveBlockDetection:
    """连续封禁检测测试"""
    
    def test_pause_after_3_consecutive_blocks(self):
        """3次连续封禁后应该暂停"""
        limiter = RateLimiter()
        
        # 前两次不应该触发暂停
        assert not limiter.record_block()
        assert not limiter.record_block()
        
        # 第三次应该触发暂停
        assert limiter.record_block()
    
    def test_success_resets_block_count(self):
        """成功请求应该重置封禁计数"""
        limiter = RateLimiter()
        
        limiter.record_block()
        limiter.record_block()
        assert limiter.get_consecutive_blocks() == 2
        
        limiter.record_success()
        assert limiter.get_consecutive_blocks() == 0
    
    def test_max_consecutive_blocks_is_3(self):
        """最大连续封禁次数应该是3"""
        limiter = RateLimiter()
        assert limiter.MAX_CONSECUTIVE_BLOCKS == 3


# ============================================================================
# 边界情况测试
# ============================================================================

class TestEdgeCases:
    """边界情况测试"""
    
    def test_custom_min_interval(self):
        """应该支持自定义最小间隔"""
        limiter = RateLimiter(min_interval=5.0)
        assert limiter.min_interval == 5.0
    
    def test_custom_randomization_factor(self):
        """应该支持自定义随机化因子"""
        limiter = RateLimiter(randomization_factor=0.5)
        assert limiter.randomization_factor == 0.5
    
    def test_reset_clears_state(self):
        """reset应该清除所有状态"""
        limiter = RateLimiter()
        
        # 使用一些功能
        for _ in range(5):
            limiter.get_next_user_agent()
        limiter.record_block()
        
        # 重置
        limiter.reset()
        
        assert limiter.get_consecutive_blocks() == 0
        assert limiter.get_total_requests() == 0
        assert not limiter.all_user_agents_used()
    
    def test_block_pause_duration_is_60_seconds(self):
        """封禁暂停时间应该是60秒"""
        limiter = RateLimiter()
        assert limiter.BLOCK_PAUSE_DURATION == 60.0
