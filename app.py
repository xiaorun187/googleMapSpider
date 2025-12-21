# from gevent import monkey
# monkey.patch_all()

import json
import sys
import io
import os
import threading
from queue import Queue
from datetime import datetime
import requests
import pandas as pd
from flask import Flask, jsonify, request, render_template, session, redirect, url_for, send_file, make_response
from flask_socketio import SocketIO
from config import SECRET_KEY, CORS_ALLOWED_ORIGINS, OUTPUT_DIR, PASSWORD
from chrome_driver import get_chrome_driver
from facebook_email_fetcher import scraper_facebook_email
from scraper import extract_business_info
from contact_scraper import extract_contact_info
from utils import save_to_csv, save_to_excel
from email_sender import EmailSender
from db import save_business_data_to_db, save_single_business_to_db, get_history_records, update_send_count
from services.user_service import UserService

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

app = Flask(__name__)
app.secret_key = SECRET_KEY
# 使用 threading 模式，避免 gevent-websocket 配置问题
socketio = SocketIO(app, cors_allowed_origins=CORS_ALLOWED_ORIGINS, async_mode='threading')

# 存储提取的商家数据
business_data_store = []

# ============================================================================
# 并发控制 (Requirements 7.3, 7.4)
# ============================================================================
# 全局任务管理器：存储线程和 driver 实例
running_tasks = {}

# 任务队列和并发限制
MAX_CONCURRENT_TASKS = 1  # 每任务限制1个浏览器实例
task_queue = Queue()
task_semaphore = threading.Semaphore(MAX_CONCURRENT_TASKS)
task_lock = threading.Lock()


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
        self._semaphore = threading.Semaphore(max_concurrent)
    
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


# 全局任务管理器实例
task_manager = TaskManager(max_concurrent=MAX_CONCURRENT_TASKS)

def terminate_all_tasks():
    """终止所有正在运行的任务和 driver 实例"""
    task_manager.terminate_all()

@app.route('/')
def index():
    return redirect(url_for('login'))


# 初始化用户服务
user_service = UserService()


@app.route('/register', methods=['GET', 'POST'])
def register():
    """用户注册路由"""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        # 检查密码确认
        if password != confirm_password:
            return render_template('register.html', error="两次输入的密码不一致", username=username)
        
        # 调用用户服务进行注册
        success, message = user_service.register_user(username, password)
        
        if success:
            # 注册成功后跳转到登录页面，并显示成功消息
            return redirect(url_for('login', registered=1))
        else:
            return render_template('register.html', error=message, username=username)
    
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    """用户登录路由"""
    # 检查是否是注册成功后跳转过来的
    registered = request.args.get('registered')
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        # 调用用户服务进行认证
        auth_result = user_service.authenticate(username, password)
        
        if auth_result.success:
            session['logged_in'] = True
            session['user_id'] = auth_result.user_id
            session['username'] = auth_result.username
            return redirect(url_for('operation'))
        else:
            return render_template('login.html', error=auth_result.error_message)
    
    # 如果是注册成功跳转过来，显示成功消息
    if registered:
        return render_template('login.html', success="注册成功！请登录")
    
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))


@app.route('/operation')
def operation():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return render_template('operation.html')

@app.route('/download/<filename>')
def download_file(filename):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    filepath = os.path.join(OUTPUT_DIR, filename)
    if not os.path.exists(filepath):
        return "文件不存在", 404
    return send_file(filepath, as_attachment=True, download_name=filename)

