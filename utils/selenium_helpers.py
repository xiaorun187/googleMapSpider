import sys
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException, TimeoutException
from utils.enterprise_logger import get_logger

_logger = get_logger('selenium-helpers')

class TimeoutConfig:
    """全局超时配置"""
    PAGE_LOAD = 10
    NETWORK_IDLE = 15
    ELEMENT_WAIT = 5
    ELEMENT_WAIT_SHORT = 3

def wait_for_element(driver, selector, timeout=TimeoutConfig.ELEMENT_WAIT, condition=EC.presence_of_element_located):
    """
    智能等待元素出现，可指定等待条件
    """
    try:
        element = WebDriverWait(driver, timeout).until(
            condition((By.CSS_SELECTOR, selector))
        )
        return element
    except TimeoutException:
        _logger.warn(f"等待元素超时: {selector}")
        return None
    except Exception as e:
        _logger.error(str(e), error=e, biz_context={'context': 'wait_for_element', 'selector': selector})
        return None

def wait_for_page_load(driver, timeout=TimeoutConfig.PAGE_LOAD):
    """
    等待页面完全加载
    """
    try:
        WebDriverWait(driver, timeout).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        return True
    except TimeoutException:
        _logger.warn("页面加载超时")
        return False
    except Exception as e:
        _logger.error(str(e), error=e, biz_context={'context': 'wait_for_page_load'})
        return False

def wait_for_network_idle(driver, timeout=TimeoutConfig.NETWORK_IDLE):
    """
    等待网络请求完成（需要Chrome DevTools Protocol支持）
    
    采用分层捕获异常，确保在不支持 CDP 的环境下能回退。
    """
    try:
        # 检查浏览器是否支持 Network API
        if not hasattr(driver, 'execute_cdp_cmd'):
            return wait_for_page_load(driver, timeout)
        
        # 启用网络监控
        try:
            driver.execute_cdp_cmd('Network.enable', {})
        except WebDriverException:
            return wait_for_page_load(driver, timeout)
        
        # 等待网络空闲（500ms内无请求）
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                requests = driver.execute_cdp_cmd('Network.getAllRequests', {})
                # 检查是否有进行中的请求
                has_in_flight = any(req.get('status') == 'pending' for req in requests)
                if not has_in_flight:
                    # 等待 500ms 确认网络空闲
                    time.sleep(0.5)
                    # 再次检查
                    requests = driver.execute_cdp_cmd('Network.getAllRequests', {})
                    has_in_flight = any(req.get('status') == 'pending' for req in requests)
                    if not has_in_flight:
                        try:
                            driver.execute_cdp_cmd('Network.disable', {})
                        except:
                            pass
                        return True
                time.sleep(1)
            except WebDriverException:
                # CDP 命令失败，跳出循环使用回退方案
                break
        
        # 清理
        try:
            driver.execute_cdp_cmd('Network.disable', {})
        except:
            pass
            
    except Exception as e:
        _logger.warn(f"网络空闲等待发生非预期错误: {e}")
    
    # 回退方案
    return wait_for_page_load(driver, timeout)
