import zipfile
import os
import sys
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from config import CHROME_BINARY, CHROMEDRIVER_PATH, OUTPUT_DIR


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
    # chrome_options.add_argument("--headless") # 本地调试可注释掉，看效果
    # chrome_options.add_argument("--headless=new") # 推荐使用新版 headless 模式 (已注释，方便本地调试观看)
    # chrome_options.add_argument("--disable-gpu")  # Mac 上不需要
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--ignore-certificate-errors")
    # chrome_options.add_argument("--disable-webgl")  # 可能导致白屏
    chrome_options.add_argument("--start-maximized")
    
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