@app.route('/start_extraction', methods=['POST'])
def start_extraction():
    if not session.get('logged_in'):
        return jsonify({"status": "error", "message": "请先登录"}), 401

    # 支持新的城市+商品模式，以及国家级别爬取
    country = request.form.get('country')  # 国家代码
    city = request.form.get('city')
    product = request.form.get('product')
    url = request.form.get('url')  # 保留旧的URL模式兼容
    limit = request.form.get('limit')
    proxy = request.form.get('proxy')
    remember_position = request.form.get('remember_position') == 'on'  # 获取复选框状态
    
    # 调试日志
    print(f"[DEBUG] 收到提取请求 - country: {country}, city: {city}, product: {product}, URL: {url}, limit: {limit}, proxy: {proxy}, remember_position: {remember_position}", file=sys.stderr)

    # 处理 limit 参数：为空或无效时设置为不限制（使用一个很大的数）
    UNLIMITED = 999999  # 不限制时的默认值
    try:
        if limit is None or limit == '' or limit.strip() == '':
            limit = UNLIMITED
            print(f"[DEBUG] limit 为空，设置为不限制 ({UNLIMITED})", file=sys.stderr)
        else:
            limit = int(limit)
            if limit <= 0:
                return jsonify({"status": "error", "message": "limit 必须大于 0"}), 400
    except (ValueError, TypeError):
        # 如果转换失败，设置为不限制
        limit = UNLIMITED
        print(f"[DEBUG] limit 转换失败，设置为不限制 ({UNLIMITED})", file=sys.stderr)

    # 验证：必须有商品，且必须有城市或国家
    if not product:
        return jsonify({"status": "error", "message": "请输入商品/服务名称"}), 400
    if not url and not city and not country:
        return jsonify({"status": "error", "message": "请选择国家或输入城市名称"}), 400

    terminate_all_tasks()
    
    # 重置停止标志
    from scraper import reset_stop_flag
    reset_stop_flag()
    
    socketio.emit('progress_update', {'progress': 0, 'message': '正在清理旧任务...'})

    # 检查并发限制
    if not task_manager.can_start_task():
        return jsonify({
            "status": "error", 
            "message": f"已达到最大并发任务数 ({MAX_CONCURRENT_TASKS})，请等待当前任务完成"
        }), 429

    task_id = f"extract_{os.urandom(4).hex()}"
    
    # 获取国家的城市列表（如果没有指定城市但指定了国家）
    cities_to_scrape = []
    if not city and country:
        try:
            config_path = os.path.join(os.path.dirname(__file__), 'config', 'countries.json')
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    country_data = json.load(f)
                    if country in country_data:
                        cities_to_scrape = country_data[country].get('cities', [])
                        print(f"[DEBUG] 将按顺序爬取 {country} 的 {len(cities_to_scrape)} 个城市", file=sys.stderr)
        except Exception as e:
            print(f"[ERROR] 加载国家城市数据失败: {e}", file=sys.stderr)

    def background_extraction(city, product, url, limit, proxy=None, task_id=task_id, remember_position=False, cities_list=None):
        driver = None
        start_time = datetime.now()
        extracted_count = 0
        last_update_time = start_time
        
        def calculate_eta(current_count, elapsed_seconds, total_limit):
            """计算预计完成时间"""
            if current_count <= 0 or elapsed_seconds <= 0:
                return "计算中..."
            speed = current_count / elapsed_seconds  # 条/秒
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
        
        def emit_progress_with_stats(progress, current, business_data, message, is_recovery=False, total_limit=limit):
            """发送带统计信息的进度更新"""
            nonlocal extracted_count, last_update_time
            
            elapsed = (datetime.now() - start_time).total_seconds()
            speed = extracted_count / elapsed if elapsed > 0 else 0
            eta = calculate_eta(extracted_count, elapsed, total_limit)
            
            update_data = {
                'progress': progress,
                'current': current,
                'business_data': business_data,
                'message': message,
                'stats': {
                    'extracted_count': extracted_count,
                    'speed': f"{speed:.2f} 条/秒",
                    'eta': eta,
                    'elapsed': f"{int(elapsed)}秒"
                }
            }
            
            if is_recovery:
                update_data['recovery_status'] = 'recovered'
                update_data['message'] = f"[恢复] {message}"
            
            socketio.emit('progress_update', update_data)
            last_update_time = datetime.now()
        
        def extract_single_city(driver, current_city, product, limit_per_city, extracted_data, is_recovery):
            """提取单个城市的数据，实时保存到数据库"""
            nonlocal extracted_count
            
            from scraper import should_stop_extraction
            
            # 统计信息
            db_stats = {'inserted': 0, 'updated': 0, 'skipped': 0, 'errors': 0}
            
            for progress, current, business_data, message in extract_business_info(driver, url, limit_per_city, remember_position, current_city, product):
                # 检查停止标志
                if should_stop_extraction():
                    print(f"[DB STATS] 城市 {current_city} 停止时统计: 插入={db_stats['inserted']}, 更新={db_stats['updated']}, 跳过={db_stats['skipped']}, 错误={db_stats['errors']}", file=sys.stderr)
                    return extracted_data, True  # 返回数据和停止标志
                
                if business_data:
                    # 检查是否是最终结果（包含 results 和 validation 的字典）
                    if isinstance(business_data, dict) and 'results' in business_data:
                        # 这是最终汇总结果，不需要再保存（已经实时保存过了）
                        print(f"[DEBUG] 收到最终汇总结果，跳过（数据已实时保存）", file=sys.stderr)
                    elif isinstance(business_data, dict) and 'name' in business_data:
                        # 这是单个商家数据 - 实时保存到数据库
                        db_result = save_single_business_to_db(business_data)
                        
                        if db_result['success']:
                            if db_result['action'] == 'inserted':
                                db_stats['inserted'] += 1
                            elif db_result['action'] == 'updated':
                                db_stats['updated'] += 1
                            
                            # 只有成功保存的数据才添加到内存列表
                            extracted_data.append(business_data)
                            extracted_count = len(extracted_data)
                            
                            # 发送保存成功通知
                            socketio.emit('db_save_status', {
                                'success': True,
                                'action': db_result['action'],
                                'name': business_data.get('name'),
                                'record_id': db_result['record_id'],
                                'stats': db_stats
                            })
                        else:
                            if db_result['action'] == 'skipped':
                                db_stats['skipped'] += 1
                            else:
                                db_stats['errors'] += 1
                            
                            # 发送保存失败通知
                            socketio.emit('db_save_status', {
                                'success': False,
                                'action': db_result['action'],
                                'name': business_data.get('name'),
                                'error': db_result['error'],
                                'stats': db_stats
                            })
                            print(f"[WARNING] 保存失败 [{business_data.get('name')}]: {db_result['error']}", file=sys.stderr)
                
                # 检测是否是恢复状态
                if '恢复' in message or 'recover' in message.lower():
                    is_recovery = True
                    socketio.emit('recovery_status', {
                        'status': 'recovering',
                        'message': message
                    })
                
                # 只发送单个商家数据到前端，不发送最终汇总结果
                emit_business_data = None
                if business_data and isinstance(business_data, dict) and 'name' in business_data and 'results' not in business_data:
                    emit_business_data = business_data
                
                emit_progress_with_stats(progress, current, emit_business_data, message, is_recovery)
                
                # 恢复完成后重置标志
                if is_recovery and progress > 10:
                    is_recovery = False
            
            # 打印城市完成统计
            print(f"[DB STATS] 城市 {current_city} 完成统计: 插入={db_stats['inserted']}, 更新={db_stats['updated']}, 跳过={db_stats['skipped']}, 错误={db_stats['errors']}", file=sys.stderr)
            
            return extracted_data, False
        
        with app.app_context():
            try:
                driver, proxy_info = get_chrome_driver(proxy)
                task_manager.update_driver(task_id, driver)
                socketio.emit('progress_update', {'progress': 0, 'message': '正在初始化浏览器...' if not proxy_info else proxy_info})

                extracted_data = []
                is_recovery = False
                stopped = False
                
                # 如果有城市列表，按顺序爬取每个城市
                if cities_list and len(cities_list) > 0:
                    total_cities = len(cities_list)
                    limit_per_city = limit  # 每个城市的限制数量
                    
                    socketio.emit('progress_update', {
                        'progress': 0, 
                        'message': f'准备爬取 {total_cities} 个城市，每个城市 {limit_per_city} 条数据'
                    })
                    
                    for city_idx, current_city in enumerate(cities_list):
                        # 检查停止标志
                        from scraper import should_stop_extraction
                        if should_stop_extraction():
                            stopped = True
                            break
                        
                        city_progress = int((city_idx / total_cities) * 100)
                        socketio.emit('progress_update', {
                            'progress': city_progress,
                            'message': f'正在爬取城市 ({city_idx + 1}/{total_cities}): {current_city}'
                        })
                        
                        extracted_data, stopped = extract_single_city(
                            driver, current_city, product, limit_per_city, extracted_data, is_recovery
                        )
                        
                        if stopped:
                            break
                        
                        # 城市间短暂休息，避免被封
                        import time
                        time.sleep(2)
                    
                    if stopped:
                        socketio.emit('progress_update', {
                            'progress': 100,
                            'message': f'爬取已停止，已提取 {len(extracted_data)} 条数据'
                        })
                else:
                    # 单城市爬取（原有逻辑）
                    extracted_data, stopped = extract_single_city(
                        driver, city, product, limit, extracted_data, is_recovery
                    )

                if extracted_data:
                    global business_data_store
                    business_data_store = extracted_data
                    
                    # 过滤有效的商家数据（必须有 name 字段）
                    valid_data = [d for d in extracted_data if isinstance(d, dict) and d.get('name')]
                    print(f"[DEBUG] 数据汇总: 原始 {len(extracted_data)} 条, 有效 {len(valid_data)} 条", file=sys.stderr)
                    
                    # 生成 Excel 文件（数据已在抓取过程中实时保存到数据库）
                    csv_filename = save_to_excel(valid_data)
                    print(f"[INFO] 数据已实时保存到数据库，Excel 文件已生成: {csv_filename}", file=sys.stderr)
                    
                    elapsed = (datetime.now() - start_time).total_seconds()
                    final_speed = len(extracted_data) / elapsed if elapsed > 0 else 0
                    
                    socketio.emit('progress_update', {
                        'progress': 100,
                        'csv_file': csv_filename,
                        'message': '数据提取完成' if not stopped else '爬取已停止，数据已保存',
                        'data': extracted_data,
                        'stats': {
                            'extracted_count': len(extracted_data),
                            'speed': f"{final_speed:.2f} 条/秒",
                            'total_time': f"{int(elapsed)}秒"
                        }
                    })
                else:
                    socketio.emit('progress_update', {
                        'progress': 100,
                        'message': '未提取到任何数据'
                    })
            except Exception as e:
                print(f"后台任务 {task_id} 发生异常: {e}", file=sys.stderr)
                
                # 发送错误恢复状态通知
                socketio.emit('error_notification', {
                    'task_id': task_id,
                    'error_type': type(e).__name__,
                    'error_message': str(e),
                    'recovery_hint': '进度已自动保存，下次启动时可从断点恢复',
                    'extracted_count': extracted_count
                })
                
                socketio.emit('progress_update', {
                    'progress': 100,
                    'message': f'后台任务出错: {e}',
                    'error': True,
                    'recovery_available': True
                })
            finally:
                if driver:
                    try:
                        driver.quit()
                    except Exception as e:
                        print(f"关闭driver失败: {e}", file=sys.stderr)
                task_manager.unregister_task(task_id)

    thread = threading.Thread(target=background_extraction, args=(city, product, url, limit, proxy, task_id, remember_position, cities_to_scrape))
    thread.daemon = True
    
    # 注册任务
    task_manager.register_task(task_id, thread)
    thread.start()

    return jsonify({"status": "success", "message": "任务已启动，正在提取数据...", "task_id": task_id})


