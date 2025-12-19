"""
EnhancedAntiDetection - 增强的反爬规避策略
实现浏览器配置优化、隐身脚本注入和自动化标识禁用
"""
from typing import Any, List

try:
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.remote.webdriver import WebDriver
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    Options = Any
    WebDriver = Any


class EnhancedAntiDetection:
    """
    增强的反爬规避策略
    
    Features:
    - 浏览器配置优化
    - 隐身脚本注入
    - 自动化标识禁用
    - User-Agent轮换
    """
    
    # 10个常用浏览器User-Agent
    USER_AGENTS: List[str] = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
        "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0"
    ]
    
    def __init__(self):
        """初始化反爬规避组件"""
        self.ua_index = 0
        self.request_count = 0
    
    def configure_driver(self, options: Options) -> Options:
        """
        配置浏览器以规避检测
        
        Args:
            options: Chrome选项对象
            
        Returns:
            Options: 配置后的选项对象
        """
        if not SELENIUM_AVAILABLE:
            return options
        
        # 禁用自动化标识
        options.add_argument("--disable-blink-features=AutomationControlled")
        
        try:
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
        except Exception:
            pass
        
        # 设置User-Agent
        options.add_argument(f"user-agent={self.get_next_user_agent()}")
        
        # 其他反检测设置
        options.add_argument("--disable-infobars")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--no-sandbox")
        
        # 内存优化设置
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-software-rasterizer")
        options.add_argument("--disk-cache-size=1")
        options.add_argument("--media-cache-size=1")
        
        # 禁用不必要的功能
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-plugins")
        options.add_argument("--disable-images")  # 可选：禁用图片加载
        
        return options
    
    def get_next_user_agent(self) -> str:
        """
        轮换获取User-Agent
        
        Returns:
            str: User-Agent字符串
        """
        ua = self.USER_AGENTS[self.ua_index]
        self.ua_index = (self.ua_index + 1) % len(self.USER_AGENTS)
        return ua
    
    def inject_stealth_scripts(self, driver: WebDriver) -> None:
        """
        注入隐身脚本
        
        Args:
            driver: WebDriver实例
        """
        if not SELENIUM_AVAILABLE:
            return
        
        try:
            # 隐藏webdriver属性
            driver.execute_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """)
            
            # 模拟真实浏览器属性
            driver.execute_script("""
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
            """)
            
            # 模拟语言设置
            driver.execute_script("""
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en']
                });
            """)
            
            # 隐藏自动化相关属性
            driver.execute_script("""
                window.chrome = {
                    runtime: {}
                };
            """)
            
            # 模拟权限API
            driver.execute_script("""
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                        Promise.resolve({ state: Notification.permission }) :
                        originalQuery(parameters)
                );
            """)
            
        except Exception as e:
            print(f"注入隐身脚本失败: {e}")
    
    def apply_all_protections(self, driver: WebDriver) -> None:
        """
        应用所有保护措施
        
        Args:
            driver: WebDriver实例
        """
        self.inject_stealth_scripts(driver)
        self.request_count += 1
    
    def get_request_count(self) -> int:
        """
        获取请求计数
        
        Returns:
            int: 请求次数
        """
        return self.request_count
    
    def reset(self) -> None:
        """重置状态"""
        self.ua_index = 0
        self.request_count = 0
