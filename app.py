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
from config import SECRET_KEY, CORS_ALLOWED_ORIGINS, OUTPUT_DIR, PASSWORD, MAX_CONCURRENT_TASKS
from chrome_driver import get_chrome_driver
from facebook_email_fetcher import scraper_facebook_email
from scraper import extract_business_info
from contact_scraper import extract_contact_info
from utils import save_to_csv, save_to_excel
from email_sender import EmailSender
from db import save_business_data_to_db, save_single_business_to_db, get_history_records, update_send_count, update_send_failed, backup_database_daily
from services.user_service import UserService

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

app = Flask(__name__)
app.secret_key = SECRET_KEY
# 使用 threading 模式，避免 gevent-websocket 配置问题
socketio = SocketIO(app, cors_allowed_origins=CORS_ALLOWED_ORIGINS, async_mode='threading')

# 存储提取的商家数据
business_data_store = []

from utils.task_manager import TaskManager
from services.scraper_service import ScraperService

# 全局任务管理器实例
task_manager = TaskManager(max_concurrent=MAX_CONCURRENT_TASKS)
scraper_service = ScraperService(socketio, app.app_context())

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
        
        if password != confirm_password:
            return render_template('register.html', error="两次输入的密码不一致", username=username)
        
        success, message = user_service.register_user(username, password)
        if success:
            return redirect(url_for('login', registered=1))
        return render_template('register.html', error=message, username=username)
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """用户登录路由"""
    registered = request.args.get('registered')
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        auth_result = user_service.authenticate(username, password)
        if auth_result.success:
            session['logged_in'] = True
            session['user_id'] = auth_result.user_id
            session['username'] = auth_result.username
            return redirect(url_for('operation'))
        return render_template('login.html', error=auth_result.error_message)
    
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

    if not task_manager.can_start_task():
        return jsonify({"status": "error", "message": "已达到最大并发任务数"}), 429

    config = {
        'country': request.form.get('country'),
        'city': request.form.get('city'),
        'product': request.form.get('product'),
        'url': request.form.get('url'),
        'limit': int(request.form.get('limit', 999999) or 999999),
        'proxy': request.form.get('proxy'),
        'remember_position': request.form.get('remember_position') == 'on'
    }

    if not config['product']:
        return jsonify({"status": "error", "message": "请输入商品/服务名称"}), 400

    # 加载国家城市数据（如果适用）
    if not config['city'] and config['country']:
        try:
            config_path = os.path.join(os.path.dirname(__file__), 'config', 'countries.json')
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    country_data = json.load(f)
                    config['cities_list'] = country_data.get(config['country'], {}).get('cities', [])
        except Exception as e:
            print(f"[ERROR] 加载国家数据失败: {e}", file=sys.stderr)

    task_id = f"extract_{os.urandom(4).hex()}"
    from scraper import reset_stop_flag
    reset_stop_flag()
    task_manager.terminate_all()
    
    # 清除旧数据，并定义回调
    business_data_store.clear()
    def data_callback(data):
        business_data_store.append(data)

    thread = threading.Thread(
        target=scraper_service.run_extraction, 
        args=(config, task_id, task_manager, data_callback)
    )
    thread.daemon = True
    task_manager.register_task(task_id, thread)
    thread.start()

    return jsonify({"status": "success", "message": "任务已启动...", "task_id": task_id})


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

    def background_contact_extraction(task_id, proxy=None):
        driver = None
        with app.app_context():
            try:
                if not business_data_store:
                    socketio.emit('progress_update', {
                        'progress': 100,
                        'message': '没有可用的商家数据，请先执行提取任务'
                    })
                    return

                driver, proxy_info = get_chrome_driver(proxy)
                # 注册 driver 以便管理
                task_manager.update_driver(task_id, driver)
                
                socketio.emit('progress_update',
                              {'progress': 0, 'message': '正在初始化浏览器...' if not proxy_info else proxy_info})

                for i, name, business_data, message in extract_contact_info(driver, business_data_store):
                    socketio.emit('progress_update', {
                        'progress': int((i + 1) / len(business_data_store) * 100),
                        'name': name,
                        'business_data': business_data,
                        'message': message
                    })

                # 联系方式提取完成后保存到 Excel
                csv_filename = save_to_excel(business_data_store)
                socketio.emit('progress_update', {
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
                socketio.emit('progress_update', {
                    'progress': 100,
                    'message': f'联系方式提取出错: {e}'
                })
            finally:
                if driver:
                    try: driver.quit()
                    except: pass
                task_manager.unregister_task(task_id)

    if not task_manager.can_start_task():
        return jsonify({"status": "error", "message": "已达到最大并发任务数"}), 429

    task_id = f"contact_{os.urandom(4).hex()}"
    thread = threading.Thread(target=background_contact_extraction, args=(task_id, proxy))
    thread.daemon = True
    task_manager.register_task(task_id, thread)
    thread.start()

    return jsonify({"status": "success", "message": "联系方式提取任务已启动..."})


@app.route('/extract_contacts_from_db', methods=['POST'])
def extract_contacts_from_db():
    """从数据库中提取没有邮箱的记录的联系方式"""
    if not session.get('logged_in'):
        return jsonify({"status": "error", "message": "请先登录"}), 401

    proxy = request.form.get('proxy')

    def background_db_contact_extraction(task_id, proxy=None):
        with app.app_context():
            driver = None
            try:
                driver, proxy_info = get_chrome_driver(proxy=proxy)
                task_manager.update_driver(task_id, driver)
                
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
            except Exception as e:
                print(f"[ERROR] DB Contact Extraction: {e}", file=sys.stderr)
                socketio.emit('progress_update', {'progress': 100, 'message': f'提取出错: {e}'})
            finally:
                if driver:
                    try: driver.quit()
                    except: pass
                task_manager.unregister_task(task_id)

    if not task_manager.can_start_task():
        return jsonify({"status": "error", "message": "已达到最大并发任务数"}), 429

    task_id = f"db_contact_{os.urandom(4).hex()}"
    thread = threading.Thread(target=background_db_contact_extraction, args=(task_id, proxy))
    thread.daemon = True
    task_manager.register_task(task_id, thread)
    thread.start()

    return jsonify({"status": "success", "message": "数据库联系方式提取任务已启动..."})

def background_target_contact_extraction(task_id, record_ids, proxy=None):
    """后台定向联系方式提取"""
    with app.app_context():
        driver = None
        try:
            driver, proxy_info = get_chrome_driver(proxy=proxy)
            # 注册 driver
            task_manager.update_driver(task_id, driver)
            
            from contact_scraper import extract_contacts_by_ids
            for progress, name, data, msg in extract_contacts_by_ids(driver, record_ids):
                socketio.emit('progress_update', {
                    'progress': progress,
                    'message': msg,
                    'business_data': data
                })
            socketio.emit('progress_update', {'progress': 100, 'message': '定向提取任务已完成'})
        except Exception as e:
            print(f"[ERROR] Target Extraction: {e}", file=sys.stderr)
            socketio.emit('progress_update', {'progress': 100, 'message': f'提取出错: {e}'})
        finally:
            if driver:
                try: driver.quit()
                except: pass
            task_manager.unregister_task(task_id)

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
        # 发送失败时更新状态为 failed
        update_send_failed([recipient])
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
    email_filter = request.args.get('filter', 'all')  # 获取筛选参数: all, has_email, no_email
    send_status = request.args.get('send_status', 'all')  # 获取发送状态筛选: all, sent, pending
    print(f"[DEBUG] get_history params: page={page}, size={size}, query='{query}', filter={email_filter}, send_status={send_status}", file=sys.stderr)
    try:
        result = get_history_records(page=page, per_page=size, search=query, email_filter=email_filter, send_status_filter=send_status)
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
    if not task_manager.can_start_task():
        return jsonify({"status": "error", "message": "已达到最大并发任务数"}), 429

    task_id = f"target_{os.urandom(4).hex()}"
    
    # 包装任务函数以适配 task_manager
    def wrapped_target_task(task_id, record_ids, proxy):
        # 这里的原始函数没有 task_id 参数，所以我们在这里处理
        background_target_contact_extraction(task_id, record_ids, proxy)

    thread = threading.Thread(target=wrapped_target_task, args=(task_id, record_ids, proxy))
    thread.daemon = True
    task_manager.register_task(task_id, thread)
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
        result = get_history_records(page=1, per_page=999999, search=query, show_empty_email=show_empty_email)
        records = result['records']

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


@app.route('/api/records/export-excel', methods=['GET'])
def export_records_excel():
    """导出记录到Excel - 支持按ID或筛选条件导出"""
    if not session.get('logged_in'):
        return jsonify({"status": "error", "message": "请先登录"}), 401

    try:
        ids_param = request.args.get('ids', '')
        query = request.args.get('query', '')
        email_filter = request.args.get('filter', 'all')
        send_status = request.args.get('send_status', 'all')
        
        records = []
        
        # 定义字段顺序（与数据管理表格一致）
        db_columns = ['city', 'product', 'name', 'website', 'phones', 'email', 
                      'send_status', 'send_count', 'last_sent_at', 'created_at',
                      'whatsapp', 'facebook', 'instagram', 'twitter', 'linkedin', 'youtube']
        
        if ids_param:
            # 按ID导出
            ids = [int(id.strip()) for id in ids_param.split(',') if id.strip()]
            if ids:
                from db import get_db_connection, release_connection
                connection = get_db_connection()
                cursor = connection.cursor()
                placeholders = ','.join(['?' for _ in ids])
                cursor.execute(f"""
                    SELECT city, product, name, website, phones, email, 
                           send_status, send_count, last_sent_at, created_at,
                           whatsapp, facebook, instagram, twitter, linkedin, youtube
                    FROM business_records
                    WHERE id IN ({placeholders})
                    ORDER BY created_at DESC
                """, ids)
                records = [dict(zip(db_columns, row)) for row in cursor.fetchall()]
                cursor.close()
                release_connection(connection)
        else:
            # 按筛选条件导出所有记录
            result = get_history_records(page=1, per_page=999999, search=query, 
                                        email_filter=email_filter, send_status_filter=send_status)
            # 重新排序字段
            records = [{col: r.get(col, '') for col in db_columns} for r in result['records']]
        
        if not records:
            return jsonify({"status": "error", "message": "没有可导出的记录"}), 404
        
        # 转换为 DataFrame，保持字段顺序
        df = pd.DataFrame(records, columns=db_columns)
        
        # 重命名列为中文（与表格顺序一致）
        column_names = {
            'city': '城市',
            'product': '关键词/类目',
            'name': '商家名称',
            'website': '网站',
            'phones': '联系电话',
            'email': '电子邮箱',
            'send_status': '发送状态',
            'send_count': '发送次数',
            'last_sent_at': '最后发送',
            'created_at': '创建时间',
            'whatsapp': 'WhatsApp',
            'facebook': 'Facebook',
            'instagram': 'Instagram',
            'twitter': 'Twitter',
            'linkedin': 'LinkedIn',
            'youtube': 'YouTube'
        }
        df = df.rename(columns=column_names)
        
        # 创建 Excel 文件
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='商家数据')
            
            # 调整列宽
            worksheet = writer.sheets['商家数据']
            for idx, col in enumerate(df.columns):
                max_length = max(df[col].astype(str).map(len).max(), len(col)) + 2
                col_letter = chr(65 + idx) if idx < 26 else chr(64 + idx // 26) + chr(65 + idx % 26)
                worksheet.column_dimensions[col_letter].width = min(max_length, 50)
        
        output.seek(0)
        response = make_response(output.read())
        response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        filename = f'business_data_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        response.headers['Content-Disposition'] = f'attachment; filename={filename}'
        
        print(f"[EXPORT] 导出 {len(records)} 条记录到 {filename}", file=sys.stderr)
        return response
        
    except Exception as e:
        print(f"导出 Excel 失败: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return jsonify({"status": "error", "message": str(e)}), 500


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


# ============================================================================
# 定时任务 API (Requirements 1.2, 3.1, 3.2, 5.1, 5.2, 5.3, 4.3)
# ============================================================================

@app.route('/api/scheduled-tasks/config', methods=['GET'])
def get_scheduled_task_config():
    """获取当前任务配置"""
    if not session.get('logged_in'):
        return jsonify({"status": "error", "message": "请先登录"}), 401
    
    try:
        from db import get_task_config
        config = get_task_config('contact_extraction')
        
        if not config:
            return jsonify({"status": "error", "message": "任务配置不存在"}), 404
        
        # 获取下次执行时间
        next_run_time = None
        if hasattr(app, 'task_manager'):
            next_run_time = app.task_manager.get_next_run_time()
        
        return jsonify({
            "status": "success",
            "config": {
                "task_name": config['task_name'],
                "schedule_hour": config['schedule_hour'],
                "schedule_minute": config['schedule_minute'],
                "enabled": config['enabled'],
                "next_run_time": next_run_time
            }
        })
    except Exception as e:
        print(f"[API ERROR] 获取任务配置失败: {e}", file=sys.stderr)
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/scheduled-tasks/config', methods=['PUT'])
def update_scheduled_task_config():
    """更新任务配置"""
    if not session.get('logged_in'):
        return jsonify({"status": "error", "message": "请先登录"}), 401
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "请求数据为空"}), 400
        
        schedule_hour = data.get('schedule_hour')
        schedule_minute = data.get('schedule_minute')
        enabled = data.get('enabled', True)
        
        # 验证参数
        if schedule_hour is None or schedule_minute is None:
            return jsonify({"status": "error", "message": "缺少必需参数"}), 400
        
        try:
            schedule_hour = int(schedule_hour)
            schedule_minute = int(schedule_minute)
        except (ValueError, TypeError):
            return jsonify({"status": "error", "message": "时间参数必须是整数"}), 400
        
        if not (0 <= schedule_hour <= 23):
            return jsonify({"status": "error", "message": "小时必须在 0-23 之间"}), 400
        
        if not (0 <= schedule_minute <= 59):
            return jsonify({"status": "error", "message": "分钟必须在 0-59 之间"}), 400
        
        # 更新配置并重新调度
        if hasattr(app, 'task_manager'):
            if app.task_manager.reschedule_task(schedule_hour, schedule_minute, enabled):
                return jsonify({
                    "status": "success",
                    "message": "任务配置已更新"
                })
            else:
                return jsonify({"status": "error", "message": "更新配置失败"}), 500
        else:
            return jsonify({"status": "error", "message": "任务管理器未初始化"}), 500
            
    except Exception as e:
        print(f"[API ERROR] 更新任务配置失败: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/scheduled-tasks/trigger', methods=['POST'])
def trigger_scheduled_task():
    """手动触发任务"""
    if not session.get('logged_in'):
        return jsonify({"status": "error", "message": "请先登录"}), 401
    
    try:
        if hasattr(app, 'task_manager'):
            if app.task_manager.is_running:
                return jsonify({
                    "status": "error",
                    "message": "任务正在执行，请稍后再试"
                }), 409
            
            if app.task_manager.trigger_now():
                return jsonify({
                    "status": "success",
                    "message": "任务已启动",
                    "execution_id": app.task_manager.current_execution_id
                })
            else:
                return jsonify({
                    "status": "error",
                    "message": "触发任务失败"
                }), 500
        else:
            return jsonify({"status": "error", "message": "任务管理器未初始化"}), 500
            
    except Exception as e:
        print(f"[API ERROR] 触发任务失败: {e}", file=sys.stderr)
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/scheduled-tasks/history', methods=['GET'])
def get_scheduled_task_history():
    """获取任务执行历史"""
    if not session.get('logged_in'):
        return jsonify({"status": "error", "message": "请先登录"}), 401
    
    try:
        limit = int(request.args.get('limit', 10))
        
        from db import get_execution_history
        history = get_execution_history('contact_extraction', limit)
        
        return jsonify({
            "status": "success",
            "history": history
        })
    except Exception as e:
        print(f"[API ERROR] 获取任务历史失败: {e}", file=sys.stderr)
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == "__main__":
    # 启动时执行数据库备份
    print("[INIT] Doing daily database backup...", file=sys.stderr)
    backup_database_daily()
    
    # 初始化定时任务管理器
    print("[INIT] Initializing scheduled task manager...", file=sys.stderr)
    from scheduled_tasks import ScheduledTaskManager
    
    app.task_manager = ScheduledTaskManager(app, socketio)
    app.task_manager.initialize()
    app.task_manager.start()
    
    # 注册应用关闭时的清理
    import atexit
    atexit.register(app.task_manager.shutdown)
    
    print("[INIT] Scheduled task manager initialized successfully", file=sys.stderr)
    
    port = int(os.environ.get('PORT', 5001))
    # 使用 socketio.run 启动，支持 WebSocket
    socketio.run(app, host='0.0.0.0', port=port, debug=True, allow_unsafe_werkzeug=True)