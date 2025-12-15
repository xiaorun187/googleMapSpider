import zipfile
import os
import sys
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
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
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.6998.165 Safari/537.36")
    chrome_options.add_argument("window-size=1920,3000")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--ignore-certificate-errors")
    chrome_options.add_argument("--disable-webgl")  # 禁用 WebGL
    chrome_options.add_argument("--disable-accelerated-2d-canvas")  # 禁用 2D 加速
    chrome_options.add_argument("--disable-accelerated-video-decode")  # 禁用视频解码加速
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

    service_obj = Service(CHROMEDRIVER_PATH)
    driver = webdriver.Chrome(service=service_obj, options=chrome_options)
    return driver, proxy_info