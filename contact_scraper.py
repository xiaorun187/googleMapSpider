import sys
import time
import re
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from db import save_business_data_to_db, save_single_business_to_db
from facebook_email_fetcher import extract_single_facebook_email_info
from scraper import should_stop_extraction

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
    """
    total = len(business_data_list)
    
    # 优化：更严格的邮箱正则，且排除常见图片/文件扩展名
    # 模式解释：
    # 1. 用户名部分: [a-zA-Z0-9._%+-]+
    # 2. @ 符号
    # 3. 域名部分: [a-zA-Z0-9.-]+
    # 4. 顶级域名: \.[a-zA-Z]{2,}
    # 5. 负向断言 (?!...): 排除以 .png, .jpg 等结尾的匹配
    email_pattern = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(?<!\.png)(?<!\.jpg)(?<!\.jpeg)(?<!\.gif)(?<!\.webp)(?<!\.svg)(?<!\.bmp)(?<!\.css)(?<!\.js)")
    
    phone_pattern = re.compile(r"(\+?\d{1,4}[\s.-]?)?(\(?\d{2,4}\)?[\s.-]?)?\d{3,4}[\s.-]?\d{4,6}|\d{8,14}")

    def is_junk_email(email):
        """过滤垃圾邮箱和误判"""
        email = email.lower().strip()
        user_part = email.split('@')[0] if '@' in email else email
        domain_part = email.split('@')[1] if '@' in email else ''
        
        # 1. 过滤常见占位符用户名
        junk_users = ['example', 'domain', 'email', 'user', 'name', 'test', 'admin', 
                      'info', 'contact', 'hello', 'support', 'sales', 'noreply', 'no-reply',
                      'webmaster', 'postmaster', 'hostmaster', 'abuse']
        # 只有当用户名完全匹配占位符时才过滤（允许 info@company.com 这种）
        if user_part in junk_users and domain_part in ['example.com', 'domain.com', 'test.com', 'email.com']:
            return True
            
        # 2. 过滤文件扩展名误判（从CSS/JS文件中提取的）
        file_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.bmp', 
                          '.css', '.js', '.woff', '.woff2', '.ttf', '.eot', '.ico',
                          '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.zip', '.rar']
        if any(email.endswith(ext) for ext in file_extensions):
            return True
        
        # 3. 过滤域名是文件扩展名的情况（如 xxx@11.css, xxx@2x.jp）
        if domain_part and '.' in domain_part:
            tld = domain_part.split('.')[-1]
            invalid_tlds = ['css', 'js', 'png', 'jpg', 'jpeg', 'gif', 'svg', 'woff', 'ttf', 'ico', 'jp', 'webp']
            if tld in invalid_tlds:
                return True
        
        # 3.5 过滤 Retina 图片命名模式（如 xxx@2x.jpg）
        if re.search(r'@[123]x\.', email):
            return True
        
        # 4. 过滤包含尺寸模式的（如 100x200）
        import re
        if re.search(r'\d{2,}x\d+', email):
            return True
        
        # 5. 过滤包含图片相关关键词的
        image_keywords = ['logo', 'image', 'img', 'icon', 'banner', 'thumb', 'avatar', 
                         'photo', 'picture', 'sprite', 'background', 'bg-']
        if any(kw in user_part for kw in image_keywords):
            return True
            
        # 6. 过滤过长或过短的
        if len(email) > 60 or len(email) < 6:
            return True
        
        # 7. 过滤用户名过短的（可能是误提取）
        if len(user_part) < 2:
            return True
        
        # 8. 过滤包含连续数字过多的（可能是ID或时间戳）
        if re.search(r'\d{8,}', user_part):
            return True
        
        # 9. 过滤明显无效的域名
        invalid_domains = ['localhost', '127.0.0.1', 'example.com', 'test.com', 
                          'domain.com', 'email.com', 'sample.com', 'yoursite.com',
                          'yourdomain.com', 'company.com', 'website.com']
        if domain_part in invalid_domains:
            return True
            
        return False
    
    # 重置批量处理器
    _batch_processor.clear()
    
    for i, business in enumerate(business_data_list):
        # 检查是否应该停止
        if should_stop_extraction():
            print("收到停止信号，停止联系方式提取")
            break
        
        # 确保business是字典类型，如果是元组则转换为字典
        if isinstance(business, tuple):
            print(f"警告: business是元组类型，尝试转换为字典")
            # 假设元组格式为 (id, name, website, city, product)
            if len(business) >= 3:
                business = {
                    'id': business[0] if len(business) > 0 else None,
                    'name': business[1] if len(business) > 1 else 'Unknown',
                    'website': business[2] if len(business) > 2 else None,
                    'city': business[3] if len(business) > 3 else None,
                    'product': business[4] if len(business) > 4 else None
                }
            else:
                print(f"错误: 元组格式不正确，跳过此记录: {business}")
                continue
        
        # 再次检查business是否为字典
        if not isinstance(business, dict):
            print(f"错误: business不是字典类型，跳过此记录: {type(business)} - {business}")
            continue
            
        name = business.get('name', 'Unknown')
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
                if is_valid_email(email) and not is_junk_email(email):
                    emails.add(email.lower())  # 统一转小写

            # 从 mailto 链接提取邮箱
            mailto_links = driver.find_elements(By.CSS_SELECTOR, 'a[href^="mailto:"]')
            for link in mailto_links:
                href = link.get_attribute('href')
                if href:
                    mailto_match = re.search(r"mailto:([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})", href)
                    if mailto_match:
                        email_candidate = mailto_match.group(1)
                        if is_valid_email(email_candidate) and not is_junk_email(email_candidate):
                            emails.add(email_candidate.lower())

            # 尝试查找多个潜在的联系页面链接
            contact_keywords = [
                'contact', '联系', 'about', '关于', 'get in touch', '联系我们',
                'support', '帮助', 'customer service', '客户服务', 'team', '团队',
                'legal', 'imprint', 'privacy', 'terms'
            ]
            
            potential_links = []
            all_links = driver.find_elements(By.TAG_NAME, 'a')
            for link in all_links:
                try:
                    href = link.get_attribute('href')
                    text = link.text.lower()
                    if href and any(kw in href.lower() or kw in text for kw in contact_keywords):
                        if href.startswith(website.rstrip('/')) or href.startswith('/'):
                            if href.startswith('/'):
                                href = website.rstrip('/') + href
                            if href not in potential_links and href != website:
                                potential_links.append(href)
                except:
                    continue
            
            # 限制遍历页面数量，避免陷入死循环或过度消耗资源
            max_subpages = 3
            for subpage_url in potential_links[:max_subpages]:
                try:
                    print(f"访问子页面: {subpage_url}")
                    driver.get(subpage_url)
                    _smart_wait.wait_for_page_load(driver, timeout=5)
                    _smart_wait.wait_for_network_idle(driver, timeout=5)
                    scroll_page(driver, scroll_times=1, scroll_delay=0.5)
                    
                    sub_text = driver.find_element(By.TAG_NAME, "body").text
                    sub_source = driver.page_source
                    
                    # 提取邮箱
                    for email in email_pattern.findall(sub_text) + email_pattern.findall(sub_source):
                        if is_valid_email(email) and not is_junk_email(email):
                            emails.add(email.lower())
                    
                    # 提取电话
                    for phone in phone_pattern.findall(sub_text):
                        if isinstance(phone, tuple): phone = phone[0]
                        clean_phone = ''.join(c for c in phone if c.isdigit() or c == '+')
                        if len(clean_phone) >= 8:
                            phones.add(clean_phone)
                            
                except Exception as e:
                    print(f"访问子页面 {subpage_url} 失败: {e}")

            # 提取电话号码（由于正则表达式可能返回元组，需要特殊处理）
            raw_phones = phone_pattern.findall(page_text) + phone_pattern.findall(page_source)
            for p in raw_phones:
                if isinstance(p, tuple): p = p[0]
                clean_phone = ''.join(c for c in p if c.isdigit() or c == '+')
                if len(clean_phone) >= 8:
                    phones.add(clean_phone)

            # 更新 business 字典
            business['emails'] = list(emails) if emails else []
            business['phones'] = list(phones) if phones else business.get('phones', [])
            
            if business['emails']:
                print(f"提取到 {name} 的邮箱: {business['emails']}")
            if business['phones']:
                print(f"提取到 {name} 的电话: {business['phones']}")
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
                
            yield progress, name, business, f"成功提取 {name} 的联系方式"
            
        except Exception as e:
            print(f"提取 {name} 联系方式时出错: {e}")
            _logger.log_extraction(website, 0, 1)
            yield i, name, business, f"提取 {name} 联系方式失败: {str(e)}"

def extract_contacts_by_ids(driver, record_ids: list):
    """
    针对指定的记录 ID 列表进行定向联系方式提取
    """
    from db import get_db_connection, release_connection
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    placeholders = ','.join(['?' for _ in record_ids])
    cursor.execute(f"SELECT id, name, website, city, product FROM business_records WHERE id IN ({placeholders})", record_ids)
    
    records = []
    for row in cursor.fetchall():
        records.append({
            'id': row[0],
            'name': row[1],
            'website': row[2],
            'city': row[3],
            'product': row[4]
        })
    
    cursor.close()
    release_connection(conn)
    
    if not records:
        print("未找到对应的记录", file=sys.stderr)
        return

    # 调用核心提取逻辑
    for progress, name, data, msg in extract_contact_info(driver, records):
        yield progress, name, data, msg