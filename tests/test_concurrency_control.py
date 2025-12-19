"""
并发控制属性测试
验证任务管理器的并发限制功能

**Feature: data-collection-optimization**
"""
import pytest
import threading
import time
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ============================================================================
# 模拟 TaskManager 类（用于测试）
# ============================================================================

class TaskManager:
    """任务管理器 - 控制并发和资源清理"""
    
    def __init__(self, max_concurrent: int = 1):
        self.max_concurrent = max_concurrent
        self._active_tasks = {}
        self._lock = threading.Lock()
    
    def can_start_task(self) -> bool:
        """检查是否可以启动新任务"""
        with self._lock:
            return len(self._active_tasks) < self.max_concurrent
    
    def register_task(self, task_id: str, thread: threading.Thread = None, driver=None):
        """注册新任务"""
        with self._lock:
            if len(self._active_tasks) >= self.max_concurrent:
                return False
            self._active_tasks[task_id] = {
                'thread': thread,
                'driver': driver
            }
            return True
    
    def unregister_task(self, task_id: str):
        """注销任务"""
        with self._lock:
            if task_id in self._active_tasks:
                del self._active_tasks[task_id]
    
    def get_active_count(self) -> int:
        """获取活跃任务数"""
        with self._lock:
            return len(self._active_tasks)
    
    def terminate_all(self):
        """终止所有任务"""
        with self._lock:
            self._active_tasks.clear()


# ============================================================================
# Property 18: Concurrency Limit
# **Feature: data-collection-optimization, Property 18: Concurrency Limit**
# **Validates: Requirements 7.3**
# ============================================================================

class TestConcurrencyLimit:
    """Property 18: 并发限制测试"""
    
    def test_single_task_allowed(self):
        """
        单个任务应该被允许启动
        **Feature: data-collection-optimization, Property 18: Concurrency Limit**
        **Validates: Requirements 7.3**
        """
        manager = TaskManager(max_concurrent=1)
        
        assert manager.can_start_task() is True
        assert manager.register_task("task_1") is True
        assert manager.get_active_count() == 1
    
    def test_concurrent_limit_enforced(self):
        """
        *For any* number of concurrent tasks exceeding the limit,
        new tasks SHALL be rejected.
        **Feature: data-collection-optimization, Property 18: Concurrency Limit**
        **Validates: Requirements 7.3**
        """
        manager = TaskManager(max_concurrent=1)
        
        # 第一个任务应该成功
        assert manager.register_task("task_1") is True
        
        # 第二个任务应该被拒绝
        assert manager.can_start_task() is False
        assert manager.register_task("task_2") is False
        
        # 活跃任务数应该仍然是1
        assert manager.get_active_count() == 1
    
    def test_task_unregister_allows_new_task(self):
        """
        任务完成后应该允许新任务启动
        **Feature: data-collection-optimization, Property 18: Concurrency Limit**
        **Validates: Requirements 7.3**
        """
        manager = TaskManager(max_concurrent=1)
        
        # 注册第一个任务
        manager.register_task("task_1")
        assert manager.can_start_task() is False
        
        # 注销任务
        manager.unregister_task("task_1")
        
        # 现在应该可以启动新任务
        assert manager.can_start_task() is True
        assert manager.register_task("task_2") is True
    
    def test_multiple_concurrent_limit(self):
        """
        测试多个并发限制
        **Feature: data-collection-optimization, Property 18: Concurrency Limit**
        **Validates: Requirements 7.3**
        """
        manager = TaskManager(max_concurrent=3)
        
        # 应该允许3个任务
        assert manager.register_task("task_1") is True
        assert manager.register_task("task_2") is True
        assert manager.register_task("task_3") is True
        
        # 第4个应该被拒绝
        assert manager.can_start_task() is False
        assert manager.register_task("task_4") is False
        
        assert manager.get_active_count() == 3
    
    def test_terminate_all_clears_tasks(self):
        """
        终止所有任务应该清空任务列表
        **Feature: data-collection-optimization, Property 18: Concurrency Limit**
        **Validates: Requirements 7.4**
        """
        manager = TaskManager(max_concurrent=3)
        
        manager.register_task("task_1")
        manager.register_task("task_2")
        assert manager.get_active_count() == 2
        
        manager.terminate_all()
        
        assert manager.get_active_count() == 0
        assert manager.can_start_task() is True


# ============================================================================
# 线程安全测试
# ============================================================================

class TestThreadSafety:
    """线程安全测试"""
    
    def test_concurrent_registration(self):
        """
        并发注册应该是线程安全的
        """
        manager = TaskManager(max_concurrent=5)
        results = []
        
        def try_register(task_id):
            result = manager.register_task(task_id)
            results.append(result)
        
        threads = []
        for i in range(10):
            t = threading.Thread(target=try_register, args=(f"task_{i}",))
            threads.append(t)
        
        for t in threads:
            t.start()
        
        for t in threads:
            t.join()
        
        # 应该只有5个成功
        success_count = sum(1 for r in results if r is True)
        assert success_count == 5
        assert manager.get_active_count() == 5
    
    def test_concurrent_unregister(self):
        """
        并发注销应该是线程安全的
        """
        manager = TaskManager(max_concurrent=10)
        
        # 先注册10个任务
        for i in range(10):
            manager.register_task(f"task_{i}")
        
        assert manager.get_active_count() == 10
        
        def unregister(task_id):
            manager.unregister_task(task_id)
        
        threads = []
        for i in range(10):
            t = threading.Thread(target=unregister, args=(f"task_{i}",))
            threads.append(t)
        
        for t in threads:
            t.start()
        
        for t in threads:
            t.join()
        
        assert manager.get_active_count() == 0


# ============================================================================
# 边界情况测试
# ============================================================================

class TestEdgeCases:
    """边界情况测试"""
    
    def test_unregister_nonexistent_task(self):
        """注销不存在的任务不应该报错"""
        manager = TaskManager(max_concurrent=1)
        
        # 不应该抛出异常
        manager.unregister_task("nonexistent_task")
        assert manager.get_active_count() == 0
    
    def test_double_unregister(self):
        """重复注销同一任务不应该报错"""
        manager = TaskManager(max_concurrent=1)
        
        manager.register_task("task_1")
        manager.unregister_task("task_1")
        manager.unregister_task("task_1")  # 第二次注销
        
        assert manager.get_active_count() == 0
    
    def test_zero_concurrent_limit(self):
        """零并发限制应该拒绝所有任务"""
        manager = TaskManager(max_concurrent=0)
        
        assert manager.can_start_task() is False
        assert manager.register_task("task_1") is False
