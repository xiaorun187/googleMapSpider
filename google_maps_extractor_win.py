import time
import pandas as pd
from datetime import datetime
from flask import Flask, jsonify, request, render_template, session, redirect, url_for, send_file
from flask_socketio import SocketIO, emit
import threading
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import os
import sys
import io
import re
import zipfile

# 设置标准输出和标准错误流的编码为 UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# 初始化 Flask 应用
app = Flask(__name__)
app.secret_key = 'your-secret-key'  # 请替换为安全的密钥
socketio = SocketIO(app, cors_allowed_origins="*")

# 确保输出目录存在
OUTPUT_DIR = 'output'
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

# ChromeDriver 服务路径（Windows）
service = Service(r"C:\chromedriver\chromedriver.exe")

# 创建代理认证扩展
def create_proxy_auth_extension(proxy_host, proxy_port, username, password):
    manifest_json = """
    {
        "version": "1.0.0",
        "manifest_version": 2,
        "name": "Proxy Auth Extension",
        "permissions": [
            "proxy",
            "tabs",
            "unlimitedStorage",
            "storage",
            "<all_urls>",
            "webRequest",
            "webRequestBlocking"
        ],
        "background": {
            "scripts": ["background.js"]
        }
    }
    """

    background_js = f"""
    var config = {{
        mode: "fixed_servers",
        rules: {{
            singleProxy: {{
                scheme: "http",
                host: "{proxy_host}",
                port: parseInt({proxy_port})
            }},
            bypassList: ["localhost"]
        }}
    }};

    chrome.proxy.settings.set({{value: config, scope: "regular"}}, function() {{}});

    function callbackFn(details) {{
        return {{
            authCredentials: {{
                username: "{username}",
                password: "{password}"
            }}
        }};
    }}

    chrome.webRequest.onAuthRequired.addListener(
        callbackFn,
        {{urls: ["<all_urls>"]}},
        ['blocking']
    );
    """

    proxy_extension = os.path.join(OUTPUT_DIR, "proxy_auth.zip")
    with zipfile.ZipFile(proxy_extension, 'w') as zp:
        zp.writestr("manifest.json", manifest_json)
        zp.writestr("background.js", background_js)
    return proxy_extension

# 配置 Chrome 选项
def get_chrome_options(proxy=None):
    chrome_options = Options()
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.6998.165 Safari/537.36")
    chrome_options.add_argument("window-size=1920,3000")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    # 调试时禁用无头模式，确保浏览器可见
    # chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--ignore-certificate-errors")  # 忽略 SSL 错误
    chrome_options.binary_location = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

    if proxy:
        if '@' in proxy:  # 带认证的代理
            try:
                username_password, host_port = proxy.split('@')
                username, password = username_password.split(':')
                host, port = host_port.split(':')
                extension = create_proxy_auth_extension(host, port, username, password)
                chrome_options.add_extension(extension)
                print(f"应用带认证代理: {proxy}")
                socketio.emit('progress_update', {'progress': 0, 'message': f'应用带认证代理: {proxy}'})
            except ValueError as e:
                print(f"代理格式错误: {proxy}, 应为 username:password@host:port, 错误: {e}", file=sys.stderr)
                socketio.emit('progress_update', {'progress': 0, 'message': f'代理格式错误: {e}'})
        else:  # 无认证代理
            chrome_options.add_argument(f"--proxy-server={proxy}")  # 去掉 http:// 前缀，确保格式正确
            print(f"应用无认证代理: {proxy}")
            socketio.emit('progress_update', {'progress': 0, 'message': f'应用无认证代理: {proxy}'})

    return chrome_options

def wait_for_element(driver, selector, timeout=10):
    """等待元素出现"""
    try:
        element = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, selector))
        )
        return element
    except Exception as e:
        print(f"未找到元素 {selector}: {e}", file=sys.stderr)
        return None

def scroll_and_load_more(driver, max_scrolls=5, scroll_delay=3, target_count=10):
    """滚动页面以加载更多内容"""
    previous_link_count = 0
    business_links = []
    for i in range(max_scrolls):
        business_links = driver.find_elements(By.CSS_SELECTOR,
                                              'a[role="link"][aria-label], a.hfpxzc, a[href*="/maps/place/"]')
        current_link_count = len(business_links)
        print(f"滚动 {i + 1}/{max_scrolls} - 当前商家链接数量: {current_link_count}")

        if current_link_count >= target_count:
            print(f"已达到目标条数 {target_count}，停止滚动")
            business_links = business_links[:target_count]
            break

        if i > 0 and current_link_count == previous_link_count:
            print("链接数量不再增加，停止滚动")
            break

        previous_link_count = current_link_count
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(scroll_delay)

    print(f"滚动完成，最终找到 {len(business_links)} 个商家链接")
    return business_links