@app.route('/stop_extraction', methods=['POST'])
def stop_extraction():
    """停止当前爬取任务"""
    if not session.get('logged_in'):
        return jsonify({"status": "error", "message": "请先登录"}), 401
    
    try:
        # 导入并设置停止标志
        from scraper import set_stop_extraction
        set_stop_extraction(True)
        
        # 通知前端
        socketio.emit('progress_update', {
            'progress': 100,
            'message': '正在停止爬取任务...',
            'stopping': True
        })
        
        return jsonify({
            "status": "success", 
            "message": "停止信号已发送，爬取将在当前商家处理完成后停止"
        })
    except Exception as e:
        print(f"停止爬取失败: {e}", file=sys.stderr)
        return jsonify({"status": "error", "message": f"停止爬取失败: {e}"}), 500


@app.route('/api/task_status', methods=['GET'])
def get_task_status():
    """获取当前任务状态"""
    if not session.get('logged_in'):
        return jsonify({"status": "error", "message": "请先登录"}), 401
    
    is_running = task_manager.get_active_count() > 0
    return jsonify({
        "status": "success",
        "is_running": is_running,
        "active_count": task_manager.get_active_count()
    })


@app.route('/extract_contacts', methods=['POST'])
def extract_contacts():
    if not session.get('logged_in'):
        return jsonify({"status": "error", "message": "请先登录"}), 401

    proxy = request.form.get('proxy')

    def background_contact_extraction(proxy=None):
        driver = None
        with app.app_context():
            try:
                if not business_data_store:
                    socketio.emit('contact_update', {
                        'progress': 100,
                        'message': '没有可用的商家数据，请先执行提取任务'
                    })
                    return

                driver, proxy_info = get_chrome_driver(proxy)
                socketio.emit('contact_update',
                              {'progress': 0, 'message': '正在初始化浏览器...' if not proxy_info else proxy_info})

                for i, name, business_data, message in extract_contact_info(driver, business_data_store):
                    socketio.emit('contact_update', {
                        'progress': int((i + 1) / len(business_data_store) * 100),
                        'name': name,
                        'business_data': business_data,
                        'message': message
                    })

                # 联系方式提取完成后保存到 Excel
                csv_filename = save_to_excel(business_data_store)
                socketio.emit('contact_update', {
                    'progress': 100,
                    'csv_file': csv_filename,
                    'message': '联系方式提取完成',
                    'data': business_data_store  # 返回完整数据，确保界面与Excel一致
                })

                # 注意：由于在contact_scraper.py中已经实时保存到数据库，这里不再重复保存
                # 保留此注释是为了说明数据已经在提取过程中实时保存了
                print("[INFO] 联系方式提取完成，数据已在提取过程中实时保存到数据库", file=sys.stderr)

            except Exception as e:
                print(f"联系方式提取任务发生异常: {e}", file=sys.stderr)
                socketio.emit('contact_update', {
                    'progress': 100,
                    'message': f'联系方式提取出错: {e}'
                })
            finally:
                if driver:
                    driver.quit()

    def background_contact_extraction(proxy=None):
        with app.app_context():
            from chrome_driver import get_chrome_driver as create_driver
            driver, proxy_info = create_driver(proxy=proxy, headless=True)
            try:
                # 获取有网站但没邮箱的记录
                from db import get_db_connection, release_connection
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT id, name, website, city, product FROM business_records WHERE website IS NOT NULL AND website != '' AND (email IS NULL OR email = '')")
                records = [{'id': r[0], 'name': r[1], 'website': r[2], 'city': r[3], 'product': r[4]} for r in cursor.fetchall()]
                cursor.close()
                release_connection(conn)
                
                if not records:
                    socketio.emit('progress_update', {'progress': 100, 'message': '没有需要提取联系方式的记录'})
                    return

                for progress, name, data, msg in extract_contact_info(driver, records):
                    socketio.emit('progress_update', {
                        'progress': progress,
                        'message': msg,
                        'business_data': data
                    })
            finally:
                driver.quit()

    thread = threading.Thread(target=background_contact_extraction, args=(proxy,))
    thread.daemon = True
    thread.start()

    return jsonify({"status": "success", "message": "联系方式提取任务已启动..."})

