import sys
import time
import re
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from db import save_business_data_to_db
from facebook_email_fetcher import extract_single_facebook_email_info

# 导入优化模块
from validators.email_validator import EmailValidator
from validators.phone_validator import PhoneValidator
from validators.url_validator import URLValidator
from utils.smart_wait import SmartWaitStrategy
from utils.batch_processor import BatchProcessor
from utils.data_deduplicator import DataDeduplicator
from utils.structured_logger import StructuredLogger

# 初始化全局组件
_email_validator = EmailValidator()
_phone_validator = PhoneValidator()
_url_validator = URLValidator()
_smart_wait = SmartWaitStrategy()
_batch_processor = BatchProcessor(batch_size=10)
_deduplicator = DataDeduplicator()
_logger = StructuredLogger(log_dir='logs')


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

def scroll_page(driver, scroll_times=3, scroll_delay=0.5):
    """滚动页面以加载动态内容，减少等待时间"""
    for i in range(scroll_times):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        # 使用更短的延迟时间，或考虑使用智能等待替代固定延迟
        time.sleep(scroll_delay)

def is_valid_email(email):
    """
    验证是否为有效邮箱，使用 EmailValidator
    
    Features:
    - 集成 EmailValidator (Requirements 1.1, 1.2, 1.3)
    """
    result = _email_validator.validate(email)
    return result.is_valid

