import sys
import os
import json
from datetime import datetime
import time
from chrome_driver import get_chrome_driver
from scraper import extract_business_info, should_stop_extraction
from db import save_single_business_to_db
from utils import save_to_excel

class ScraperService:
    """
    抓取业务逻辑处理类
    负责处理多城市抓取、统计、进度上报等逻辑
    """
    
    def __init__(self, socket_io, app_context):
        self.socketio = socket_io
        self.app_context = app_context

    def calculate_eta(self, current_count, elapsed_seconds, total_limit):
        """计算预计完成时间"""
        if current_count <= 0 or elapsed_seconds <= 0:
            return "计算中..."
        speed = current_count / elapsed_seconds
        remaining = total_limit - current_count
        if speed > 0:
            eta_seconds = remaining / speed
            if eta_seconds < 60:
                return f"{int(eta_seconds)}秒"
            elif eta_seconds < 3600:
                return f"{int(eta_seconds / 60)}分钟"
            else:
                return f"{int(eta_seconds / 3600)}小时{int((eta_seconds % 3600) / 60)}分钟"
        return "计算中..."

    def emit_progress(self, progress_data):
        """集中处理进度上报"""
        self.socketio.emit('progress_update', progress_data)

    def extract_single_city(self, driver, city, product, limit, remember_position, start_stats, data_callback=None):
        """单个城市的数据抓取逻辑"""
        extracted_data = []
        db_stats = {'inserted': 0, 'updated': 0, 'skipped': 0, 'errors': 0}
        
        # 这里的 business_data 流来自 scraper.extract_business_info
        for progress, current, business_data, message in extract_business_info(driver, None, limit, remember_position, city, product):
            if should_stop_extraction():
                return extracted_data, True
            
            is_recovery = '恢复' in message or 'recover' in message.lower()
            
            if business_data and isinstance(business_data, dict) and 'name' in business_data and 'results' not in business_data:
                # 实时更新全局数据存储
                if data_callback:
                    data_callback(business_data)

                # 实时保存到数据库
                db_result = save_single_business_to_db(business_data)
                
                # 更新统计
                if db_result['success']:
                    db_stats[db_result['action']] += 1
                    extracted_data.append(business_data)
                    
                    # 实时反馈保存状态
                    self.socketio.emit('db_save_status', {
                        'success': True,
                        'action': db_result['action'],
                        'name': business_data.get('name'),
                        'record_id': db_result['record_id'],
                        'stats': db_stats
                    })
                else:
                    db_stats[db_result['action'] if db_result['action'] == 'skipped' else 'errors'] += 1
                    self.socketio.emit('db_save_status', {
                        'success': False,
                        'name': business_data.get('name'),
                        'error': db_result['error'],
                        'stats': db_stats
                    })

            # 上报进度
            self.emit_progress({
                'progress': progress,
                'current': current,
                'business_data': business_data if business_data and 'name' in business_data and 'results' not in business_data else None,
                'message': message,
                'is_recovery': is_recovery,
                'stats': {
                    'extracted_count': start_stats['count'] + len(extracted_data),
                    'speed': f"{ (start_stats['count'] + len(extracted_data)) / (time.time() - start_stats['start_time']):.2f} 条/秒",
                    'eta': self.calculate_eta(start_stats['count'] + len(extracted_data), time.time() - start_stats['start_time'], start_stats['total_limit']),
                    'elapsed': f"{int(time.time() - start_stats['start_time'])}秒"
                }
            })
            
        return extracted_data, False

    def run_extraction(self, config, task_id, task_manager, data_callback=None):
        """执行完整的抓取流程"""
        with self.app_context:
            driver = None
            try:
                driver, proxy_info = get_chrome_driver(config.get('proxy'))
                task_manager.update_driver(task_id, driver)
                self.emit_progress({'progress': 0, 'message': '正在初始化浏览器...' if not proxy_info else proxy_info})

                extracted_data = []
                cities = config.get('cities_list') or [config.get('city')]
                total_limit = config.get('limit')
                start_time = time.time()
                
                for idx, city in enumerate(cities):
                    if should_stop_extraction():
                        break
                    
                    remaining = total_limit - len(extracted_data)
                    if remaining <= 0: break
                    
                    self.emit_progress({
                        'progress': int((idx / len(cities)) * 100),
                        'message': f'正在提取城市 ({idx + 1}/{len(cities)}): {city}'
                    })
                    
                    city_data, stopped = self.extract_single_city(
                        driver, city, config.get('product'), remaining, 
                        config.get('remember_position'),
                        {'start_time': start_time, 'count': len(extracted_data), 'total_limit': total_limit},
                        data_callback
                    )
                    
                    extracted_data.extend(city_data)
                    if stopped: break
                    time.sleep(1)

                # 完成处理
                valid_data = [d for d in extracted_data if isinstance(d, dict) and d.get('name')]
                excel_file = save_to_excel(valid_data) if valid_data else None
                
                self.emit_progress({
                    'progress': 100,
                    'csv_file': excel_file,
                    'message': '提取完成' if not should_stop_extraction() else '已手动停止',
                    'stats': {
                        'extracted_count': len(extracted_data),
                        'elapsed': f"{int(time.time() - start_time)}秒"
                    }
                })

            except Exception as e:
                print(f"[ERROR] Service Execution Error: {e}", file=sys.stderr)
                self.emit_progress({'progress': 100, 'message': f'发生错误: {e}', 'error': True})
            finally:
                if driver: 
                    try: driver.quit()
                    except: pass
                task_manager.unregister_task(task_id)
