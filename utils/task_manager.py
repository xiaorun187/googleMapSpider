import sys
import threading
from datetime import datetime

class TaskManager:
    """
    任务管理器 - 控制并发和资源清理
    
    Features:
    - 任务队列管理
    - 浏览器实例限制（每任务1个）
    - 资源清理机制
    """
    
    def __init__(self, max_concurrent: int = 1):
        self.max_concurrent = max_concurrent
        self._active_tasks = {}
        self._lock = threading.Lock()
    
    def can_start_task(self) -> bool:
        """检查是否可以启动新任务"""
        with self._lock:
            return len(self._active_tasks) < self.max_concurrent
    
    def register_task(self, task_id: str, thread: threading.Thread, driver=None):
        """注册新任务"""
        with self._lock:
            self._active_tasks[task_id] = {
                'thread': thread,
                'driver': driver,
                'start_time': datetime.now()
            }
    
    def update_driver(self, task_id: str, driver):
        """更新任务的driver实例"""
        with self._lock:
            if task_id in self._active_tasks:
                self._active_tasks[task_id]['driver'] = driver
    
    def unregister_task(self, task_id: str):
        """注销任务"""
        with self._lock:
            if task_id in self._active_tasks:
                del self._active_tasks[task_id]
    
    def get_active_count(self) -> int:
        """获取活跃任务数"""
        with self._lock:
            return len(self._active_tasks)
    
    def terminate_task(self, task_id: str) -> bool:
        """终止指定任务"""
        with self._lock:
            if task_id not in self._active_tasks:
                return False
            
            task_info = self._active_tasks[task_id]
            driver = task_info.get('driver')
            
            try:
                if driver:
                    driver.quit()
                    print(f"任务 {task_id} 的 Selenium driver 已终止", file=sys.stderr)
            except Exception as e:
                print(f"终止任务 {task_id} 的driver失败: {e}", file=sys.stderr)
            
            del self._active_tasks[task_id]
            return True
    
    def terminate_all(self):
        """终止所有任务"""
        with self._lock:
            for task_id in list(self._active_tasks.keys()):
                task_info = self._active_tasks[task_id]
                driver = task_info.get('driver')
                
                try:
                    if driver:
                        driver.quit()
                        print(f"任务 {task_id} 的 Selenium driver 已终止", file=sys.stderr)
                except Exception as e:
                    print(f"终止任务 {task_id} 失败: {e}", file=sys.stderr)
            
            self._active_tasks.clear()
            print("所有任务已清理", file=sys.stderr)
    
    def cleanup_stale_tasks(self, max_age_seconds: int = 3600):
        """清理超时任务（默认1小时）"""
        with self._lock:
            now = datetime.now()
            stale_tasks = []
            
            for task_id, task_info in self._active_tasks.items():
                age = (now - task_info['start_time']).total_seconds()
                if age > max_age_seconds:
                    stale_tasks.append(task_id)
            
            for task_id in stale_tasks:
                self.terminate_task(task_id)
                print(f"清理超时任务: {task_id}", file=sys.stderr)