def background_target_contact_extraction(record_ids, proxy=None):
    """后台定向联系方式提取"""
    with app.app_context():
        from chrome_driver import get_chrome_driver as create_driver
        driver, proxy_info = create_driver(proxy=proxy, headless=True)
        try:
            from contact_scraper import extract_contacts_by_ids
            for progress, name, data, msg in extract_contacts_by_ids(driver, record_ids):
                socketio.emit('progress_update', {
                    'progress': progress,
                    'message': msg,
                    'business_data': data
                })
            socketio.emit('progress_update', {'progress': 100, 'message': '定向提取任务已完成'})
        finally:
            driver.quit()

@app.route('/email')
@app.route('/send_email_page')
def send_email_page():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return render_template('send_email.html')



@app.route('/send_email', methods=['POST'])
def send_email_route():
    if not session.get('logged_in'):
        return jsonify({"status": "error", "message": "Please log in"}), 401

    data = request.get_json()
    recipient = data.get('recipient')
    subject = data.get('subject')
    body = data.get('body')
    attach_file = data.get('attach_file')

    if not recipient or not subject or not body:
        return jsonify({"status": "error", "message": "Missing required fields"}), 400

    success, message = EmailSender().send_email(recipient, subject, body, attach_file)
    if success:
        return jsonify({"status": "success", "message": message})
    else:
        return jsonify({"status": "error", "message": message})

