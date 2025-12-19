import zipfile
import os
import sys
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException, InvalidSessionIdException
from webdriver_manager.chrome import ChromeDriverManager
from config import CHROME_BINARY, CHROMEDRIVER_PATH, OUTPUT_DIR


class BrowserManager:
    """
    浏览器管理器 - 实现浏览器状态监控和自动重启
    
    Features:
    - 浏览器状态监控
    - 自动重启机制
    - 崩溃恢复
    """
    
    def __init__(self, proxy=None, max_restart_attempts=3):
        self.proxy = proxy
        self.max_restart_attempts = max_restart_attempts
        self.restart_count = 0
        self.driver = None
        self.last_url = None
        self._is_healthy = False
    
    def start(self):
        """启动浏览器"""
        self.driver, proxy_info = get_chrome_driver(self.proxy)
        self._is_healthy = True
        self.restart_count = 0
        return self.driver, proxy_info
    
    def is_alive(self) -> bool:
        """检查浏览器是否存活"""
        if not self.driver:
            return False
        
        try:
            # 尝试获取当前URL来检测浏览器状态
            _ = self.driver.current_url
            return True
        except (WebDriverException, InvalidSessionIdException):
            return False
        except Exception:
            return False
    
    def check_health(self) -> bool:
        """
        检查浏览器健康状态
        
        Returns:
            bool: 浏览器是否健康
        """
        if not self.is_alive():
            self._is_healthy = False
            return False
        
        try:
            # 执行简单的JavaScript来验证浏览器响应
            self.driver.execute_script("return document.readyState")
            self._is_healthy = True
            return True
        except Exception as e:
            print(f"浏览器健康检查失败: {e}", file=sys.stderr)
            self._is_healthy = False
            return False
    
    def save_state(self):
        """保存当前状态（用于恢复）"""
        if self.driver and self.is_alive():
            try:
                self.last_url = self.driver.current_url
            except Exception:
                pass
    
    def restart(self) -> tuple:
        """
        重启浏览器
        
        Returns:
            tuple: (driver, proxy_info) 或 (None, error_message)
        """
        if self.restart_count >= self.max_restart_attempts:
            return None, f"已达到最大重启次数 ({self.max_restart_attempts})"
        
        print(f"正在重启浏览器 (尝试 {self.restart_count + 1}/{self.max_restart_attempts})...")
        
        # 保存当前状态
        self.save_state()
        
        # 关闭旧的浏览器实例
        self.quit()
        
        # 等待一段时间再重启
        time.sleep(2)
        
        try:
            self.driver, proxy_info = get_chrome_driver(self.proxy)
            self._is_healthy = True
            self.restart_count += 1
            
            # 如果有保存的URL，尝试恢复
            if self.last_url and 'google.com/maps' in self.last_url:
                try:
                    self.driver.get(self.last_url)
                    print(f"已恢复到: {self.last_url}")
                except Exception as e:
                    print(f"恢复URL失败: {e}", file=sys.stderr)
            
            return self.driver, proxy_info
        except Exception as e:
            print(f"重启浏览器失败: {e}", file=sys.stderr)
            self.restart_count += 1
            return None, str(e)
    
    def quit(self):
        """关闭浏览器"""
        if self.driver:
            try:
                self.driver.quit()
            except Exception as e:
                print(f"关闭浏览器失败: {e}", file=sys.stderr)
            finally:
                self.driver = None
                self._is_healthy = False
    
    def execute_with_recovery(self, func, *args, **kwargs):
        """
        执行操作，如果浏览器崩溃则自动恢复
        
        Args:
            func: 要执行的函数
            *args, **kwargs: 函数参数
            
        Returns:
            函数执行结果
        """
        try:
            return func(*args, **kwargs)
        except (WebDriverException, InvalidSessionIdException) as e:
            print(f"浏览器异常，尝试恢复: {e}", file=sys.stderr)
            
            # 尝试重启
            new_driver, result = self.restart()
            if new_driver:
                # 重新执行操作
                return func(*args, **kwargs)
            else:
                raise Exception(f"浏览器恢复失败: {result}")
    
    @property
    def is_healthy(self) -> bool:
        """获取健康状态"""
        return self._is_healthy


def create_proxy_auth_extension(proxy_host, proxy_port, username, password):
    manifest_json = """
    {
        "version": "1.0.0",
        "manifest_version": 2,
        "name": "Proxy Auth Extension",
        "permissions": [
            "proxy",
            "tabs",
            "unlimitedStorage",
            "storage",
            "<all_urls>",
            "webRequest",
            "webRequestBlocking"
        ],
        "background": {
            "scripts": ["background.js"]
        }
    }
    """

    background_js = f"""
    var config = {{
        mode: "fixed_servers",
        rules: {{
            singleProxy: {{
                scheme: "http",
                host: "{proxy_host}",
                port: parseInt({proxy_port})
            }},
            bypassList: ["localhost"]
        }}
    }};

    chrome.proxy.settings.set({{value: config, scope: "regular"}}, function() {{}});

    function callbackFn(details) {{
        return {{
            authCredentials: {{
                username: "{username}",
                password: "{password}"
            }}
        }};
    }}

    chrome.webRequest.onAuthRequired.addListener(
        callbackFn,
        {{urls: ["<all_urls>"]}},
        ['blocking']
    );
    """

    proxy_extension = os.path.join(OUTPUT_DIR, "proxy_auth.zip")
    with zipfile.ZipFile(proxy_extension, 'w') as zp:
        zp.writestr("manifest.json", manifest_json)
        zp.writestr("background.js", background_js)
    return proxy_extension

