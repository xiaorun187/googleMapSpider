import sys
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys

# 导入SQLite数据库模块
import db as db_module

# 导入优化模块
from utils.enterprise_logger import get_logger, LogLevel
from utils.rate_limiter import RateLimiter
from utils.smart_wait import SmartWaitStrategy
from utils.data_integrity_validator import DataIntegrityValidator

import json
import os
from datetime import datetime
import re

# 初始化全局组件
_logger = get_logger('google-map-spider')
_rate_limiter = RateLimiter()
_smart_wait = SmartWaitStrategy()

# 进度保存目录
PROGRESS_DIR = 'progress'

# 全局停止标志 - 用于控制持续爬取的停止
_stop_extraction_flag = False
_stop_lock = __import__('threading').Lock()


def set_stop_extraction(stop: bool):
    """设置停止爬取标志"""
    global _stop_extraction_flag
    with _stop_lock:
        _stop_extraction_flag = stop
        print(f"停止爬取标志已设置为: {stop}")


def should_stop_extraction() -> bool:
    """检查是否应该停止爬取"""
    global _stop_extraction_flag
    with _stop_lock:
        return _stop_extraction_flag


def reset_stop_flag():
    """重置停止标志"""
    global _stop_extraction_flag
    with _stop_lock:
        _stop_extraction_flag = False