def extract_single_business_info(driver):
    """从单个商家页面提取信息"""
    results = []
    try:
        time.sleep(5)
        name_elem = wait_for_element(driver, 'h1.DUwDvf')
        name = name_elem.text.strip() if name_elem else "Unknown"

        business_data = {'name': name}

        address_elem = wait_for_element(driver, 'button[aria-label*="Address:"], div[data-item-id="address"]')
        if address_elem:
            business_data['address'] = (address_elem.get_attribute('aria-label') or address_elem.text).replace('Address: ', '').strip()

        hours_elem = wait_for_element(driver, 'span.ZDu9vd, div[data-item-id="oh"]')
        if hours_elem:
            business_data['hours'] = hours_elem.text.strip()

        website_elem = wait_for_element(driver, 'a[aria-label*="Website:"], a[data-item-id="authority"]')
        if website_elem:
            business_data['website'] = website_elem.get_attribute('href')

        phone_elem = wait_for_element(driver, 'button[aria-label*="Phone:"], div[data-item-id="phone"]')
        if phone_elem:
            business_data['phone'] = (phone_elem.get_attribute('aria-label') or phone_elem.text).replace('Phone: ', '').strip()

        plus_code_elem = wait_for_element(driver, 'button[aria-label*="Plus code:"], div[data-item-id="oloc"]')
        if plus_code_elem:
            business_data['plusCode'] = (plus_code_elem.get_attribute('aria-label') or plus_code_elem.text).replace('Plus code: ', '').strip()

        results.append(business_data)
        print(f"成功提取 {name} 的信息: {business_data}")
        socketio.emit('progress_update', {'progress': 100, 'current': name, 'message': '完成单个商家数据提取'})
    except Exception as e:
        print(f"提取单个商家信息时出错: {e}", file=sys.stderr)

    return results