# 可选：保留此接口供手动保存，但在此场景下无需前端调用
@app.route('/save_business_data', methods=['POST'])
def save_business_data():
    if not session.get('logged_in'):
        return jsonify({"status": "error", "message": "请先登录"}), 401

    data = request.get_json()
    business_data = data.get('business_data', [])

    if not business_data:
        return jsonify({"status": "error", "message": "商家数据为空"}), 400

    try:
        save_business_data_to_db(business_data)
        return jsonify({"status": "success", "message": "商家数据保存成功"})
    except Exception as e:
        print(f"保存商家数据失败: {e}", file=sys.stderr)
        return jsonify({"status": "error", "message": f"保存商家数据失败: {e}"}), 500
# 新增历史记录页面路由
@app.route('/history')
def history():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return render_template('history.html')

# 新增历史记录查询接口
@app.route('/get_history', methods=['GET'])
def get_history():
    if not session.get('logged_in'):
        return jsonify({"status": "error", "message": "请先登录"}), 401

    page = int(request.args.get('page', 1))
    size = int(request.args.get('size', 10))
    query = request.args.get('query', '')
    show_empty_email = request.args.get('show_empty_email', 'false').lower() == 'true'  # 获取筛选参数，默认为 false
    print(f"[DEBUG] get_history params: page={page}, size={size}, query='{query}', show_empty_email={show_empty_email}", file=sys.stderr)
    try:
        result = get_history_records(page, size, query, show_empty_email)
        return jsonify({
            "status": "success",
            "records": result['records'],
            "total_pages": result['total_pages'],
            "total": result['total']
        })
    except Exception as e:
        print(f"查询历史记录失败: {e}", file=sys.stderr)
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/records/target-extract', methods=['POST'])
def target_extract_contacts():
    """定向对选中的记录提取联系人"""
    if not session.get('logged_in'):
        return jsonify({"status": "error", "message": "请先登录"}), 401
    
    data = request.get_json()
    record_ids = data.get('ids', [])
    proxy = data.get('proxy', None)
    if not record_ids:
        return jsonify({"status": "error", "message": "没有选中的记录"}), 400

    # 启动后台线程进行定向爬取
    thread = threading.Thread(target=background_target_contact_extraction, args=(record_ids, proxy))
    thread.daemon = True
    thread.start()
    
    return jsonify({"status": "success", "message": f"已针对 {len(record_ids)} 条记录启动定向提取任务"})

# 在路由部分添加
@app.route('/update_send_count', methods=['POST'])
def update_send_count_route():
    if not session.get('logged_in'):
        return jsonify({"status": "error", "message": "请先登录"}), 401

    data = request.get_json()
    emails = data.get('emails', [])

    if not emails:
        return jsonify({"status": "error", "message": "No emails provided"}), 400

    try:
        update_send_count(emails)
        return jsonify({"status": "success", "message": "Send counts updated successfully"})
    except Exception as e:
        print(f"更新发送次数失败: {e}", file=sys.stderr)
        return jsonify({"status": "error", "message": f"Failed to update send counts: {e}"}), 500


