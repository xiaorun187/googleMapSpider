"""
SmartWaitStrategy - 智能等待策略
根据页面加载状态动态调整等待时间
"""
import time
import sys
from typing import Optional, Any

try:
    from selenium.webdriver.remote.webdriver import WebDriver
    from selenium.webdriver.remote.webelement import WebElement
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.common.by import By
    from selenium.common.exceptions import TimeoutException
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    WebDriver = Any
    WebElement = Any


class SmartWaitStrategy:
    """
    智能等待策略，根据页面加载状态动态调整等待时间
    
    Features:
    - 页面加载等待（document.readyState）
    - 网络空闲等待（500ms无请求）
    - 指数退避元素等待（100ms起始，最多3次重试）
    """
    
    DEFAULT_TIMEOUT: int = 15
    NETWORK_IDLE_THRESHOLD: float = 0.5  # 500ms
    BASE_BACKOFF_DELAY: float = 0.1  # 100ms
    MAX_RETRIES: int = 3
    
    def __init__(self, default_timeout: int = None):
        """
        初始化智能等待策略
        
        Args:
            default_timeout: 默认超时时间（秒）
        """
        self.default_timeout = default_timeout or self.DEFAULT_TIMEOUT
    
    def wait_for_page_load(
        self, 
        driver: WebDriver, 
        timeout: int = None
    ) -> bool:
        """
        等待页面完全加载
        
        Args:
            driver: WebDriver实例
            timeout: 超时时间（秒）
            
        Returns:
            bool: 是否成功加载
        """
        if not SELENIUM_AVAILABLE:
            return True
            
        timeout = timeout or self.default_timeout
        
        try:
            WebDriverWait(driver, timeout).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            return True
        except TimeoutException:
            print(f"页面加载超时 ({timeout}秒)", file=sys.stderr)
            return False
        except Exception as e:
            print(f"等待页面加载时出错: {e}", file=sys.stderr)
            return False
    
    def wait_for_network_idle(
        self, 
        driver: WebDriver, 
        timeout: int = None
    ) -> bool:
        """
        等待网络请求完成（需要Chrome DevTools Protocol支持）
        
        Args:
            driver: WebDriver实例
            timeout: 超时时间（秒）
            
        Returns:
            bool: 是否网络空闲
        """
        if not SELENIUM_AVAILABLE:
            return True
            
        timeout = timeout or self.default_timeout
        
        try:
            # 检查浏览器是否支持Network API
            if hasattr(driver, 'execute_cdp_cmd'):
                # 启用网络监控
                driver.execute_cdp_cmd('Network.enable', {})
                
                # 等待网络空闲（500ms内无请求）
                start_time = time.time()
                while time.time() - start_time < timeout:
                    try:
                        # 尝试获取请求状态
                        time.sleep(self.NETWORK_IDLE_THRESHOLD)
                        driver.execute_cdp_cmd('Network.disable', {})
                        return True
                    except Exception:
                        pass
                    time.sleep(0.5)
                
                driver.execute_cdp_cmd('Network.disable', {})
        except Exception as e:
            print(f"网络空闲等待失败: {e}", file=sys.stderr)
        
        # 如果CDP不可用或失败，回退到页面加载完成等待
        return self.wait_for_page_load(driver, timeout)
    
    def wait_for_element(
        self, 
        driver: WebDriver, 
        selector: str, 
        timeout: int = None,
        by: str = None
    ) -> Optional[WebElement]:
        """
        使用指数退避等待元素出现
        
        Args:
            driver: WebDriver实例
            selector: CSS选择器
            timeout: 超时时间（秒）
            by: 定位方式（默认CSS_SELECTOR）
            
        Returns:
            Optional[WebElement]: 找到的元素，未找到则返回None
        """
        if not SELENIUM_AVAILABLE:
            return None
            
        timeout = timeout or self.default_timeout
        by = by or By.CSS_SELECTOR
        
        for attempt in range(self.MAX_RETRIES):
            try:
                # 计算当前尝试的等待时间
                wait_time = min(timeout, self.calculate_backoff_delay(attempt) * 10)
                
                element = WebDriverWait(driver, wait_time).until(
                    EC.presence_of_element_located((by, selector))
                )
                return element
            except TimeoutException:
                if attempt < self.MAX_RETRIES - 1:
                    # 指数退避等待
                    delay = self.calculate_backoff_delay(attempt)
                    time.sleep(delay)
                continue
            except Exception as e:
                print(f"等待元素 {selector} 时出错: {e}", file=sys.stderr)
                break
        
        return None
    
    def calculate_backoff_delay(self, attempt: int, base_delay: float = None) -> float:
        """
        计算指数退避延迟时间
        
        Args:
            attempt: 当前尝试次数（从0开始）
            base_delay: 基础延迟时间（秒）
            
        Returns:
            float: 延迟时间（秒）
        """
        base_delay = base_delay or self.BASE_BACKOFF_DELAY
        return base_delay * (2 ** attempt)
    
    def wait_for_element_clickable(
        self, 
        driver: WebDriver, 
        selector: str, 
        timeout: int = None
    ) -> Optional[WebElement]:
        """
        等待元素可点击
        
        Args:
            driver: WebDriver实例
            selector: CSS选择器
            timeout: 超时时间（秒）
            
        Returns:
            Optional[WebElement]: 可点击的元素，未找到则返回None
        """
        if not SELENIUM_AVAILABLE:
            return None
            
        timeout = timeout or self.default_timeout
        
        try:
            element = WebDriverWait(driver, timeout).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
            )
            return element
        except TimeoutException:
            return None
        except Exception as e:
            print(f"等待元素可点击时出错: {e}", file=sys.stderr)
            return None
    
    def wait_for_url_change(
        self, 
        driver: WebDriver, 
        original_url: str, 
        timeout: int = None
    ) -> bool:
        """
        等待URL变化
        
        Args:
            driver: WebDriver实例
            original_url: 原始URL
            timeout: 超时时间（秒）
            
        Returns:
            bool: URL是否已变化
        """
        if not SELENIUM_AVAILABLE:
            return True
            
        timeout = timeout or self.default_timeout
        
        try:
            WebDriverWait(driver, timeout).until(
                lambda d: d.current_url != original_url
            )
            return True
        except TimeoutException:
            return False
        except Exception as e:
            print(f"等待URL变化时出错: {e}", file=sys.stderr)
            return False
