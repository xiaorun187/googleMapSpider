import time
import pandas as pd
from datetime import datetime
from flask import Flask, jsonify, request, render_template, session, redirect, url_for, send_file
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import os
import sys
import io

# 设置标准输出和标准错误流的编码为 UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 配置 Chrome 选项
chrome_options = Options()
chrome_options.add_argument(
    "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.6998.165 Safari/537.36")
chrome_options.add_argument("window-size=1920,3000")
chrome_options.add_argument("--disable-blink-features=AutomationControlled")
# 启用无头模式（Docker 环境中必须使用无头模式）
chrome_options.add_argument("--headless")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--no-sandbox")  # Docker 环境中需要
chrome_options.add_argument("--disable-dev-shm-usage")  # 解决 Docker 内存问题

# 在 Docker 环境中，Chrome 二进制路径由 Dockerfile 设置
chrome_options.binary_location = "/usr/bin/google-chrome"

# 设置 ChromeDriver 路径（Docker 环境中由 Dockerfile 设置）
service = Service("/usr/local/bin/chromedriver")

# 初始化 WebDriver
try:
    driver = webdriver.Chrome(service=service, options=chrome_options)
except Exception as e:
    print(f"初始化 WebDriver 失败: {e}")
    raise

# 初始化 Flask 应用
app = Flask(__name__)
app.secret_key = 'your-secret-key'  # 用于 session，需要替换为安全的密钥

# 确保输出目录存在
OUTPUT_DIR = 'output'
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)


def wait_for_element(selector, timeout=10):
    """等待元素出现"""
    try:
        element = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, selector))
        )
        return element
    except Exception as e:
        print(f"未找到元素 {selector}: {e}", file=sys.stderr, errors='replace')
        return None


def scroll_and_load_more(max_scrolls=5, scroll_delay=3, target_count=10):
    """滚动页面以加载更多内容，直到达到目标条数或无新内容"""
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

        scroll_position_before = driver.execute_script("return window.scrollY;")
        print(f"滚动前位置: {scroll_position_before}")

        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(scroll_delay)

        scroll_position_after = driver.execute_script("return window.scrollY;")
        print(f"滚动后位置: {scroll_position_after}")

        if scroll_position_after <= scroll_position_before:
            print("滚动未生效，可能是页面已到底部或动态加载失败")
            break

    print(f"滚动完成，最终找到 {len(business_links)} 个商家链接")
    return business_links


def extract_single_business_info():
    """从单个商家页面提取信息"""
    results = []
    try:
        time.sleep(5)
        name_elem = wait_for_element('h1.DUwDvf')
        name = name_elem.text.strip() if name_elem else "Unknown"

        business_data = {'name': name}

        address_elem = wait_for_element('button[aria-label*="Address:"], div[data-item-id="address"]')
        if address_elem:
            business_data['address'] = address_elem.get_attribute('aria-label').replace('Address: ',
                                                                                        '').strip() if address_elem.get_attribute(
                'aria-label') else address_elem.text.strip()

        hours_elem = wait_for_element('span.ZDu9vd, div[data-item-id="oh"]')
        if hours_elem:
            business_data['hours'] = hours_elem.text.strip()

        website_elem = wait_for_element('a[aria-label*="Website:"], a[data-item-id="authority"]')
        if website_elem:
            business_data['website'] = website_elem.get_attribute('href')

        phone_elem = wait_for_element('button[aria-label*="Phone:"], div[data-item-id="phone"]')
        if phone_elem:
            business_data['phone'] = phone_elem.get_attribute('aria-label').replace('Phone: ',
                                                                                    '').strip() if phone_elem.get_attribute(
                'aria-label') else phone_elem.text.strip()

        plus_code_elem = wait_for_element('button[aria-label*="Plus code:"], div[data-item-id="oloc"]')
        if plus_code_elem:
            business_data['plusCode'] = plus_code_elem.get_attribute('aria-label').replace('Plus code: ',
                                                                                           '').strip() if plus_code_elem.get_attribute(
                'aria-label') else plus_code_elem.text.strip()

        results.append(business_data)
        print(f"成功提取 {name} 的信息: {business_data}")

    except Exception as e:
        print(f"提取单个商家信息时出错: {e}", file=sys.stderr, errors='replace')

    return results


