import sys
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
import mysql.connector

from config import DB_CONFIG


def create_table():
    cnx = mysql.connector.connect(**DB_CONFIG)
    cursor = cnx.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS last_extraction_positions (
            id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
            url TEXT NOT NULL,
            last_position INTEGER,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY (url)
        )
    ''')
    cnx.commit()
    cursor.close()
    cnx.close()

def get_last_position(url):
    try:
        cnx = mysql.connector.connect(**DB_CONFIG)
        cursor = cnx.cursor()
        query = "SELECT last_position FROM last_extraction_positions WHERE url = %s"
        cursor.execute(query, (url,))
        result = cursor.fetchone()
        cursor.close()
        cnx.close()
        return result[0] if result else 0  # 如果没有找到记录，默认从 0 开始
    except mysql.connector.Error as err:
        print(f"Error getting last position: {err}", file=sys.stderr)
        return 0

def save_last_position(url, last_position):
    try:
        cnx = mysql.connector.connect(**DB_CONFIG)
        cursor = cnx.cursor()
        query = "INSERT INTO last_extraction_positions (url, last_position) VALUES (%s, %s) ON DUPLICATE KEY UPDATE last_position = %s, timestamp = CURRENT_TIMESTAMP"
        cursor.execute(query, (url, last_position, last_position))
        cnx.commit()
        cursor.close()
        cnx.close()
    except mysql.connector.Error as err:
        print(f"Error saving last position: {err}", file=sys.stderr)

def wait_for_element(driver, selector, timeout=5):
    try:
        element = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, selector))
        )
        return element
    except Exception as e:
        print(f"未找到元素 {selector}: {e}", file=sys.stderr)
        return None

def scroll_and_load_more(driver, max_scrolls=50, scroll_delay=3, target_count=500):
    business_links = set()  # 使用 set 避免重复链接
    min_scrolls = 5  # 至少滚动 5 次

    # 定位左侧商家列表的滚动区域
    scrollable_area = wait_for_element(driver, 'div[role="feed"], div[aria-label*="results"], div.m6QErb[style*="overflow: auto"], div[style*="overflow-y: scroll"]')
    if not scrollable_area:
        print("未找到左侧滚动区域，尝试整个页面滚动")
        scrollable_area = driver.find_element(By.TAG_NAME, "body")

    for i in range(max_scrolls):
        # 获取当前所有可见链接
        new_links = driver.find_elements(By.CSS_SELECTOR,
                                         'a[role="link"][aria-label], a.hfpxzc, a[href*="/maps/place/"]')
        for link in new_links:
            href = link.get_attribute('href') or link.text
            if href:
                business_links.add(href)
        current_link_count = len(business_links)
        print(f"滚动 {i + 1}/{max_scrolls} - 当前唯一商家链接数量: {current_link_count}")

        # 发送滚动状态给前端
        progress = int((i + 1) / max_scrolls * 50)  # 滚动阶段占前 50% 进度
        yield progress, None, None, f"正在滚动页面 ({i + 1}/{max_scrolls})，已找到 {current_link_count} 个商家链接"

        if current_link_count >= target_count:
            print(f"已达到或超过目标条数 {target_count}，停止滚动")
            break

        # 模拟滚轮向下滚动
        ActionChains(driver).move_to_element(scrollable_area).click().send_keys(Keys.PAGE_DOWN).perform()
        time.sleep(scroll_delay)  # 等待加载

        # 检查是否还有新链接加载
        new_links_after_scroll = driver.find_elements(By.CSS_SELECTOR,
                                                      'a[role="link"][aria-label], a.hfpxzc, a[href*="/maps/place/"]')
        for link in new_links_after_scroll:
            href = link.get_attribute('href') or link.text
            if href:
                business_links.add(href)
        if i >= min_scrolls and len(business_links) == current_link_count:
            print("链接数量不再增加，停止滚动")
            break

    # 转换为列表并截取目标数量
    business_links = list(business_links)[:target_count]
    print(f"滚动完成，最终找到 {len(business_links)} 个唯一商家链接")
    yield 50, None, business_links, "滚动完成"

def extract_single_business_info(driver):
    results = []
    try:
        time.sleep(3)  # 确保页面加载
        name_elem = wait_for_element(driver, 'h1.DUwDvf')
        name = name_elem.text.strip() if name_elem else "Unknown"

        business_data = {'name': name, 'website': None}

        # 提取网站
        website_elem = wait_for_element(driver, 'a[aria-label*="Website:"], a[data-item-id="authority"]')
        if website_elem:
            href = website_elem.get_attribute('href')
            business_data['website'] = href
            print(f"提取到网站: {href}")
        else:
            print(f"未找到 {name} 的网站元素，使用备用选择器")
            website_elem = wait_for_element(driver, 'a[href^="http"]:not([href*="google.com"])')
            if website_elem:
                href = website_elem.get_attribute('href')
                business_data['website'] = href
                print(f"备用选择器提取到网站: {href}")

        results.append(business_data)
        print(f"成功提取 {name} 的信息: {business_data}")
        return results, f"完成单个商家数据提取: {name}"
    except Exception as e:
        print(f"提取单个商家信息时出错: {e}", file=sys.stderr)
        return results, f"提取单个商家信息时出错: {e}"

def extract_business_info(driver, search_url, limit=500, remember_position=False):
    print(f"正在访问 URL: {search_url}，目标提取数量: {limit}，记住位置: {remember_position}")
    start_index = 0
    if remember_position:
        start_index = get_last_position(search_url)
        print(f"记住位置已启用，从索引 {start_index} 开始提取。")
        limit=limit+start_index
    try:
        driver.get(search_url)
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'body'))
        )
    except Exception as e:
        print(f"访问 URL 失败: {e}", file=sys.stderr)
        yield 0, None, None, f"访问 URL 失败: {e}"
        return

    if "/place/" in search_url:
        print("检测到单个商家页面，直接提取信息...")
        results, message = extract_single_business_info(driver)
        yield 50, None, None, "正在提取单个商家数据"
        yield 100, None, results[0] if results else None, message
        return

    print("开始滚动页面以加载更多商家...")
    business_links = []
    for progress, _, data, message in scroll_and_load_more(driver, max_scrolls=50, scroll_delay=3, target_count=limit):
        if data is not None and isinstance(data, list):
            business_links = data  # 收集滚动完成的链接列表
        yield progress, None, None, message

    if not business_links:
        print("未找到任何商家链接")
        yield 100, None, None, "未找到任何商家链接"
        return

    results = []
    total = len(business_links)
    print(f"共有 {total} 个商家链接可供提取")
    for i, link_href in enumerate(business_links[start_index:]): # 从上次保存的位置开始遍历
        current_index = start_index + i
        if len(results) >= limit:
            print(f"已提取 {limit} 条数据，停止提取")
            break

        try:
            # 根据 href 重新定位元素
            link = driver.find_element(By.XPATH, f"//a[@href='{link_href}' or text()='{link_href}']")
            name = link.get_attribute('aria-label') or link.text
            if not name:
                continue
            name = name.replace('Visited link', '').strip()

            print(f"点击商家: {name}")
            ActionChains(driver).move_to_element(link).click().perform()
            time.sleep(3)  # 确保页面加载

            # 发送提取状态
            progress = int(50 + (current_index + 1) / total * 50) if total > 0 else 50  # 提取阶段占后 50% 进度
            yield progress, name, None, f"正在提取数据: {name} ({current_index + 1}/{total})"

            current_url = driver.current_url
            if "/maps/place/" not in current_url:
                print(f"未跳转到商家详情页，当前 URL: {current_url}")
                continue

            info_panel = wait_for_element(driver, 'div[role="region"][aria-label*="Information for"], div.m6QErb')
            if not info_panel:
                print(f"未找到 {name} 的信息面板，跳过")
                continue
            print(f"找到 {name} 的信息面板")

            business_data = {'name': name, 'website': None}

            # 精准提取网站
            website_elem = wait_for_element(driver, 'a[aria-label*="Website:"], a[data-item-id="authority"]', timeout=3)
            if website_elem:
                href = website_elem.get_attribute('href')
                business_data['website'] = href
                print(f"提取到网站: {href}")
            else:
                print(f"未找到 {name} 的网站元素，使用备用选择器")
                website_elem = wait_for_element(driver, 'a[href^="http"]:not([href*="google.com"])', timeout=3)
                if website_elem:
                    href = website_elem.get_attribute('href')
                    business_data['website'] = href
                    print(f"备用选择器提取到网站: {href}")
            # 添加手机号提取逻辑（仅根据元素）
            business_data['phones'] = []  # 初始化 phones 字段
            phone_elem = wait_for_element(driver, 'button[data-item-id^="phone"], div[aria-label*="Phone:"]', timeout=3)
            if phone_elem:
                phone_text = phone_elem.text.strip()
                if phone_text:
                    # 清理常见分隔符，保留数字和加号
                    phone = ''.join(c for c in phone_text if c.isdigit() or c == '+')
                    if len(phone) >= 8:  # 确保是有效长度
                        business_data['phones'].append(phone)
                        print(f"提取到手机号: {phone}")
            else:
                print(f"未找到 {name} 的手机号元素，使用备用选择器")
                # 备用选择器：从页面中寻找包含电话图标的元素
                backup_phone_elem = wait_for_element(driver,
                                                     'div.rogA2c span.google-symbols[aria-hidden="true"] + div.Io6YTe',
                                                     timeout=3)
                if backup_phone_elem:
                    phone_text = backup_phone_elem.text.strip()
                    if phone_text:
                        phone = ''.join(c for c in phone_text if c.isdigit() or c == '+')
                        if len(phone) >= 8:
                            business_data['phones'].append(phone)
                            print(f"备用选择器提取到手机号: {phone}")
            business_data['phones'] = list(set(business_data['phones']))  # 去重
            results.append(business_data)
            print(f"成功提取 {name} 的信息: {business_data}")
            yield progress, name, business_data, f"成功提取: {name}"

        except Exception as e:
            print(f"提取 {link_href} 时出错: {e}", file=sys.stderr)
            continue
        finally:
            if remember_position:
                save_last_position(search_url, current_index + 1) # 保存当前完成的索引

    yield 100, None, None, "数据提取完成"