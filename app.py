from gevent import monkey
monkey.patch_all()

import json
import sys
import io
import os
import threading
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
from db import save_business_data_to_db, get_history_records,update_send_count  # 新增导入

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

app = Flask(__name__)
app.secret_key = SECRET_KEY
socketio = SocketIO(app, cors_allowed_origins=CORS_ALLOWED_ORIGINS)

# 存储提取的商家数据
business_data_store = []

# 全局任务管理器：存储线程和 driver 实例
running_tasks = {}

def terminate_all_tasks():
    """终止所有正在运行的任务和 driver 实例"""
    global running_tasks
    for task_id, task_info in list(running_tasks.items()):
        thread = task_info['thread']
        driver = task_info['driver']
        try:
            if driver:
                driver.quit()
                print(f"任务 {task_id} 的 Selenium driver 已终止", file=sys.stderr)
            if thread.is_alive():
                print(f"任务 {task_id} 的线程仍在运行，等待其自然结束", file=sys.stderr)
        except Exception as e:
            print(f"终止任务 {task_id} 失败: {e}", file=sys.stderr)
    running_tasks.clear()
    print("所有任务已清理", file=sys.stderr)

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username == 'admin' and password == PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('operation'))
        else:
            return render_template('login.html', error="用户名或密码错误")
    return render_template('login.html')

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

    url = request.form.get('url')
    limit = request.form.get('limit')
    proxy = request.form.get('proxy')
    remember_position = request.form.get('remember_position') == 'on'  # 获取复选框状态

    try:
        limit = int(limit)
        if limit <= 0:
            return jsonify({"status": "error", "message": "limit 必须大于 0"}), 400
    except (ValueError, TypeError):
        return jsonify({"status": "error", "message": "limit 必须是一个有效的正整数"}), 400

    terminate_all_tasks()
    socketio.emit('progress_update', {'progress': 0, 'message': '正在清理旧任务...'})

    task_id = f"extract_{os.urandom(4).hex()}"

    def background_extraction(search_url, limit, proxy=None, task_id=task_id,remember_position=False):
        driver = None
        with app.app_context():
            try:
                driver, proxy_info = get_chrome_driver(proxy)
                running_tasks[task_id] = {'thread': threading.current_thread(), 'driver': driver}
                socketio.emit('progress_update', {'progress': 0, 'message': '正在初始化浏览器...' if not proxy_info else proxy_info})

                extracted_data = []
                for progress, current, business_data, message in extract_business_info(driver, search_url, limit,remember_position):
                    if business_data:
                        extracted_data.append(business_data)
                    socketio.emit('progress_update', {
                        'progress': progress,
                        'current': current,
                        'business_data': business_data,
                        'message': message
                    })

                if extracted_data:
                    global business_data_store
                    business_data_store = extracted_data
                    csv_filename = save_to_excel(extracted_data)
                    socketio.emit('progress_update', {
                        'progress': 100,
                        'csv_file': csv_filename,
                        'message': '数据提取完成',
                        'data': extracted_data
                    })
                else:
                    socketio.emit('progress_update', {
                        'progress': 100,
                        'message': '未提取到任何数据'
                    })
            except Exception as e:
                print(f"后台任务 {task_id} 发生异常: {e}", file=sys.stderr)
                socketio.emit('progress_update', {
                    'progress': 100,
                    'message': f'后台任务出错: {e}'
                })
            finally:
                if driver:
                    driver.quit()
                if task_id in running_tasks:
                    del running_tasks[task_id]

    thread = threading.Thread(target=background_extraction, args=(url, limit, proxy, task_id,remember_position))
    thread.daemon = True
    thread.start()

    return jsonify({"status": "success", "message": "任务已启动，正在提取数据...", "task_id": task_id})

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

                # 联系方式提取完成后保存到 Excel 和数据库
                csv_filename = save_to_excel(business_data_store)
                socketio.emit('contact_update', {
                    'progress': 100,
                    'csv_file': csv_filename,
                    'message': '联系方式提取完成'
                })

                # 保存到数据库
                # save_business_data_to_db(business_data_store)
                # socketio.emit('contact_update', {
                #     'progress': 100,
                #     'csv_file': csv_filename,
                #     'message': '联系方式提取完成并已保存到数据库'
                # })

            except Exception as e:
                print(f"联系方式提取任务发生异常: {e}", file=sys.stderr)
                socketio.emit('contact_update', {
                    'progress': 100,
                    'message': f'联系方式提取出错: {e}'
                })
            finally:
                if driver:
                    driver.quit()

    thread = threading.Thread(target=background_contact_extraction, args=(proxy,))
    thread.daemon = True
    thread.start()

    return jsonify({"status": "success", "message": "联系方式提取任务已启动..."})

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
    try:
        records, total = get_history_records(page, size, query,show_empty_email)
        total_pages = (total + size - 1) // size
        return jsonify({
            "status": "success",
            "records": records,
            "total_pages": total_pages
        })
    except Exception as e:
        print(f"查询历史记录失败: {e}", file=sys.stderr)
        return jsonify({"status": "error", "message": str(e)}), 500

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
        # 解析 columns 参数
        columns = json.loads(columns) if columns else [
            'id', 'name', 'website', 'email', 'phones', 'facebook', 'twitter',
            'instagram', 'linkedin', 'whatsapp', 'youtube', 'send_count',
            'updated_at', 'created_at'
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
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=True)