def extract_business_info(search_url, limit=10):
    """从 Google Maps 提取指定数量的商家信息"""
    print(f"正在访问 URL: {search_url}")
    try:
        driver.get(search_url)
    except Exception as e:
        print(f"访问 URL 失败: {e}", file=sys.stderr, errors='replace')
        return []

    if "/place/" in search_url:
        print("检测到单个商家页面，直接提取信息...")
        return extract_single_business_info()

    print("开始滚动页面以加载更多商家...")
    business_links = scroll_and_load_more(max_scrolls=10, scroll_delay=3, target_count=limit)

    if not business_links:
        print("未找到任何商家链接")
        return []

    results = []
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
            driver.execute_script("arguments[0].click();", link)
            time.sleep(2)

            info_panel = wait_for_element('div[role="region"][aria-label*="Information for"]')
            if not info_panel:
                print(f"未找到 {name} 的信息面板，跳过")
                continue

            business_data = {'name': name}

            address_elem = info_panel.find_elements(By.CSS_SELECTOR,
                                                    'button[aria-label*="Address:"], div[data-item-id="address"]')
            if address_elem:
                business_data['address'] = address_elem[0].get_attribute('aria-label').replace('Address: ',
                                                                                               '').strip() if \
                address_elem[0].get_attribute('aria-label') else address_elem[0].text.strip()

            hours_elem = info_panel.find_elements(By.CSS_SELECTOR, 'span.ZDu9vd, div[data-item-id="oh"]')
            if hours_elem:
                business_data['hours'] = hours_elem[0].text.strip()

            website_elem = info_panel.find_elements(By.CSS_SELECTOR,
                                                    'a[aria-label*="Website:"], a[data-item-id="authority"]')
            if website_elem:
                business_data['website'] = website_elem[0].get_attribute('href')

            phone_elem = info_panel.find_elements(By.CSS_SELECTOR,
                                                  'button[aria-label*="Phone:"], div[data-item-id="phone"]')
            if phone_elem:
                business_data['phone'] = phone_elem[0].get_attribute('aria-label').replace('Phone: ', '').strip() if \
                phone_elem[0].get_attribute('aria-label') else address_elem[0].text.strip()

            plus_code_elem = info_panel.find_elements(By.CSS_SELECTOR,
                                                      'button[aria-label*="Plus code:"], div[data-item-id="oloc"]')
            if plus_code_elem:
                business_data['plusCode'] = plus_code_elem[0].get_attribute('aria-label').replace('Plus code: ',
                                                                                                  '').strip() if \
                plus_code_elem[0].get_attribute('aria-label') else plus_code_elem[0].text.strip()

            results.append(business_data)
            print(f"成功提取 {name} 的信息: {business_data}")

        except Exception as e:
            print(f"提取 {name} 时出错: {e}", file=sys.stderr, errors='replace')
            continue

    return results


def save_to_csv(data):
    """将数据保存为 CSV 文件，文件名基于当前时间"""
    if not data:
        print("没有数据可保存")
        return None

    # 生成基于时间的文件名
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"google_maps_data_{timestamp}.csv"
    filepath = os.path.join(OUTPUT_DIR, filename)

    df = pd.DataFrame(data)
    df.to_csv(filepath, sep=';', encoding='utf-8-sig', index=False)
    print(f"数据已保存到 {filepath}")
    return filename  # 返回文件名，而不是完整路径


# 根路径重定向到登录页面
@app.route('/')
def index():
    return redirect(url_for('login'))


# 登录页面
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


# 操作页面
@app.route('/operation')
def operation():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return render_template('operation.html')


# 结果页面
@app.route('/result', methods=['POST'])
def result():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    url = request.form.get('url')
    limit = request.form.get('limit')

    try:
        limit = int(limit)
        if limit <= 0:
            raise ValueError("limit 必须大于 0")
    except (ValueError, TypeError):
        return render_template('operation.html', error="limit 必须是一个有效的正整数")

    try:
        extracted_data = extract_business_info(url, limit=limit)
        if not extracted_data:
            return render_template('operation.html', error="未提取到任何数据")

        csv_filename = save_to_csv(extracted_data)
        return render_template('result.html', data=extracted_data, csv_file=csv_filename)
    except Exception as e:
        return render_template('operation.html', error=f"提取失败: {str(e)}")


# 下载 CSV 文件
@app.route('/download/<filename>')
def download_file(filename):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    filepath = os.path.join(OUTPUT_DIR, filename)
    if not os.path.exists(filepath):
        return "文件不存在", 404
    return send_file(filepath, as_attachment=True, download_name=filename)


# API 接口：提取数据
@app.route('/extract', methods=['POST'])
def extract():
    if not session.get('logged_in'):
        return jsonify({"status": "error", "message": "请先登录"}), 401

    data = request.get_json()
    if not data or 'url' not in data:
        return jsonify({"status": "error", "message": "请提供 Google Maps URL"}), 400

    search_url = data['url']
    if not search_url.startswith('https://www.google.com/maps'):
        return jsonify({"status": "error", "message": "请输入有效的 Google Maps URL"}), 400

    limit = data.get('limit', 10)
    try:
        limit = int(limit)
        if limit <= 0:
            return jsonify({"status": "error", "message": "limit 必须大于 0"}), 400
    except (ValueError, TypeError):
        return jsonify({"status": "error", "message": "limit 必须是一个有效的整数"}), 400

    try:
        extracted_data = extract_business_info(search_url, limit=limit)
        if not extracted_data:
            return jsonify({"status": "error", "message": "未提取到任何数据"}), 404

        csv_filename = save_to_csv(extracted_data)
        return jsonify({
            "status": "success",
            "data": extracted_data,
            "csv_file": csv_filename
        })
    except Exception as e:
        return jsonify({"status": "error", "message": f"提取失败: {str(e)}"}), 500


if __name__ == "__main__":
    try:
        app.run(host='0.0.0.0', port=5000, debug=True)
    finally:
        driver.quit()