class ProgressManager:
    """
    进度管理器 - 实现进度保存与恢复
    
    Features:
    - 关键错误时自动保存进度
    - 从保存点恢复功能
    - 支持多任务进度管理
    """
    
    def __init__(self, progress_dir: str = PROGRESS_DIR):
        self.progress_dir = progress_dir
        self._ensure_dir_exists()
    
    def _ensure_dir_exists(self):
        """确保进度目录存在"""
        if not os.path.exists(self.progress_dir):
            os.makedirs(self.progress_dir)
    
    def _get_progress_file(self, task_key: str) -> str:
        """获取进度文件路径"""
        # 清理任务键，移除非法字符
        safe_key = "".join(c if c.isalnum() or c in ('_', '-') else '_' for c in task_key)
        return os.path.join(self.progress_dir, f"{safe_key}_progress.json")
    
    def save_progress(self, task_key: str, progress_data: dict) -> bool:
        """
        保存进度
        
        Args:
            task_key: 任务标识（如 "product_in_city"）
            progress_data: 进度数据
            
        Returns:
            bool: 是否保存成功
        """
        try:
            progress_file = self._get_progress_file(task_key)
            data = {
                'task_key': task_key,
                'saved_at': datetime.now().isoformat(),
                **progress_data
            }
            with open(progress_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"进度已保存: {progress_file}")
            return True
        except Exception as e:
            print(f"保存进度失败: {e}", file=sys.stderr)
            return False
    
    def load_progress(self, task_key: str) -> dict | None:
        """
        加载进度
        
        Args:
            task_key: 任务标识
            
        Returns:
            dict | None: 进度数据，如果不存在则返回 None
        """
        try:
            progress_file = self._get_progress_file(task_key)
            if os.path.exists(progress_file):
                with open(progress_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                print(f"已加载进度: {progress_file}")
                return data
        except Exception as e:
            print(f"加载进度失败: {e}", file=sys.stderr)
        return None
    
    def clear_progress(self, task_key: str) -> bool:
        """
        清除进度
        
        Args:
            task_key: 任务标识
            
        Returns:
            bool: 是否清除成功
        """
        try:
            progress_file = self._get_progress_file(task_key)
            if os.path.exists(progress_file):
                os.remove(progress_file)
                print(f"进度已清除: {progress_file}")
            return True
        except Exception as e:
            print(f"清除进度失败: {e}", file=sys.stderr)
            return False
    
    def has_progress(self, task_key: str) -> bool:
        """检查是否有保存的进度"""
        progress_file = self._get_progress_file(task_key)
        return os.path.exists(progress_file)


# 全局进度管理器
_progress_manager = ProgressManager()


# 生产环境禁用调试高亮功能，减少性能开销
# def highlight_element(driver, element, color="red", border_width="3px", duration=0.5):
#     """高亮显示元素，用于调试和可视化"""
#     pass

# def highlight_element_keep(driver, element, color="red", border_width="3px"):
#     """高亮显示元素并保持（不恢复原样式）"""
#     pass


def wait_for_element(driver, selector, timeout=5, condition=EC.presence_of_element_located):
    """智能等待元素出现，可指定等待条件"""
    try:
        element = WebDriverWait(driver, timeout).until(
            condition((By.CSS_SELECTOR, selector))
        )
        return element
    except Exception as e:
        print(f"未找到元素 {selector}: {e}", file=sys.stderr)
        return None

def wait_for_page_load(driver, timeout=10):
    """等待页面完全加载"""
    try:
        WebDriverWait(driver, timeout).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        return True
    except Exception as e:
        print(f"页面加载超时: {e}", file=sys.stderr)
        return False

def wait_for_network_idle(driver, timeout=15):
    """等待网络请求完成（需要Chrome DevTools Protocol支持）"""
    try:
        # 检查浏览器是否支持Network API
        if hasattr(driver, 'execute_cdp_cmd'):
            # 启用网络监控
            driver.execute_cdp_cmd('Network.enable', {})
            
            # 等待网络空闲（500ms内无请求）
            start_time = time.time()
            while time.time() - start_time < timeout:
                requests = driver.execute_cdp_cmd('Network.getAllRequests', {})
                # 检查是否有进行中的请求
                has_in_flight = any(req.get('status') == 'pending' for req in requests)
                if not has_in_flight:
                    # 等待500ms确认网络空闲
                    time.sleep(0.5)
                    # 再次检查
                    requests = driver.execute_cdp_cmd('Network.getAllRequests', {})
                    has_in_flight = any(req.get('status') == 'pending' for req in requests)
                    if not has_in_flight:
                        driver.execute_cdp_cmd('Network.disable', {})
                        return True
                time.sleep(1)
            driver.execute_cdp_cmd('Network.disable', {})
    except Exception as e:
        print(f"网络空闲等待失败: {e}", file=sys.stderr)
    # 如果CDP不可用或失败，回退到页面加载完成等待
    return wait_for_page_load(driver, timeout)

def scroll_and_load_more(driver, max_scrolls=50, scroll_delay=1, target_count=500):
    """
    优化后的滚动加载函数
    
    Features:
    - 使用 Set 数据结构自动去重 (Property 10)
    - 连续无新链接计数器（5次才停止）
    - 页面底部检测
    - 集成结构化日志记录
    """
    business_links = set()  # 使用 set 避免重复链接 (Property 10: Set-Based URL Deduplication)
    no_new_links_count = 0  # 连续无新链接计数器
    max_no_new_links = 5  # 连续5次无新链接才停止
    
    # 优化：缓存选择器，避免重复编译
    link_selector = 'a[role="link"][aria-label], a.hfpxzc, a[href*="/maps/place/"]'
    
    # 页面底部检测标识
    end_markers = [
        "//div[contains(text(), '没有更多结果')]",
        "//div[contains(text(), 'No more results')]",
        "//div[contains(text(), \"You've reached the end\")]",
        "//span[contains(text(), '没有更多结果')]",
        "//span[contains(text(), 'No more results')]"
    ]
    
    def is_at_bottom():
        """检测是否到达滚动区域底部"""
        for marker in end_markers:
            try:
                driver.find_element(By.XPATH, marker)
                return True
            except:
                pass
        return False
    
    # 定位左侧商家列表的滚动区域
    scrollable_area = wait_for_element(driver, 'div[role="feed"], div[aria-label*="results"], div.m6QErb[style*="overflow: auto"], div[style*="overflow-y: scroll"]')
    if not scrollable_area:
        _logger.log_warning("未找到左侧滚动区域，尝试整个页面滚动")
        print("未找到左侧滚动区域，尝试整个页面滚动")
        scrollable_area = driver.find_element(By.TAG_NAME, "body")
    
    # 优化：提取链接的辅助函数，减少重复代码
    def extract_hrefs(links):
        """从链接元素列表中提取href并添加到集合中"""
        hrefs = set()
        for link in links:
            href = link.get_attribute('href')
            if href:
                hrefs.add(href)
        return hrefs
    
    # 初始化链接集合
    initial_links = driver.find_elements(By.CSS_SELECTOR, link_selector)
    business_links.update(extract_hrefs(initial_links))
    current_link_count = len(business_links)
    
    _logger.log_progress(current_link_count, target_count, f"初始链接数: {current_link_count}")
    
    for i in range(max_scrolls):
        # 检查是否应该停止爬取
        if should_stop_extraction():
            print("收到停止信号，停止滚动加载")
            break
            
        # 记录滚动前的链接数量
        before_count = len(business_links)
        
        # 获取当前所有链接
        current_links = driver.find_elements(By.CSS_SELECTOR, link_selector)
        business_links.update(extract_hrefs(current_links))
        current_link_count = len(business_links)
        
        print(f"滚动 {i + 1}/{max_scrolls} - 当前唯一商家链接数量: {current_link_count}")

        # 发送滚动状态给前端
        progress = int((i + 1) / max_scrolls * 50)  # 滚动阶段占前 50% 进度
        yield progress, None, None, f"正在滚动页面 ({i + 1}/{max_scrolls})，已找到 {current_link_count} 个商家链接"

        # 检查是否达到目标数量
        if current_link_count >= target_count:
            _logger.log_progress(current_link_count, target_count, f"已达到目标条数 {target_count}")
            print(f"已达到或超过目标条数 {target_count}，停止滚动")
            break
        
        # 检查是否到达页面底部
        if is_at_bottom():
            _logger.log_progress(current_link_count, target_count, "检测到页面底部")
            print("检测到页面底部，停止滚动")
            break

        # 执行滚动
        driver.execute_script("arguments[0].scrollTop += arguments[0].offsetHeight;", scrollable_area)
        
        # 等待新内容加载
        time.sleep(scroll_delay)
        
        # 滚动后获取新链接
        after_scroll_links = driver.find_elements(By.CSS_SELECTOR, link_selector)
        business_links.update(extract_hrefs(after_scroll_links))
        after_count = len(business_links)
        
        # 检查是否有新链接
        if after_count == before_count:
            no_new_links_count += 1
            print(f"无新链接 ({no_new_links_count}/{max_no_new_links})")
            
            # 连续多次无新链接才停止
            if no_new_links_count >= max_no_new_links:
                _logger.log_progress(after_count, target_count, f"连续{max_no_new_links}次无新链接")
                print(f"连续{max_no_new_links}次无新链接，停止滚动")
                break
        else:
            # 有新链接，重置计数器
            no_new_links_count = 0
            current_link_count = after_count

    # 转换为列表并截取目标数量
    business_links = list(business_links)[:target_count]
    _logger.log_extraction(driver.current_url, len(business_links), 0)
    print(f"滚动完成，最终找到 {len(business_links)} 个唯一商家链接")
    yield 50, None, business_links, "滚动完成"

def extract_single_business_info(driver):
    results = []
    try:
        # 移除固定等待，使用智能等待确保页面加载
        name_elem = wait_for_element(driver, 'h1.DUwDvf', timeout=10)
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

def navigate_to_city_and_search(driver, city, product):
    """
    两步搜索：先定位到城市，再搜索商品
    
    修复：增加城市定位等待时间，确保地图完全定位后再搜索商品
    """
    print(f"开始两步搜索：城市={city}, 商品={product}")
    
    # 第一步：打开 Google Maps 并搜索城市
    yield 5, None, None, f"正在打开 Google Maps..."
    driver.get("https://www.google.com/maps")
    
    # 使用智能等待页面加载完成
    wait_for_page_load(driver)
    
    # 等待搜索框出现（Google Maps 2026年版更新：使用 name="q" 代替旧的 #searchboxinput）
    search_box = wait_for_element(driver, 'input[name="q"]', timeout=15, condition=EC.element_to_be_clickable)
    if not search_box:
        yield 0, None, None, "未找到 Google Maps 搜索框"
        return False
    
    # 第二步：输入城市名称并搜索
    yield 8, None, None, f"正在搜索城市: {city}..."
    search_box.clear()
    search_box.send_keys(city)
    search_box.send_keys(Keys.ENTER)
    
    # 等待搜索结果加载和网络空闲
    wait_for_network_idle(driver)
    
    # 关键修复：等待地图完全定位到城市
    yield 10, None, None, f"正在等待地图定位到 {city}..."
    
    # 等待地图视图更新（检测URL变化或地图移动完成）
    time.sleep(3)  # 基础等待，让地图开始移动
    
    # 等待地图稳定（检测地图是否停止移动）
    try:
        # 等待地图canvas或视图稳定
        WebDriverWait(driver, 10).until(
            lambda d: d.execute_script("""
                // 检查地图是否加载完成
                var canvas = document.querySelector('canvas');
                if (canvas) return true;
                var mapDiv = document.querySelector('div[aria-label*="Map"]');
                return mapDiv !== null;
            """)
        )
        # 额外等待确保地图动画完成
        time.sleep(2)
    except Exception as e:
        print(f"等待地图定位时出现警告: {e}")
        time.sleep(3)  # 回退到固定等待
    
    yield 12, None, None, f"地图已定位到 {city}，准备搜索商品..."
    
    # 第三步：清空搜索框，输入商品名称
    yield 15, None, None, f"正在搜索: {city} 的 {product}..."
    search_box = wait_for_element(driver, 'input[name="q"]', timeout=15, condition=EC.element_to_be_clickable)
    if search_box:
        search_box.clear()
        # 输入 "商品 in 城市" 格式，更精确定位
        search_query = f"{product} in {city}"
        search_box.send_keys(search_query)
        search_box.send_keys(Keys.ENTER)
        
        # 等待搜索结果加载和网络空闲
        wait_for_network_idle(driver)
    
    yield 20, None, None, f"搜索完成，正在加载 {city} 的 {product} 结果..."
    return True


def calculate_retry_delay(attempt: int, base_delay: float = 1.0) -> float:
    """
    计算重试延迟时间（指数退避）
    
    Args:
        attempt: 尝试次数（从1开始）
        base_delay: 基础延迟时间（秒）
        
    Returns:
        float: 延迟时间（秒）
    """
    return base_delay * (2 ** (attempt - 1))


def extract_business_detail_with_retry(driver, link_href, max_retries=3):
    """
    使用重试机制提取商家详情
    
    Features:
    - 直接URL导航替代点击
    - 多重重试机制（3次）
    - 指数退避策略（1s, 2s, 4s）
    - 集成智能等待策略
    - 集成请求限流器
    
    Args:
        driver: WebDriver实例
        link_href: 商家详情页URL
        max_retries: 最大重试次数
        
    Returns:
        tuple: (business_data, error_message)
    """
    last_error = None
    
    for attempt in range(1, max_retries + 1):
        try:
            # 应用请求限流
            wait_time = _rate_limiter.wait_if_needed()
            if wait_time > 0:
                _logger.log_request(link_href, 200, wait_time)
            
            # 直接URL导航替代点击（更可靠）
            driver.get(link_href)
            
            # 使用智能等待策略
            if not _smart_wait.wait_for_page_load(driver, timeout=10):
                raise Exception("页面加载超时")
            
            _smart_wait.wait_for_network_idle(driver, timeout=8)
            
            # 等待商家名称元素出现
            # 优化：增强名称提取策略，增加 fallback
            try:
                name_elem = _smart_wait.wait_for_element(driver, 'h1.DUwDvf', timeout=10)
                if name_elem:
                    current_name = name_elem.text.strip()
                else:
                    raise Exception("Element not found")
            except Exception:
                # Fallback: 尝试从页面标题提取 (通常格式为 "Name - Google Maps")
                page_title = driver.title
                if " - Google Maps" in page_title:
                    current_name = page_title.split(" - Google Maps")[0].strip()
                else:
                    # 最后尝试：查找任何 h1
                    h1s = driver.find_elements(By.TAG_NAME, "h1")
                    if h1s:
                        current_name = h1s[0].text.strip()
                    else:
                        raise Exception("无法提取商家名称")

            if not current_name:
                raise Exception("商家名称为空")
            
            business_data = {'name': current_name, 'website': None, 'phones': []}
            
            # 提取网站
            website_elem = _smart_wait.wait_for_element(
                driver, 
                'a[aria-label*="Website:"], a[data-item-id="authority"]', 
                timeout=3
            )
            if website_elem:
                business_data['website'] = website_elem.get_attribute('href')
            else:
                # 备用选择器
                website_elem = _smart_wait.wait_for_element(
                    driver, 
                    'a[href^="http"]:not([href*="google.com"])', 
                    timeout=2
                )
                if website_elem:
                    business_data['website'] = website_elem.get_attribute('href')
            
            # 提取电话
            phone_elem = _smart_wait.wait_for_element(
                driver, 
                'button[data-item-id^="phone"], div[aria-label*="Phone:"]', 
                timeout=3
            )
            
            phone_text_found = ""
            if phone_elem:
                phone_text_found = phone_elem.text.strip()
            else:
                # 备用选择器
                backup_phone_elem = _smart_wait.wait_for_element(
                    driver,
                    'div.rogA2c span.google-symbols[aria-hidden="true"] + div.Io6YTe',
                    timeout=2
                )
                if backup_phone_elem:
                    phone_text_found = backup_phone_elem.text.strip()
            
            # 使用正则清洗和提取电话号码，提高精准度
            if phone_text_found:
                # 匹配格式如: +1 234-567-8900, (02) 1234 5678, 0912 345 678
                # 至少包含7位数字
                found_phones = re.findall(r'(?:\+?\d{1,3}[- ]?)?\(?\d{2,4}\)?[- ]?\d{3,4}[- ]?\d{3,4}', phone_text_found)
                if found_phones:
                    # 再次过滤，确保去除太短的匹配
                    valid_phones = [p for p in found_phones if len(re.sub(r'\D', '', p)) >= 7]
                    if valid_phones:
                        # 通常取最长的一个或者是第一个
                        business_data['phones'].extend(valid_phones)
                else:
                     # Fallback: 保留原来的简单清洗逻辑作为兜底
                     simple_phone = ''.join(c for c in phone_text_found if c.isdigit() or c == '+')
                     if len(simple_phone) >= 8:
                         business_data['phones'].append(simple_phone)

            business_data['phones'] = list(set(business_data['phones']))
            
            # 记录成功
            _rate_limiter.record_success()
            _logger.log_extraction(link_href, 1, 0)
            
            return business_data, None
            
        except Exception as e:
            last_error = str(e)
            _logger.log_error(e, {'url': link_href, 'attempt': attempt})
            
            if attempt < max_retries:
                # 指数退避等待
                delay = calculate_retry_delay(attempt)
                print(f"提取失败 (尝试 {attempt}/{max_retries}): {e}，{delay}秒后重试")
                time.sleep(delay)
            else:
                # 记录封禁
                if _rate_limiter.record_block():
                    print("连续多次失败，暂停60秒...")
                    _rate_limiter.pause_for_block()
    
    return None, last_error


def extract_business_info(driver, search_url, limit=500, remember_position=False, city=None, product=None):
    """
    提取商家信息（优化版）
    
    Features:
    - 直接URL导航替代点击
    - 多重重试机制（3次）
    - 指数退避策略（1s, 2s, 4s）
    - 集成智能等待策略
    - 集成请求限流器
    - 关键错误时自动保存进度
    - 支持从保存点恢复
    
    如果提供了 city 和 product，则使用两步搜索（先定位城市再搜索商品）
    否则使用传统的 URL 直接访问方式
    """
    start_index = 0
    task_key = None
    recovered_results = []
    recovered_links = []
    
    # 新模式：城市 + 商品两步搜索
    if city and product:
        print(f"使用两步搜索模式：城市={city}, 商品={product}")
        task_key = f"{product}_in_{city}"
        
        # 检查是否有保存的进度可以恢复
        saved_progress = _progress_manager.load_progress(task_key)
        if saved_progress:
            print(f"发现保存的进度，保存时间: {saved_progress.get('saved_at')}")
            start_index = saved_progress.get('current_index', 0)
            recovered_results = saved_progress.get('results', [])
            recovered_links = saved_progress.get('business_links', [])
            print(f"从索引 {start_index} 恢复，已有 {len(recovered_results)} 条结果")
            yield 5, None, None, f"从保存点恢复，已有 {len(recovered_results)} 条数据"
        elif remember_position:
            saved_position = db_module.get_last_position(task_key)
            start_index = saved_position if saved_position is not None else 0
            print(f"记住位置已启用，从索引 {start_index} 开始提取。")
            limit = limit + start_index
        
        # 如果没有恢复的链接，执行两步搜索
        if not recovered_links:
            for progress, current, data, message in navigate_to_city_and_search(driver, city, product):
                yield progress, current, data, message
                if data is False:  # 搜索失败
                    return
    else:
        # 旧模式：直接访问 URL
        print(f"正在访问 URL: {search_url}，目标提取数量: {limit}，记住位置: {remember_position}")
        
        if remember_position and search_url:
            saved_position = db_module.get_last_position(search_url)
            start_index = saved_position if saved_position is not None else 0
            print(f"记住位置已启用，从索引 {start_index} 开始提取。")
            limit = limit + start_index
        
        try:
            # 应用请求限流
            _rate_limiter.wait_if_needed()
            
            driver.get(search_url)
            # 使用智能等待策略
            _smart_wait.wait_for_page_load(driver)
            _smart_wait.wait_for_network_idle(driver)
        except Exception as e:
            print(f"访问 URL 失败: {e}", file=sys.stderr)
            _logger.log_error(e, {'url': search_url})
            yield 0, None, None, f"访问 URL 失败: {e}"
            return

        if search_url and "/place/" in search_url:
            print("检测到单个商家页面，直接提取信息...")
            results, message = extract_single_business_info(driver)
            yield 50, None, None, "正在提取单个商家数据"
            yield 100, None, results[0] if results else None, message
            return

    # 如果有恢复的链接，使用恢复的链接；否则滚动加载
    if recovered_links:
        business_links = recovered_links
        print(f"使用恢复的 {len(business_links)} 个商家链接")
        yield 50, None, None, f"使用恢复的 {len(business_links)} 个商家链接"
    else:
        print("开始滚动页面以加载更多商家...")
        business_links = []
        # 优化：减少滚动延迟时间，从3秒减少到1秒
        for progress, _, data, message in scroll_and_load_more(driver, max_scrolls=50, scroll_delay=1, target_count=limit):
            if data is not None and isinstance(data, list):
                business_links = data  # 收集滚动完成的链接列表
            yield progress, None, None, message

    if not business_links:
        print("未找到任何商家链接")
        _logger.log_warning("未找到任何商家链接")
        yield 100, None, None, "未找到任何商家链接"
        return

    # 使用恢复的结果或初始化空列表
    results = recovered_results.copy() if recovered_results else []
    total = len(business_links)
    failed_count = 0
    consecutive_failures = 0  # 连续失败计数
    max_consecutive_failures = 5  # 连续失败阈值，触发进度保存
    
    print(f"共有 {total} 个商家链接可供提取，从索引 {start_index} 开始")
    _logger.log_progress(len(results), total, f"开始提取 {total} 个商家")
    
    # 优化：批量保存位置，减少数据库操作次数
    position_save_interval = 10  # 每10个商家保存一次位置
    
    def save_critical_progress(current_idx, reason):
        """保存关键进度（用于错误恢复）"""
        if task_key:
            progress_data = {
                'current_index': current_idx,
                'results': results,
                'business_links': business_links,
                'failed_count': failed_count,
                'reason': reason
            }
            _progress_manager.save_progress(task_key, progress_data)
            print(f"关键进度已保存: {reason}")
    
    try:
        for i, link_href in enumerate(business_links[start_index:]):
            current_index = start_index + i
            
            # 检查是否应该停止爬取
            if should_stop_extraction():
                print(f"收到停止信号，已提取 {len(results)} 条数据")
                save_critical_progress(current_index, "用户手动停止")
                yield 100, None, None, f"爬取已停止，已保存 {len(results)} 条数据"
                return
            
            if len(results) >= limit:
                print(f"已提取 {limit} 条数据，停止提取")
                break

            # 发送提取状态
            progress = int(50 + (current_index + 1) / total * 50) if total > 0 else 50
            yield progress, None, None, f"正在提取数据 ({current_index + 1}/{total})"

            # 使用重试机制提取商家详情
            business_data, error = extract_business_detail_with_retry(driver, link_href, max_retries=3)
            
            if business_data:
                # 检查是否重复
                if results and business_data['name'] == results[-1]['name']:
                    print(f"重复提取同一商家: {business_data['name']}，跳过")
                    continue
                
                # 添加 city 和 product 字段到商家数据
                if city:
                    business_data['city'] = city
                if product:
                    business_data['product'] = product
                
                results.append(business_data)
                consecutive_failures = 0  # 重置连续失败计数
                print(f"成功提取 {business_data['name']} 的信息")
                yield progress, business_data['name'], business_data, f"成功提取: {business_data['name']}"
            else:
                failed_count += 1
                consecutive_failures += 1
                print(f"提取 {link_href} 失败: {error}")
                _logger.log_extraction(link_href, 0, 1)
                
                # 连续失败达到阈值，保存进度
                if consecutive_failures >= max_consecutive_failures:
                    save_critical_progress(current_index, f"连续 {consecutive_failures} 次失败")
                    yield progress, None, None, f"警告: 连续 {consecutive_failures} 次失败，已保存进度"
                    consecutive_failures = 0  # 重置计数，继续尝试

            # 批量保存位置
            if remember_position and (current_index + 1) % position_save_interval == 0:
                position_key = task_key if task_key else search_url
                db_module.save_last_position(position_key, current_index + 1)
                print(f"已保存当前位置: {current_index + 1}")
                
    except Exception as e:
        # 关键错误时保存进度
        print(f"发生关键错误: {e}", file=sys.stderr)
        _logger.log_error(e, {'task_key': task_key, 'current_index': current_index})
        save_critical_progress(current_index, f"关键错误: {str(e)}")
        yield 100, None, None, f"发生错误，进度已保存: {str(e)}"
        raise
    
    # 提取完成，清除进度文件
    if task_key:
        _progress_manager.clear_progress(task_key)

    # 执行数据完整性验证
    validator = DataIntegrityValidator(expected_count=limit)
    validation_report = validator.validate_extraction(results)
    
    # 生成验证摘要
    summary = validator.generate_summary(validation_report)
    print(summary)
    _logger.log_progress(
        len(results), 
        total, 
        f"提取完成: 成功 {len(results)}, 失败 {failed_count}, 质量评分 {validation_report.quality_score:.1f}/100"
    )

    # 生成爬取报告
    yield 100, None, {
        'results': results,
        'validation': validation_report.to_dict()
    }, f"数据提取完成: 成功 {len(results)} 条, 失败 {failed_count} 条, 质量评分 {validation_report.quality_score:.1f}/100"