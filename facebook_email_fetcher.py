import time
from db import save_business_data_to_db, update_business_email, get_facebook_non_email
from chrome_driver import get_chrome_driver
from utils.selenium_helpers import wait_for_element
from utils.enterprise_logger import get_logger

# 初始化日志器
_logger = get_logger('facebook-fetcher')

import re


def scraper_facebook_email(proxy):
    # 从数据库返回邮箱为空，且有 facebook URL 的记录
    result = get_facebook_non_email()
    for r in result:
        facebook_url = r.get('facebook')
        business_id = r.get('id')  # 获取 business ID
        if facebook_url and business_id:
            extract_business_info(proxy, facebook_url=facebook_url, business_id=business_id)
        else:
            _logger.log_info(f"记录 ID {r.get('id')} 没有 Facebook URL，跳过。")
def extract_single_facebook_email_info(driver, facebook_url):
    try:
        driver.get(facebook_url)
        time.sleep(3)  # 等待页面加载完成，可以适当调整
        page_source = driver.page_source
        email_pattern = r"[a-zA-Z0-9.\-_%+#]+@[a-zA-Z0-9.\-_%+#]+\.[a-zA-Z]{2,}"
        emails = re.findall(email_pattern, page_source)
        return emails
    except Exception as e:
        _logger.log_error(e, {'context': 'extract_fb_email', 'url': facebook_url})
        return []  # 确保始终返回列表类型
def extract_business_info(proxy, facebook_url, business_id):
    driver, proxy_info = get_chrome_driver(proxy)
    email_address = None
    try:
        driver.get(facebook_url)
        time.sleep(5)  # 等待页面加载完成，可以适当调整

        page_source = driver.page_source
        # 使用统一的稳健正则
        email_pattern = r"[a-zA-Z0-9.\-_%+#]+@[a-zA-Z0-9.\-_%+#]+\.[a-zA-Z]{2,}"
        emails = re.findall(email_pattern, page_source)

        if emails:
            # 如果找到多个邮箱，可以根据一些策略选择最可能的那个
            # 这里我们简单地选择第一个找到的邮箱
            email_address = emails[0]
            _logger.log_info(f"从 Facebook URL: {facebook_url} 的源代码中找到邮箱地址: {email_address}")

            update_success = update_business_email(business_id, email_address)
            if update_success:
                _logger.log_info(f"成功更新数据库中 ID 为 {business_id} 的邮箱为: {email_address}")
            else:
                _logger.log_warning(f"更新数据库中 ID 为 {business_id} 的邮箱失败。")
        else:
            _logger.log_info(f"未能从 Facebook URL: {facebook_url} 的源代码中找到邮箱地址。")

    except Exception as e:
        _logger.log_error(e, {'context': 'fb_fetch_task', 'url': facebook_url, 'id': business_id})
    finally:
        driver.quit()

if __name__ == '__main__':
    # 示例调用
    # 假设您已经配置好了数据库连接和 chrome_driver
    scraper_facebook_email('http://localhost:10809')