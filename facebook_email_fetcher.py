import sys
import time
import re
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from db import save_business_data_to_db, update_business_email  # 导入数据库保存和更新函数
from chrome_driver import get_chrome_driver
from db import get_facebook_non_email

def wait_for_element(driver, selector, timeout=5):
    try:
        element = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, selector))
        )
        return element
    except Exception as e:
        print(f"未找到元素 {selector}: {e}", file=sys.stderr)
        return None

def scraper_facebook_email(proxy):
    # 从数据库返回邮箱为空，且有 facebook URL 的记录
    result = get_facebook_non_email()
    for r in result:
        facebook_url = r.get('facebook')
        business_id = r.get('id')  # 获取 business ID
        if facebook_url and business_id:
            extract_business_info(proxy, facebook_url=facebook_url, business_id=business_id)
        else:
            print(f"记录 ID {r.get('id')} 没有 Facebook URL，跳过。")
def extract_single_facebook_email_info(driver, facebook_url):
    try:
        driver.get(facebook_url)
        time.sleep(3)  # 等待页面加载完成，可以适当调整
        page_source = driver.page_source
        email_pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
        emails = re.findall(email_pattern, page_source)
        return emails
    except Exception as e:
        print(f"处理 Facebook URL: {facebook_url} 时发生错误: {e}", file=sys.stderr)
        return []  # 确保始终返回列表类型
def extract_business_info(proxy, facebook_url, business_id):
    driver, proxy_info = get_chrome_driver(proxy)
    email_address = None
    try:
        driver.get(facebook_url)
        time.sleep(5)  # 等待页面加载完成，可以适当调整

        page_source = driver.page_source
        # 排除常见图片扩展名
        email_pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(?<!\.png)(?<!\.jpg)(?<!\.jpeg)(?<!\.gif)(?<!\.webp)"
        emails = re.findall(email_pattern, page_source)

        if emails:
            # 如果找到多个邮箱，可以根据一些策略选择最可能的那个
            # 这里我们简单地选择第一个找到的邮箱
            email_address = emails[0]
            print(f"从 Facebook URL: {facebook_url} 的源代码中找到邮箱地址: {email_address}")

            update_success = update_business_email(business_id, email_address)
            if update_success:
                print(f"成功更新数据库中 ID 为 {business_id} 的邮箱为: {email_address}")
            else:
                print(f"更新数据库中 ID 为 {business_id} 的邮箱失败。")
        else:
            print(f"未能从 Facebook URL: {facebook_url} 的源代码中找到邮箱地址。")

    except Exception as e:
        print(f"处理 Facebook URL: {facebook_url} 时发生错误: {e}", file=sys.stderr)
    finally:
        driver.quit()

if __name__ == '__main__':
    # 示例调用
    # 假设您已经配置好了数据库连接和 chrome_driver
    scraper_facebook_email('http://localhost:10809')