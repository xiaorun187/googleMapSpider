import sys
import time
import re
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from db import save_business_data_to_db  # 导入数据库保存函数
from facebook_email_fetcher import extract_single_facebook_email_info


def wait_for_element(driver, selector, timeout=5):
    try:
        element = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, selector))
        )
        return element
    except Exception as e:
        print(f"未找到元素 {selector}: {e}", file=sys.stderr)
        return None

def scroll_page(driver, scroll_times=3, scroll_delay=0.5):
    """滚动页面以加载动态内容，减少等待时间"""
    for i in range(scroll_times):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        # 使用更短的延迟时间，或考虑使用智能等待替代固定延迟
        time.sleep(scroll_delay)

def is_valid_email(email):
    """验证是否为有效邮箱，排除图片文件名等无效项"""
    # 首先检查邮箱格式是否有效
    if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email):
        return False
    
    # 检查邮箱长度
    if len(email) > 254:
        return False
    
    email_lower = email.lower()
    
    # 分离用户名和域名
    username, domain = email_lower.split('@')
    
    # 检查用户名是否以无效扩展名结尾
    invalid_extensions = ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg')
    if any(username.endswith(ext) for ext in invalid_extensions):
        return False
    
    # 检查邮箱中是否包含无效模式
    invalid_patterns = [r'\d+x\d*', r'logo', r'image', r'img']
    if any(re.search(pattern, email_lower) for pattern in invalid_patterns):
        return False
    
    return True

def extract_contact_info(driver, business_data_list):
    """优化后的联系方式提取函数，减少DOM查询次数和等待时间"""
    total = len(business_data_list)
    
    # 优化：预编译正则表达式，避免重复编译
    email_pattern = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
    phone_pattern = re.compile(r"(\+?\d{1,4}[\s.-]?)?(\(?\d{2,4}\)?[\s.-]?)?\d{3,4}[\s.-]?\d{4,6}|\d{8,14}")
    
    for i, business in enumerate(business_data_list):
        name = business['name']
        website = business.get('website')
        if not website:
            print(f"{name} 无网站，跳过联系方式提取")
            yield i, name, business, f"{name} 无网站，跳过"
            continue

        try:
            print(f"访问网站: {website} 以提取联系方式")
            driver.get(website)
            
            # 优化：减少等待时间，使用更高效的等待条件
            try:
                WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
            except Exception:
                print(f"等待 {website} 加载超时，跳过")
                yield i, name, business, f"访问 {website} 超时，跳过"
                continue
            
            # 优化：减少滚动次数和等待时间
            scroll_page(driver, scroll_times=2, scroll_delay=0.5)

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
            # 优化：批量保存数据到数据库，减少数据库操作次数
            print(f"准备保存 {name} 的完整数据: {business}")
            
            # 尝试保存数据到数据库
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    save_business_data_to_db([business])
                    print(f"已将 {name} 的完整数据保存到数据库")
                    break
                except Exception as db_error:
                    print(f"保存 {name} 的数据到数据库失败 (尝试 {attempt + 1}/{max_retries}): {db_error}", file=sys.stderr)
                    if attempt < max_retries - 1:
                        time.sleep(1)  # 减少重试等待时间
                    else:
                        print(f"保存 {name} 的数据最终失败", file=sys.stderr)

            print(f"成功提取 {name} 的联系方式: {business}")
            yield progress, name, business, f"成功提取 {name} 的联系方式"

        except Exception as e:
            print(f"提取 {name} 的联系方式时出错: {e}", file=sys.stderr)
            yield progress, name, business, f"提取 {name} 的联系方式失败: {e}"