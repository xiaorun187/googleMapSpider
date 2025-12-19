"""
RateLimiter - 请求限流器
控制请求频率以避免被目标网站封禁
"""
import time
import random
from typing import List


class RateLimiter:
    """
    请求限流器，控制请求频率
    
    Features:
    - 最小2秒请求间隔控制
    - ±30% 随机化延迟
    - 10 个 User-Agent 轮换
    - 连续封禁检测（3次触发暂停）
    """
    
    MIN_INTERVAL: float = 2.0  # 最小间隔2秒
    RANDOMIZATION_FACTOR: float = 0.3  # ±30%随机化
    BLOCK_PAUSE_DURATION: float = 60.0  # 封禁暂停60秒
    MAX_CONSECUTIVE_BLOCKS: int = 3  # 最大连续封禁次数
    
    # 10个常用浏览器User-Agent
    USER_AGENTS: List[str] = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
        "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0"
    ]
    
    def __init__(
        self, 
        min_interval: float = None,
        randomization_factor: float = None
    ):
        """
        初始化请求限流器
        
        Args:
            min_interval: 最小请求间隔（秒）
            randomization_factor: 随机化因子
        """
        self.min_interval = min_interval or self.MIN_INTERVAL
        self.randomization_factor = randomization_factor or self.RANDOMIZATION_FACTOR
        self._last_request_time: float = 0
        self._ua_index: int = 0
        self._consecutive_blocks: int = 0
        self._total_requests: int = 0
        self._ua_usage_count: dict = {i: 0 for i in range(len(self.USER_AGENTS))}
    
    def wait_if_needed(self) -> float:
        """
        如果需要则等待，返回实际等待时间
        
        Returns:
            float: 实际等待时间（秒）
        """
        current_time = time.time()
        elapsed = current_time - self._last_request_time
        
        # 计算需要等待的时间
        delay = self.get_randomized_delay()
        wait_time = max(0, delay - elapsed)
        
        if wait_time > 0:
            time.sleep(wait_time)
        
        self._last_request_time = time.time()
        self._total_requests += 1
        
        return wait_time
    
    def get_randomized_delay(self) -> float:
        """
        获取随机化的延迟时间
        
        Returns:
            float: 随机化后的延迟时间（秒）
        """
        # 在 ±30% 范围内随机化
        min_delay = self.min_interval * (1 - self.randomization_factor)
        max_delay = self.min_interval * (1 + self.randomization_factor)
        
        return random.uniform(min_delay, max_delay)
    
    def get_next_user_agent(self) -> str:
        """
        获取下一个User-Agent（轮换）
        
        Returns:
            str: User-Agent字符串
        """
        ua = self.USER_AGENTS[self._ua_index]
        self._ua_usage_count[self._ua_index] += 1
        self._ua_index = (self._ua_index + 1) % len(self.USER_AGENTS)
        return ua
    
    def get_random_user_agent(self) -> str:
        """
        获取随机User-Agent
        
        Returns:
            str: User-Agent字符串
        """
        return random.choice(self.USER_AGENTS)
    
    def record_block(self) -> bool:
        """
        记录被封禁，返回是否应该暂停
        
        Returns:
            bool: 是否应该暂停（连续3次封禁）
        """
        self._consecutive_blocks += 1
        
        if self._consecutive_blocks >= self.MAX_CONSECUTIVE_BLOCKS:
            return True
        
        return False
    
    def record_success(self) -> None:
        """记录成功请求，重置连续封禁计数"""
        self._consecutive_blocks = 0
    
    def pause_for_block(self) -> None:
        """因封禁暂停"""
        time.sleep(self.BLOCK_PAUSE_DURATION)
        self._consecutive_blocks = 0
    
    def get_consecutive_blocks(self) -> int:
        """
        获取连续封禁次数
        
        Returns:
            int: 连续封禁次数
        """
        return self._consecutive_blocks
    
    def get_total_requests(self) -> int:
        """
        获取总请求次数
        
        Returns:
            int: 总请求次数
        """
        return self._total_requests
    
    def get_ua_usage_stats(self) -> dict:
        """
        获取User-Agent使用统计
        
        Returns:
            dict: 每个UA的使用次数
        """
        return self._ua_usage_count.copy()
    
    def all_user_agents_used(self) -> bool:
        """
        检查是否所有User-Agent都已使用
        
        Returns:
            bool: 是否所有UA都已使用至少一次
        """
        return all(count > 0 for count in self._ua_usage_count.values())
    
    def reset(self) -> None:
        """重置限流器状态"""
        self._last_request_time = 0
        self._ua_index = 0
        self._consecutive_blocks = 0
        self._total_requests = 0
        self._ua_usage_count = {i: 0 for i in range(len(self.USER_AGENTS))}
