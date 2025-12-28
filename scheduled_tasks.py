"""
定时任务管理模块

实现基于 APScheduler 的定时任务调度功能，支持：
- 每天凌晨2点自动触发联系信息提取任务
- 任务配置管理（执行时间、启用状态）
- 任务执行历史记录
- 手动触发任务
"""

import sys
import threading
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from typing import Optional

# 导入数据库操作函数
from db import (
    get_task_config,
    save_task_config,
    create_default_task_config,
    create_execution_record,
    update_execution_record,
    get_execution_history
)


class ScheduledTaskManager:
    """
    定时任务管理器
    
    Features:
    - 使用 APScheduler BackgroundScheduler 实现非阻塞调度
    - 任务配置持久化到数据库
    - 任务执行历史记录
    - 并发控制（同时只运行一个任务）
    - 支持动态重新调度
    """
    
    def __init__(self, app, socketio):
        """
        初始化任务管理器
        
        Args:
            app: Flask 应用实例
            socketio: SocketIO 实例（用于实时推送进度）
        """
        self.app = app
        self.socketio = socketio
        self.scheduler = BackgroundScheduler()
        self.task_lock = threading.Lock()
        self.is_running = False
        self.current_execution_id = None
        
        print("[Scheduler] 任务管理器已初始化", file=sys.stderr)
    
    def initialize(self):
        """
        初始化调度器
        
        - 从数据库加载任务配置
        - 如果配置不存在，创建默认配置
        - 根据配置注册定时任务
        """
        try:
            # 加载任务配置
            config = self.load_config()
            
            if config:
                print(f"[Scheduler] 加载任务配置: {config['task_name']} at {config['schedule_hour']:02d}:{config['schedule_minute']:02d}, enabled={config['enabled']}", file=sys.stderr)
                
                # 如果任务启用，注册定时任务
                if config['enabled']:
                    self.schedule_contact_extraction(
                        config['schedule_hour'],
                        config['schedule_minute'],
                        config['enabled']
                    )
            else:
                print("[Scheduler] 未找到任务配置，创建默认配置", file=sys.stderr)
                # 创建默认配置（每天凌晨2点，启用状态）
                if create_default_task_config():
                    self.schedule_contact_extraction(2, 0, True)
                else:
                    print("[Scheduler ERROR] 创建默认配置失败", file=sys.stderr)
            
            print("[Scheduler] 调度器初始化完成", file=sys.stderr)
            
        except Exception as e:
            print(f"[Scheduler ERROR] 初始化失败: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)
    
    def load_config(self) -> Optional[dict]:
        """
        从数据库加载任务配置
        
        Returns:
            dict: 任务配置，或None
        """
        try:
            config = get_task_config('contact_extraction')
            return config
        except Exception as e:
            print(f"[Scheduler ERROR] 加载配置失败: {e}", file=sys.stderr)
            return None
    
    def schedule_contact_extraction(self, hour: int, minute: int, enabled: bool):
        """
        配置联系信息提取任务
        
        Args:
            hour: 执行小时 (0-23)
            minute: 执行分钟 (0-59)
            enabled: 是否启用
        """
        try:
            # 移除现有任务（如果存在）
            if self.scheduler.get_job('contact_extraction'):
                self.scheduler.remove_job('contact_extraction')
                print("[Scheduler] 移除现有任务", file=sys.stderr)
            
            if not enabled:
                print("[Scheduler] 任务已禁用，不注册定时任务", file=sys.stderr)
                return
            
            # 创建 Cron 触发器（每天指定时间执行）
            trigger = CronTrigger(hour=hour, minute=minute)
            
            # 注册任务
            self.scheduler.add_job(
                func=self.execute_contact_extraction,
                trigger=trigger,
                id='contact_extraction',
                name='联系信息提取任务',
                replace_existing=True
            )
            
            print(f"[Scheduler] 任务已注册: 每天 {hour:02d}:{minute:02d} 执行", file=sys.stderr)
            
        except Exception as e:
            print(f"[Scheduler ERROR] 注册任务失败: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)
    
    def execute_contact_extraction(self):
        """
        执行联系信息提取任务
        
        - 检查是否有任务正在执行（并发控制）
        - 记录任务开始时间
        - 调用现有的联系信息提取逻辑
        - 记录任务完成时间和结果
        - 通过 WebSocket 推送进度更新
        """
        # 并发控制：检查是否有任务正在执行
        if not self.task_lock.acquire(blocking=False):
            print("[Scheduler] 任务正在执行，跳过本次触发", file=sys.stderr)
            return
        
        try:
            self.is_running = True
            start_time = datetime.now()
            start_time_str = start_time.isoformat()
            
            # 创建执行记录
            execution_id = create_execution_record('contact_extraction', start_time_str)
            self.current_execution_id = execution_id
            
            print(f"[Scheduler] 开始执行任务，执行ID: {execution_id}", file=sys.stderr)
            
            # 通过 WebSocket 通知前端任务开始
            with self.app.app_context():
                self.socketio.emit('scheduled_task_start', {
                    'task_name': 'contact_extraction',
                    'execution_id': execution_id,
                    'start_time': start_time_str
                })
            
            # 调用联系信息提取逻辑
            records_processed, records_success, records_failed, error_message = self._run_contact_extraction()
            
            # 计算结束时间
            end_time = datetime.now()
            end_time_str = end_time.isoformat()
            duration = (end_time - start_time).total_seconds()
            
            # 确定任务状态
            status = 'completed' if error_message is None else 'failed'
            
            # 更新执行记录
            update_execution_record(
                execution_id,
                end_time_str,
                status,
                records_processed,
                records_success,
                records_failed,
                error_message
            )
            
            print(f"[Scheduler] 任务完成: 处理={records_processed}, 成功={records_success}, 失败={records_failed}, 耗时={duration:.1f}秒", file=sys.stderr)
            
            # 通过 WebSocket 通知前端任务完成
            with self.app.app_context():
                self.socketio.emit('scheduled_task_complete', {
                    'task_name': 'contact_extraction',
                    'execution_id': execution_id,
                    'status': status,
                    'records_processed': records_processed,
                    'records_success': records_success,
                    'records_failed': records_failed,
                    'duration_seconds': int(duration),
                    'error_message': error_message
                })
            
        except Exception as e:
            print(f"[Scheduler ERROR] 任务执行失败: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)
            
            # 记录失败
            if self.current_execution_id:
                end_time_str = datetime.now().isoformat()
                update_execution_record(
                    self.current_execution_id,
                    end_time_str,
                    'failed',
                    0, 0, 0,
                    str(e)
                )
            
            # 通知前端任务失败
            with self.app.app_context():
                self.socketio.emit('scheduled_task_error', {
                    'task_name': 'contact_extraction',
                    'execution_id': self.current_execution_id,
                    'error': str(e)
                })
        
        finally:
            self.is_running = False
            self.current_execution_id = None
            self.task_lock.release()
    
    def _run_contact_extraction(self) -> tuple:
        """
        运行联系信息提取逻辑
        
        Returns:
            tuple: (records_processed, records_success, records_failed, error_message)
        """
        try:
            from chrome_driver import get_chrome_driver
            from contact_scraper import extract_contact_info
            from db import get_db_connection, release_connection
            
            # 获取有网站但没有邮箱的记录
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, name, website, city, product 
                FROM business_records 
                WHERE website IS NOT NULL AND website != '' 
                AND (email IS NULL OR email = '')
            """)
            records = [
                {'id': r[0], 'name': r[1], 'website': r[2], 'city': r[3], 'product': r[4]} 
                for r in cursor.fetchall()
            ]
            cursor.close()
            release_connection(conn)
            
            if not records:
                print("[Scheduler] 没有需要提取联系方式的记录", file=sys.stderr)
                return 0, 0, 0, None
            
            print(f"[Scheduler] 找到 {len(records)} 条需要提取联系方式的记录", file=sys.stderr)
            
            # 启动浏览器（无头模式）
            driver, proxy_info = get_chrome_driver(proxy=None, headless=True)
            
            records_processed = 0
            records_success = 0
            records_failed = 0
            
            try:
                # 提取联系信息
                for progress, name, data, msg in extract_contact_info(driver, records):
                    records_processed += 1
                    
                    if data and data.get('email'):
                        records_success += 1
                    else:
                        records_failed += 1
                    
                    # 通过 WebSocket 推送进度
                    with self.app.app_context():
                        self.socketio.emit('scheduled_task_progress', {
                            'task_name': 'contact_extraction',
                            'execution_id': self.current_execution_id,
                            'progress': progress,
                            'current': records_processed,
                            'total': len(records),
                            'message': msg
                        })
                
                return records_processed, records_success, records_failed, None
                
            finally:
                if driver:
                    driver.quit()
        
        except Exception as e:
            print(f"[Scheduler ERROR] 提取联系信息失败: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)
            return 0, 0, 0, str(e)
    
    def start(self):
        """启动调度器"""
        try:
            if not self.scheduler.running:
                self.scheduler.start()
                print("[Scheduler] 调度器已启动", file=sys.stderr)
            else:
                print("[Scheduler] 调度器已在运行", file=sys.stderr)
        except Exception as e:
            print(f"[Scheduler ERROR] 启动失败: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)
    
    def shutdown(self):
        """关闭调度器"""
        try:
            if self.scheduler.running:
                self.scheduler.shutdown(wait=False)
                print("[Scheduler] 调度器已关闭", file=sys.stderr)
        except Exception as e:
            print(f"[Scheduler ERROR] 关闭失败: {e}", file=sys.stderr)
    
    def reschedule_task(self, hour: int, minute: int, enabled: bool = True):
        """
        重新调度任务
        
        Args:
            hour: 执行小时 (0-23)
            minute: 执行分钟 (0-59)
            enabled: 是否启用
        """
        try:
            # 保存新配置到数据库
            if save_task_config('contact_extraction', hour, minute, enabled):
                # 重新注册任务
                self.schedule_contact_extraction(hour, minute, enabled)
                print(f"[Scheduler] 任务已重新调度: {hour:02d}:{minute:02d}, enabled={enabled}", file=sys.stderr)
                return True
            else:
                print("[Scheduler ERROR] 保存配置失败", file=sys.stderr)
                return False
        except Exception as e:
            print(f"[Scheduler ERROR] 重新调度失败: {e}", file=sys.stderr)
            return False
    
    def get_next_run_time(self) -> Optional[str]:
        """
        获取下次执行时间
        
        Returns:
            str: 下次执行时间（ISO格式），或None
        """
        try:
            job = self.scheduler.get_job('contact_extraction')
            if job:
                # APScheduler 3.x uses next_run_time attribute
                next_run = getattr(job, 'next_run_time', None)
                if next_run:
                    return next_run.isoformat()
            return None
        except Exception as e:
            print(f"[Scheduler ERROR] 获取下次执行时间失败: {e}", file=sys.stderr)
            return None
    
    def trigger_now(self) -> bool:
        """
        手动触发任务（立即执行）
        
        Returns:
            bool: 是否成功触发
        """
        if self.is_running:
            print("[Scheduler] 任务正在执行，无法手动触发", file=sys.stderr)
            return False
        
        try:
            # 在新线程中执行任务
            thread = threading.Thread(target=self.execute_contact_extraction)
            thread.daemon = True
            thread.start()
            print("[Scheduler] 手动触发任务成功", file=sys.stderr)
            return True
        except Exception as e:
            print(f"[Scheduler ERROR] 手动触发失败: {e}", file=sys.stderr)
            return False