def get_chrome_driver(proxy=None):
    chrome_options = Options()
    # 常用配置
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    
    # 根据环境变量决定是否启用无头模式
    if os.environ.get("IS_DOCKER") == "true":
        print("Docker 环境检测: 启用无头模式 (headless=new)")
        chrome_options.add_argument("--headless=new")
    else:
        print("本地环境检测: 启用 GUI 模式 (可见窗口)")
        # chrome_options.add_argument("--headless=new") # 本地开发不启用无头模式
    
    # 基础配置
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--ignore-certificate-errors")
    chrome_options.add_argument("--start-maximized")
    
    # ============================================================================
    # 内存优化配置 (Requirements 7.1)
    # ============================================================================
    # 禁用 GPU 加速（减少内存占用）
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-software-rasterizer")
    
    # 限制缓存大小（100MB）
    chrome_options.add_argument("--disk-cache-size=104857600")
    chrome_options.add_argument("--media-cache-size=104857600")
    
    # 禁用不必要的功能以减少内存
    chrome_options.add_argument("--disable-extensions")  # 禁用扩展（代理扩展除外）
    chrome_options.add_argument("--disable-plugins")
    chrome_options.add_argument("--disable-infobars")
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_argument("--disable-popup-blocking")
    
    # 禁用图片加载（可选，大幅减少内存和带宽）
    # chrome_options.add_argument("--blink-settings=imagesEnabled=false")
    
    # 限制渲染进程数量
    chrome_options.add_argument("--renderer-process-limit=2")
    
    # 禁用后台网络服务
    chrome_options.add_argument("--disable-background-networking")
    chrome_options.add_argument("--disable-background-timer-throttling")
    chrome_options.add_argument("--disable-backgrounding-occluded-windows")
    
    # 禁用默认浏览器检查
    chrome_options.add_argument("--no-default-browser-check")
    chrome_options.add_argument("--no-first-run")
    
    # 单进程模式（减少内存，但可能影响稳定性）
    # chrome_options.add_argument("--single-process")
    
    # 禁用共享内存使用（Docker环境推荐）
    chrome_options.add_argument("--disable-features=VizDisplayCompositor")
    
    # 设置JavaScript堆内存限制
    chrome_options.add_argument("--js-flags=--max-old-space-size=512")
    
    # 显式指定 Chrome 二进制位置 (config.py 中已适配 Mac/Linux/Windows)
    if CHROME_BINARY and os.path.exists(CHROME_BINARY):
        chrome_options.binary_location = CHROME_BINARY
    
    proxy_info = None
    if proxy:
        if '@' in proxy:
            try:
                username_password, host_port = proxy.split('@')
                username, password = username_password.split(':')
                host, port = host_port.split(':')
                extension = create_proxy_auth_extension(host, port, username, password)
                # 移除禁用扩展参数以支持代理认证扩展
                args_to_remove = ['--disable-extensions']
                chrome_options._arguments = [
                    arg for arg in chrome_options._arguments 
                    if arg not in args_to_remove
                ]
                chrome_options.add_extension(extension)
                proxy_info = f"应用带认证代理: {proxy}"
                print(proxy_info)
            except ValueError as e:
                proxy_info = f"代理格式错误: {proxy}, 应为 username:password@host:port, 错误: {e}"
                print(proxy_info, file=sys.stderr)
        else:
            chrome_options.add_argument(f"--proxy-server={proxy}")
            proxy_info = f"应用无认证代理: {proxy}"
            print(proxy_info)

    # 优先使用配置的 ChromeDriver (Docker 环境或手动指定)
    if CHROMEDRIVER_PATH and os.path.exists(CHROMEDRIVER_PATH):
        try:
            print(f"使用本地 ChromeDriver: {CHROMEDRIVER_PATH}")
            service_obj = Service(CHROMEDRIVER_PATH)
            driver = webdriver.Chrome(service=service_obj, options=chrome_options)
            return driver, proxy_info
        except Exception as e:
            print(f"本地 ChromeDriver 启动失败，尝试使用 webdriver-manager: {e}")

    # 回退到 webdriver-manager 自动管理
    try:
        print("使用 webdriver-manager 自动下载驱动...")
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        return driver, proxy_info
    except Exception as e:
        print(f"Failed to initialize ChromeDriver: {e}")
        raise
