import os
import sys

# 编码设置
OUTPUT_ENCODING = 'utf-8'
ERRORS = 'replace'

# Flask 配置
SECRET_KEY = 'your-secret-key'  # 请替换为安全的密钥
CORS_ALLOWED_ORIGINS = "*"
PASSWORD='V000000008954'
MAX_CONCURRENT_TASKS = 2  # 最大并发抓取任务数

# 邮件配置
# 支持的邮箱服务：
# - Gmail: smtp.gmail.com:587 (需要应用专用密码，可能被墙)
# - QQ邮箱: smtp.qq.com:587 (需要开启SMTP服务并获取授权码)
# - 163邮箱: smtp.163.com:25 或 smtp.163.com:465 (需要开启SMTP服务并获取授权码)
# 
# 配置方法：
# 1. 在下方设置邮箱配置，或
# 2. 设置环境变量: MAIL_SERVER, MAIL_PORT, MAIL_USERNAME, MAIL_PASSWORD
#
# 获取授权码：
# - QQ邮箱: 设置 -> 账户 -> POP3/IMAP/SMTP/Exchange/CardDAV/CalDAV服务 -> 开启SMTP服务
# - 163邮箱: 设置 -> POP3/SMTP/IMAP -> 开启SMTP服务
MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
MAIL_PORT = int(os.environ.get('MAIL_PORT', '465'))  # SSL 端口，比 TLS 587 更可靠
MAIL_USERNAME = os.environ.get('MAIL_USERNAME', 'yunhongliu81@gmail.com')
MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', 'ellalaozqxsyxlus')

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
# 数据库文件路径: data/business.db
# 创建输出目录
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)