@app.route('/export_excel', methods=['GET'])
def export_excel():
    if not session.get('logged_in'):
        return jsonify({"status": "error", "message": "请先登录"}), 401

    query = request.args.get('query', '')
    show_empty_email = request.args.get('show_empty_email', 'false').lower() == 'true'
    columns = request.args.get('columns', '[]')

    try:
        # 解析 columns 参数 - 包含 city 和 product 字段
        columns = json.loads(columns) if columns else [
            'id', 'name', 'website', 'email', 'phones', 'city', 'product',
            'facebook', 'twitter', 'instagram', 'linkedin', 'whatsapp', 'youtube', 
            'send_count', 'updated_at', 'created_at'
        ]

        # 查询记录（不分页，获取所有匹配的记录）
        records, _ = get_history_records(page=1, size=999999, query=query, show_empty_email=show_empty_email)

        if not records:
            return jsonify({"status": "error", "message": "没有可导出的记录"}), 404

        # 转换为 DataFrame
        df = pd.DataFrame(records)

        # 只保留指定的列
        available_columns = [col for col in columns if col in df.columns]
        if not available_columns:
            return jsonify({"status": "error", "message": "未选择有效列"}), 400
        df = df[available_columns]

        # 创建 Excel 文件
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='History')

        # 设置响应
        output.seek(0)
        response = make_response(output.read())
        response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        response.headers[
            'Content-Disposition'] = f'attachment; filename=history_export_{datetime.now().strftime("%Y-%m-%d")}.xlsx'

        return response

    except json.JSONDecodeError:
        return jsonify({"status": "error", "message": "无效的 columns 参数"}), 400
    except Exception as e:
        print(f"导出 Excel 失败: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/auto_scraper_facebook_email', methods=['POST'])
def auto_scraper_facebook_email():
    scraper_facebook_email('')


# ============================================================================
# 国家城市 API (Requirements 10.1, 10.2, 10.4)
# ============================================================================

@app.route('/api/countries', methods=['GET'])
def get_countries_api():
    """获取国家城市列表"""
    try:
        # 尝试从配置文件加载
        config_path = os.path.join(os.path.dirname(__file__), 'config', 'countries.json')
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return jsonify(data)
        
        # 返回默认数据
        default_data = {
            "US": {"name": "United States", "cities": ["New York", "Los Angeles", "Chicago", "Houston", "Phoenix", "Philadelphia", "San Antonio", "San Diego", "Dallas", "San Jose", "Austin", "Jacksonville", "Fort Worth", "Columbus", "Charlotte", "Seattle", "Denver", "Boston", "Atlanta", "Miami"]},
            "GB": {"name": "United Kingdom", "cities": ["London", "Birmingham", "Manchester", "Glasgow", "Liverpool", "Leeds", "Sheffield", "Edinburgh", "Bristol", "Leicester"]},
            "CA": {"name": "Canada", "cities": ["Toronto", "Montreal", "Vancouver", "Calgary", "Edmonton", "Ottawa", "Winnipeg", "Quebec City", "Hamilton", "Kitchener"]},
            "AU": {"name": "Australia", "cities": ["Sydney", "Melbourne", "Brisbane", "Perth", "Adelaide", "Gold Coast", "Newcastle", "Canberra", "Sunshine Coast", "Wollongong"]},
            "DE": {"name": "Germany", "cities": ["Berlin", "Hamburg", "Munich", "Cologne", "Frankfurt", "Stuttgart", "Düsseldorf", "Leipzig", "Dortmund", "Essen"]},
            "FR": {"name": "France", "cities": ["Paris", "Marseille", "Lyon", "Toulouse", "Nice", "Nantes", "Strasbourg", "Montpellier", "Bordeaux", "Lille"]},
            "CN": {"name": "China", "cities": ["Shanghai", "Beijing", "Guangzhou", "Shenzhen", "Chengdu", "Hangzhou", "Wuhan", "Xi'an", "Suzhou", "Nanjing"]},
            "JP": {"name": "Japan", "cities": ["Tokyo", "Osaka", "Nagoya", "Sapporo", "Fukuoka", "Kobe", "Kyoto", "Kawasaki", "Saitama", "Hiroshima"]},
            "IN": {"name": "India", "cities": ["Mumbai", "Delhi", "Bangalore", "Hyderabad", "Chennai", "Kolkata", "Pune", "Ahmedabad", "Jaipur", "Surat"]},
            "BR": {"name": "Brazil", "cities": ["São Paulo", "Rio de Janeiro", "Brasília", "Salvador", "Fortaleza", "Belo Horizonte", "Manaus", "Curitiba", "Recife", "Porto Alegre"]}
        }
        return jsonify(default_data)
    except Exception as e:
        print(f"获取国家城市数据失败: {e}", file=sys.stderr)
        return jsonify({"error": str(e)}), 500


@app.route('/api/cities/<country_code>', methods=['GET'])
def get_cities_api(country_code):
    """根据国家代码获取城市列表"""
    try:
        config_path = os.path.join(os.path.dirname(__file__), 'config', 'countries.json')
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if country_code in data:
                    return jsonify({"cities": data[country_code].get("cities", [])})
        return jsonify({"cities": []})
    except Exception as e:
        print(f"获取城市数据失败: {e}", file=sys.stderr)
        return jsonify({"error": str(e)}), 500


# ============================================================================
# 历史数据管理 API (Requirements 11.3, 11.5, 11.7)
# ============================================================================

from utils.history_manager import HistoryManager
_history_manager = HistoryManager()


@app.route('/api/records', methods=['POST'])
def create_record():
    """创建新记录"""
    if not session.get('logged_in'):
        return jsonify({"status": "error", "message": "请先登录"}), 401
    
    data = request.get_json()
    if not data:
        return jsonify({"status": "error", "message": "请求数据为空"}), 400
    
    record_id = _history_manager.create_record(data)
    if record_id > 0:
        return jsonify({"status": "success", "id": record_id, "message": "记录创建成功"})
    else:
        return jsonify({"status": "error", "message": "记录创建失败"}), 400


@app.route('/api/records/<int:record_id>', methods=['PUT'])
def update_record(record_id):
    """更新记录"""
    if not session.get('logged_in'):
        return jsonify({"status": "error", "message": "请先登录"}), 401
    
    data = request.get_json()
    if not data:
        return jsonify({"status": "error", "message": "请求数据为空"}), 400
    
    success = _history_manager.update_record(record_id, data)
    if success:
        return jsonify({"status": "success", "message": "记录更新成功"})
    else:
        return jsonify({"status": "error", "message": "记录更新失败"}), 400


@app.route('/api/records/<int:record_id>', methods=['DELETE'])
def delete_record(record_id):
    """删除记录"""
    if not session.get('logged_in'):
        return jsonify({"status": "error", "message": "请先登录"}), 401
    
    success = _history_manager.delete_record(record_id)
    if success:
        return jsonify({"status": "success", "message": "记录删除成功"})
    else:
        return jsonify({"status": "error", "message": "记录删除失败"}), 400


@app.route('/api/records/<int:record_id>', methods=['GET'])
def get_record(record_id):
    """获取单条记录"""
    if not session.get('logged_in'):
        return jsonify({"status": "error", "message": "请先登录"}), 401
    
    record = _history_manager.get_record_by_id(record_id)
    if record:
        return jsonify({"status": "success", "record": record})
    else:
        return jsonify({"status": "error", "message": "记录不存在"}), 404


@app.route('/api/records/batch-delete', methods=['POST'])
def batch_delete_records():
    """批量删除记录"""
    if not session.get('logged_in'):
        return jsonify({"status": "error", "message": "请先登录"}), 401
    
    data = request.get_json()
    record_ids = data.get('ids', [])
    
    if not record_ids:
        return jsonify({"status": "error", "message": "请选择要删除的记录"}), 400
    
    from db import delete_records_batch
    deleted_count = delete_records_batch(record_ids)
    
    return jsonify({
        "status": "success", 
        "message": f"成功删除 {deleted_count} 条记录",
        "deleted_count": deleted_count
    })


@app.route('/api/analytics/summary', methods=['GET'])
def get_analytics_summary_api():
    """获取系统统计摘要"""
    if not session.get('logged_in'):
        return jsonify({"status": "error", "message": "请先登录"}), 401
    
    from db import get_analytics_summary
    data = get_analytics_summary()
    return jsonify({"status": "success", "summary": data})

# ============================================================================
# AI 配置 API (Requirements 12.5, 12.6)
# ============================================================================

from models.ai_configuration import AIConfiguration
from utils.ai_email_assistant import AIEmailAssistant


def _get_ai_config_from_db() -> AIConfiguration:
    """从数据库获取AI配置"""
    try:
        from db import get_db_connection, release_connection
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT api_endpoint, api_key_encrypted, model_name FROM ai_configurations ORDER BY id DESC LIMIT 1')
        row = cursor.fetchone()
        cursor.close()
        release_connection(conn)
        
        if row:
            # 解密API密钥
            encrypted_key = row[1] or ''
            api_key = AIConfiguration.decrypt_key(encrypted_key) if encrypted_key else ''
            
            return AIConfiguration(
                api_endpoint=row[0] or '',
                api_key=api_key,  # 解密后的密钥
                model=row[2] or ''
            )
        return AIConfiguration()
    except Exception as e:
        print(f"获取AI配置失败: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return AIConfiguration()


def _save_ai_config_to_db(config: AIConfiguration) -> bool:
    """保存AI配置到数据库"""
    try:
        from db import get_db_connection, release_connection
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 检查是否已有配置
        cursor.execute('SELECT id FROM ai_configurations LIMIT 1')
        existing = cursor.fetchone()
        
        if existing:
            cursor.execute('''
                UPDATE ai_configurations 
                SET api_endpoint = ?, api_key_encrypted = ?, model_name = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (config.api_endpoint, config.api_key, config.model, existing[0]))
        else:
            cursor.execute('''
                INSERT INTO ai_configurations (api_endpoint, api_key_encrypted, model_name, provider)
                VALUES (?, ?, ?, 'custom')
            ''', (config.api_endpoint, config.api_key, config.model))
        
        conn.commit()
        cursor.close()
        release_connection(conn)
        print(f"[AI Config] 保存成功: endpoint={config.api_endpoint}, model={config.model}", file=sys.stderr)
        return True
    except Exception as e:
        print(f"[AI Config ERROR] 保存AI配置失败: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return False


@app.route('/api/ai-config', methods=['GET'])
def get_ai_config():
    """获取AI配置"""
    if not session.get('logged_in'):
        return jsonify({"status": "error", "message": "请先登录"}), 401
    
    config = _get_ai_config_from_db()
    # 不返回解密后的密钥，只返回是否已配置
    return jsonify({
        "status": "success",
        "config": {
            "api_endpoint": config.api_endpoint,
            "has_api_key": bool(config.api_key),
            "model": config.model
        }
    })


@app.route('/api/ai-config', methods=['PUT'])
def update_ai_config():
    """更新AI配置"""
    if not session.get('logged_in'):
        return jsonify({"status": "error", "message": "请先登录"}), 401
    
    data = request.get_json()
    if not data:
        return jsonify({"status": "error", "message": "请求数据为空"}), 400
    
    api_endpoint = data.get('api_endpoint', '')
    api_key = data.get('api_key', '')
    model = data.get('model', '')
    
    # 如果提供了新的API密钥，则加密存储
    encrypted_key = ''
    if api_key:
        encrypted_key = AIConfiguration.encrypt_key(api_key)
    else:
        # 保留原有密钥
        existing_config = _get_ai_config_from_db()
        encrypted_key = existing_config.api_key
    
    config = AIConfiguration(
        api_endpoint=api_endpoint,
        api_key=encrypted_key,
        model=model
    )
    
    if _save_ai_config_to_db(config):
        return jsonify({"status": "success", "message": "AI配置更新成功"})
    else:
        return jsonify({"status": "error", "message": "AI配置更新失败"}), 500


@app.route('/api/ai/generate-email', methods=['POST'])
def generate_email_api():
    """AI生成邮件内容"""
    if not session.get('logged_in'):
        return jsonify({"status": "error", "message": "请先登录"}), 401
    
    data = request.get_json() or {}
    requirements = data.get('requirements', '')
    context = data.get('context', {})
    
    config = _get_ai_config_from_db()
    assistant = AIEmailAssistant(config)
    
    if requirements:
        result = assistant.generate_with_requirements(requirements, context)
    else:
        result = assistant.generate_email(context)
    
    return jsonify({
        "status": "success" if result.success else "error",
        "content": result.content,
        "message": result.error_message or ""
    })


# 配置认证 token（推荐使用环境变量）
AUTH_TOKEN = os.getenv('PROXY_AUTH_TOKEN', 'p@d0000')  # 替换为你的 token


# 代理 Google Gemini API 的接口
@app.route('/api/proxy', methods=['POST'])
def proxy_gemini_api():
    try:
        # 验证 token
        auth_header = request.headers.get('Authorization')
        if not auth_header or auth_header != f'Bearer {AUTH_TOKEN}':
            return jsonify({'error': '无效或缺失的认证 token'}), 401

        # 目标 API 的 URL
        target_url = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key=AIzaSyCWxgCgsgL9Ku2MdnolX7YNolLME9OP0QE'

        # 获取客户端发送的 JSON 数据
        request_data = request.get_json()
        if not request_data:
            return jsonify({'error': '请求体必须是 JSON 格式'}), 400

        # 设置请求头
        headers = {
            'Content-Type': 'application/json'
        }

        # 发起代理请求
        response = requests.post(target_url, json=request_data, headers=headers)

        # 返回 Gemini API 的响应
        return jsonify(response.json()), response.status_code

    except requests.exceptions.RequestException as e:
        # 处理网络错误
        return jsonify({'error': f'代理请求失败: {str(e)}'}), 500
    except ValueError as e:
        # 处理 JSON 解析错误
        return jsonify({'error': '非 JSON 响应或解析错误'}), 500
    except Exception as e:
        # 处理其他未知错误
        return jsonify({'error': f'服务器错误: {str(e)}'}), 500
if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5001))
    # 使用 socketio.run 启动，支持 WebSocket
    socketio.run(app, host='0.0.0.0', port=port, debug=True, allow_unsafe_werkzeug=True)