def extract_business_info(driver, search_url, limit=10):
    """从 Google Maps 提取指定数量的商家信息"""
    print(f"正在访问 URL: {search_url}")
    try:
        driver.get(search_url)
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'body'))
        )
    except Exception as e:
        print(f"访问 URL 失败: {e}", file=sys.stderr)
        socketio.emit('progress_update', {'progress': 0, 'message': f'访问 URL 失败: {e}'})
        return []

    if "/place/" in search_url:
        print("检测到单个商家页面，直接提取信息...")
        return extract_single_business_info(driver)

    print("开始滚动页面以加载更多商家...")
    business_links = scroll_and_load_more(driver, max_scrolls=10, scroll_delay=2, target_count=limit)

    if not business_links:
        print("未找到任何商家链接")
        return []

    results = []
    total = len(business_links)
    for i, link in enumerate(business_links):
        if len(results) >= limit:
            print(f"已提取 {limit} 条数据，停止提取")
            break

        try:
            name = link.get_attribute('aria-label') or link.text
            if not name:
                continue
            name = name.replace('Visited link', '').strip()

            print(f"点击商家: {name}")
            from selenium.webdriver.common.action_chains import ActionChains
            ActionChains(driver).move_to_element(link).click().perform()
            time.sleep(3)

            current_url = driver.current_url
            if "/maps/place/" not in current_url:
                print(f"未跳转到商家详情页，当前 URL: {current_url}")
                continue

            info_panel_selectors = [
                'div[role="region"][aria-label*="Information for"]',
                'div[role="region"][aria-label*="商家信息"]',
                'div[role="main"]',
                'div.m6QErb',
                'div.W4Efsd',
                'div.fontBodyMedium',
                'div[aria-label*="Business information"]'
            ]
            info_panel = None
            for selector in info_panel_selectors:
                info_panel = wait_for_element(driver, selector, timeout=15)
                if info_panel:
                    print(f"使用选择器 {selector} 找到信息面板")
                    break

            if not info_panel:
                print(f"未找到 {name} 的信息面板，跳过")
                continue

            business_data = {'name': name}
            all_elements = info_panel.find_elements(By.CSS_SELECTOR,
                                                    'button[aria-label], div[data-item-id], div.Io6YTe, div.W4Efsd, span.ZDu9vd, a[href], div.fontBodyMedium, div[role="main"] div')

            business_data['address'] = None
            business_data['hours'] = None
            business_data['website'] = None
            business_data['phone'] = None
            business_data['plusCode'] = None

            for elem in all_elements:
                text = (elem.get_attribute('aria-label') or elem.text).strip()
                if not text:
                    continue

                if ('Address:' in text or '地址' in text) and not business_data['address']:
                    address_text = text.replace('Address: ', '').replace('地址：', '').strip()
                    if not re.match(r'^\d+\.\d+\(\d+\)', address_text):
                        business_data['address'] = address_text

                if ('hours' in text.lower() or '营业时间' in text or 'Open' in text or 'Closed' in text) and not business_data['hours']:
                    hours_text = text.strip()
                    if not re.match(r'^\d+\.\d+\(\d+\)', hours_text) and any(day in hours_text.lower() for day in ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun', 'open', 'closed']):
                        business_data['hours'] = hours_text

                if ('Phone:' in text or '电话' in text or re.match(r'\+?\d[\d\s-]+', text)) and not business_data['phone']:
                    phone_text = text.replace('Phone: ', '').replace('电话：', '').strip()
                    if re.match(r'\+?\d[\d\s-]+', phone_text):
                        business_data['phone'] = phone_text

                if ('Website:' in text or '网站' in text or elem.get_attribute('href')) and not business_data['website']:
                    href = elem.get_attribute('href')
                    if href and ('http' in href or 'www' in href) and 'google.com/maps' not in href:
                        business_data['website'] = href

                if ('Plus code:' in text or 'Plus Code' in text or re.match(r'[A-Z0-9]+\+[A-Z0-9]+', text)) and not business_data['plusCode']:
                    plus_code_text = text.replace('Plus code: ', '').strip()
                    if re.match(r'[A-Z0-9]+\+[A-Z0-9]+', plus_code_text):
                        business_data['plusCode'] = plus_code_text

            results.append(business_data)
            print(f"成功提取 {name} 的信息: {business_data}")

            progress = int((i + 1) / total * 100)
            socketio.emit('progress_update', {
                'progress': progress,
                'current': name,
                'business_data': business_data
            })

        except Exception as e:
            print(f"提取 {name} 时出错: {e}", file=sys.stderr)
            continue

    socketio.emit('progress_update', {'progress': 100, 'message': '数据提取完成'})
    return results

def save_to_csv(data):
    """将数据保存为 CSV 文件"""
    if not data:
        print("没有数据可保存")
        return None

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"google_maps_data_{timestamp}.csv"
    filepath = os.path.join(OUTPUT_DIR, filename)

    df = pd.DataFrame(data)
    df.to_csv(filepath, sep=';', encoding='utf-8-sig', index=False)
    print(f"数据已保存到 {filepath}")
    return filename

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username == 'admin' and password == 'password':
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

    try:
        limit = int(limit)
        if limit <= 0:
            return jsonify({"status": "error", "message": "limit 必须大于 0"}), 400
    except (ValueError, TypeError):
        return jsonify({"status": "error", "message": "limit 必须是一个有效的正整数"}), 400

    def background_extraction(search_url, limit, proxy=None):
        driver = None
        try:
            chrome_options = get_chrome_options(proxy)
            driver = webdriver.Chrome(service=service, options=chrome_options)
            socketio.emit('progress_update', {'progress': 0, 'message': '正在初始化浏览器...'})

            # 测试代理是否生效
            try:
                driver.set_page_load_timeout(30)  # 设置页面加载超时
                driver.get("http://httpbin.org/ip")  # 使用更简单的测试 URL
                ip_info = driver.page_source
                print(f"当前 IP 信息: {ip_info}")
                socketio.emit('progress_update', {'progress': 5, 'message': f'代理测试 IP: {ip_info[:100]}...'})
            except Exception as e:
                print(f"代理测试失败: {e}", file=sys.stderr)
                socketio.emit('progress_update', {'progress': 5, 'message': f'代理测试失败: {e}'})
                return

            # 执行提取任务
            extracted_data = extract_business_info(driver, search_url, limit=limit)
            if extracted_data:
                csv_filename = save_to_csv(extracted_data)
                socketio.emit('progress_update', {
                    'progress': 100,
                    'csv_file': csv_filename,
                    'message': '提取完成'
                })
            else:
                socketio.emit('progress_update', {
                    'progress': 100,
                    'message': '未提取到任何数据'
                })
        except Exception as e:
            print(f"后台任务发生异常: {e}", file=sys.stderr)
            socketio.emit('progress_update', {
                'progress': 100,
                'message': f'后台任务出错: {e}'
            })
        finally:
            if driver:
                driver.quit()

    thread = threading.Thread(target=background_extraction, args=(url, limit, proxy))
    thread.daemon = True
    thread.start()

    return jsonify({"status": "success", "message": "任务已启动，正在提取数据..."})

if __name__ == "__main__":
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)