def extract_contact_info(driver, business_data_list):
    """
    优化后的联系方式提取函数
    
    Features:
    - 集成 EmailValidator (Requirements 1.1, 1.2, 1.3)
    - 集成 PhoneValidator (Requirements 1.4)
    - 集成 URLValidator (Requirements 1.5)
    - 集成 SmartWaitStrategy (Requirements 3.1, 3.2, 3.3)
    - 集成 BatchProcessor (Requirements 4.1, 4.4)
    - 集成 DataDeduplicator (Requirements 2.1, 2.2, 2.3)
    """
    total = len(business_data_list)
    
    # 优化：预编译正则表达式，避免重复编译
    email_pattern = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
    phone_pattern = re.compile(r"(\+?\d{1,4}[\s.-]?)?(\(?\d{2,4}\)?[\s.-]?)?\d{3,4}[\s.-]?\d{4,6}|\d{8,14}")
    
    # 重置批量处理器
    _batch_processor.clear()
    
    for i, business in enumerate(business_data_list):
        name = business['name']
        website = business.get('website')
        if not website:
            print(f"{name} 无网站，跳过联系方式提取")
            yield i, name, business, f"{name} 无网站，跳过"
            continue

        try:
            # 验证 URL 格式
            if not _url_validator.validate(website):
                print(f"{name} 的网站 URL 无效: {website}")
                yield i, name, business, f"{name} 的网站 URL 无效"
                continue
            
            print(f"访问网站: {website} 以提取联系方式")
            _logger.log_request(website, 0, 0)
            driver.get(website)
            
            # 使用智能等待策略
            if not _smart_wait.wait_for_page_load(driver, timeout=8):
                print(f"等待 {website} 页面加载超时，尝试继续")
            
            # 等待网络请求完成
            _smart_wait.wait_for_network_idle(driver, timeout=12)
            
            # 优化：滚动页面以加载动态内容
            scroll_page(driver, scroll_times=3, scroll_delay=0.5)

            progress = int((i + 1) / total * 100)
            yield progress, name, None, f"正在访问 {name} 的网站: {website}"

            # 优化：一次性获取页面内容，减少DOM查询
            body_elem = driver.find_element(By.TAG_NAME, "body")
            page_text = body_elem.text
            page_source = driver.page_source

            # 初始化联系方式
            emails = set()
            phones = set()

            # 提取 Emails 和 Phones（主页面）
            # 从文本和源代码提取邮箱
            raw_emails = email_pattern.findall(page_text) + email_pattern.findall(page_source)
            for email in raw_emails:
                if is_valid_email(email):
                    emails.add(email)

            # 从 mailto 链接提取邮箱
            mailto_links = driver.find_elements(By.CSS_SELECTOR, 'a[href^="mailto:"]')
            for link in mailto_links:
                href = link.get_attribute('href')
                if href:
                    mailto_match = re.search(r"mailto:([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})", href)
                    if mailto_match and is_valid_email(mailto_match.group(1)):
                        emails.add(mailto_match.group(1))

            # 尝试点击“联系我们”或类似链接
            contact_keywords = [
                'contact', '联系', 'about', '关于', 'get in touch', '联系我们',
                'support', '帮助', 'customer service', '客户服务'
            ]
            contact_link = None
            for keyword in contact_keywords:
                contact_link = wait_for_element(driver, f'a[href*="{keyword}"], a:contains("{keyword}")', timeout=2)
                if contact_link:
                    break
            if contact_link:
                try:
                    print(f"找到 {name} 的联系链接: {contact_link.get_attribute('href')}")
                    ActionChains(driver).move_to_element(contact_link).click().perform()
                    WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.TAG_NAME, "body"))
                    )
                    scroll_page(driver, scroll_times=2, scroll_delay=1)
                    contact_page_text = driver.find_element(By.TAG_NAME, "body").text
                    contact_page_source = driver.page_source
                    raw_emails = re.findall(email_pattern, contact_page_text) + re.findall(email_pattern, contact_page_source)
                    print(f"{name} 联系页面原始邮箱匹配: {raw_emails}")
                    for email in raw_emails:
                        if is_valid_email(email):
                            emails.add(email)
                    mailto_links = driver.find_elements(By.CSS_SELECTOR, 'a[href^="mailto:"]')
                    for link in mailto_links:
                        href = link.get_attribute('href')
                        mailto_match = re.search(r"mailto:([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})", href)
                        if mailto_match and is_valid_email(mailto_match.group(1)):
                            emails.add(mailto_match.group(1))
                    print(f"从 {name} 的联系页面提取到额外信息")
                except Exception as e:
                    print(f"点击 {name} 的联系页面失败: {e}")

            # 更新 business 字典
            business['emails'] = list(emails) if emails else []
            if business['emails']:
                print(f"提取到 {name} 的邮箱: {business['emails']}")
            else:
                print(f"未在 {name} 的网站找到邮箱")

            # 提取社交媒体和其他联系方式
            social_platforms = {
                'facebook': ('facebook.com', 'Facebook'),
                'twitter': ('twitter.com', 'Twitter'),
                'instagram': ('instagram.com', 'Instagram'),
                'linkedin': ('linkedin.com', 'LinkedIn'),
                'whatsapp': ('wa.me', 'WhatsApp'),
                'youtube': ('youtube.com', 'YouTube')
            }
            for key, (domain, label) in social_platforms.items():
                elem = wait_for_element(driver, f'a[href*="{domain}"]', timeout=2)
                business[key] = elem.get_attribute('href') if elem else None
                if not business[key]:
                    pattern = rf"(https?://(?:www\.)?{domain}/[^\s]+)"
                    urls = re.findall(pattern, page_text)
                    business[key] = urls[0] if urls else None
                if business[key]:
                    print(f"提取到 {name} 的 {label}: {business[key]}")
            if not business.get('emails') and business.get('facebook'):
                yield progress, name, business, f"未找到邮箱，开始从facebook提取 {name} "
                business['emails']=extract_single_facebook_email_info(driver,business.get('facebook'))
                yield progress, name, business, f"从facebook提取邮箱 {business['emails']} "
                
                # 从Facebook提取邮箱后立即保存到数据库
                try:
                    result = save_single_business_to_db(business)
                    if result['success']:
                        if result['action'] == 'inserted':
                            print(f"[DB] 新增记录 [{name}] ID={result['record_id']}")
                        elif result['action'] == 'updated':
                            print(f"[DB] 更新记录 [{name}] ID={result['record_id']}")
                    else:
                        print(f"[DB ERROR] 保存失败 [{name}]: {result['error']}")
                except Exception as e:
                    print(f"[DB ERROR] 保存异常 [{name}]: {e}")
            
            print(f"成功提取 {name} 的联系方式: {business}")
            _logger.log_extraction(website, 1, 0)
            
            # 立即保存到数据库
            try:
                result = save_single_business_to_db(business)
                if result['success']:
                    if result['action'] == 'inserted':
                        print(f"[DB] 新增记录 [{name}] ID={result['record_id']}")
                    elif result['action'] == 'updated':
                        print(f"[DB] 更新记录 [{name}] ID={result['record_id']}")
                else:
                    print(f"[DB ERROR] 保存失败 [{name}]: {result['error']}")
            except Exception as e:
                print(f"[DB ERROR] 保存异常 [{name}]: {e}")
            
            yield progress, name, business, f"成功提取 {name} 的联系方式并已保存到数据库"

        except Exception as e:
            _logger.log_error(e, {'name': name, 'website': website})
            print(f"提取 {name} 的联系方式时出错: {e}", file=sys.stderr)
            yield progress, name, business, f"提取 {name} 的联系方式失败: {e}"
    
    # 处理剩余的批量数据
    remaining_data = _batch_processor.flush()
    if remaining_data:
        unique_data = _deduplicator.deduplicate(remaining_data)
        try:
            save_business_data_to_db(unique_data)
            print(f"已保存剩余 {len(unique_data)} 条数据到数据库")
        except Exception as db_error:
            print(f"保存剩余数据失败: {db_error}", file=sys.stderr)
            _logger.log_error(db_error, {'batch_size': len(unique_data)})