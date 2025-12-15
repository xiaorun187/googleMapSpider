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
    else:
        CHROME_BINARY = os.environ.get('CHROME_BIN', "/usr/bin/google-chrome")
    
    CHROMEDRIVER_PATH = os.environ.get('CHROMEDRIVER_PATH', "/usr/local/bin/chromedriver")
# MySQL 配置
DB_CONFIG = {
    'host': 'vip3.xiaomiqiu123.top',
    'user': 'google_maps',
    'password': 'yun@google_maps',
    'database': 'google_maps',
    'raise_on_warnings': True,
    'port': 40594,  # 添加端口号
    'ssl_disabled': True,
    'connect_timeout': 120
}
# 创建输出目录
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)
