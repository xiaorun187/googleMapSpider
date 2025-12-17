import os
import sys

# 编码设置
OUTPUT_ENCODING = 'utf-8'
ERRORS = 'replace'

# Flask 配置
SECRET_KEY = 'your-secret-key'  # 请替换为安全的密钥
CORS_ALLOWED_ORIGINS = "*"
PASSWORD='V000000008954'
# 文件路径
OUTPUT_DIR = 'output'

# Chrome 配置 (支持环境变量覆盖，并尝试自动检测)
if os.name == 'nt':  # Windows
    CHROME_BINARY = os.environ.get('CHROME_BIN', r"C:\Program Files\Google\Chrome\Application\chrome.exe")
    CHROMEDRIVER_PATH = os.environ.get('CHROMEDRIVER_PATH', r"C:\chromedriver\chromedriver.exe")
else:  # Linux/Mac
    # Mac 默认路径通常是: /Applications/Google Chrome.app/Contents/MacOS/Google Chrome
    # Linux (Docker) 默认路径通常是: /usr/bin/google-chrome
    if sys.platform == 'darwin':
        CHROME_BINARY = os.environ.get('CHROME_BIN', r"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
        # Mac ARM64 使用 webdriver-manager 下载的 chromedriver
        CHROMEDRIVER_PATH = os.environ.get('CHROMEDRIVER_PATH', "/Users/hanglu/.wdm/drivers/chromedriver/mac64/143.0.7499.146/chromedriver-mac-arm64/chromedriver")
    else:
        CHROME_BINARY = os.environ.get('CHROME_BIN', "/usr/bin/google-chrome")
        CHROMEDRIVER_PATH = os.environ.get('CHROMEDRIVER_PATH', "/usr/local/bin/chromedriver")
# 数据库配置
# 项目使用SQLite数据库，无需额外配置
# 数据库文件路径: business.db (在项目根目录)
# 创建输出目录
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)
