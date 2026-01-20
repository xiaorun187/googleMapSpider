import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import os
import sys
from db import update_send_count  # 导入数据库更新函数

# 尝试从 config 导入邮件配置
try:
    from config import MAIL_SERVER, MAIL_PORT, MAIL_USERNAME, MAIL_PASSWORD
except ImportError:
    # 如果导入失败，使用默认值
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', '587'))
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', 'yunhongliu81@gmail.com')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', 'fqrfuoqpjftqxoeu')

class EmailSender:
    def __init__(self, mail_server=None, mail_port=None, mail_username=None, mail_password=None):
        """
        Initializes the EmailSender class with SMTP server details.
        
        支持的邮箱服务：
        - Gmail: smtp.gmail.com:587 (需要应用专用密码)
        - QQ邮箱: smtp.qq.com:587 (需要开启SMTP服务并获取授权码)
        - 163邮箱: smtp.163.com:25 (需要开启SMTP服务并获取授权码)
        
        如果不提供参数，将从配置文件或环境变量读取
        """
        # 优先使用传入的参数，否则使用配置文件的值
        self.mail_server = mail_server or MAIL_SERVER
        self.mail_port = mail_port or MAIL_PORT
        self.mail_username = mail_username or MAIL_USERNAME
        self.mail_password = mail_password or MAIL_PASSWORD

    def send_email(self, recipient, subject, body, attachment_path=None):
        """
        Sends an email using configured SMTP server.
        
        Args:
            recipient: 收件人邮箱地址
            subject: 邮件主题
            body: 邮件正文（HTML格式）
            attachment_path: 附件路径（可选）
            
        Returns:
            tuple: (success: bool, message: str)
        """
        try:
            # 验证配置
            if not all([self.mail_server, self.mail_port, self.mail_username, self.mail_password]):
                return False, "邮件配置不完整，请检查 config.py 中的邮件设置"
            
            print(f"[Email] 准备发送邮件到: {recipient}", file=sys.stderr)
            print(f"[Email] SMTP服务器: {self.mail_server}:{self.mail_port}", file=sys.stderr)
            print(f"[Email] 发件人: {self.mail_username}", file=sys.stderr)
            
            msg = MIMEMultipart()
            msg['From'] = self.mail_username
            msg['To'] = recipient
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'html'))


            # 连接 SMTP 服务器并发送邮件
            print(f"[Email] 正在连接到 SMTP 服务器...", file=sys.stderr)
            
            # 根据端口选择连接方式
            if str(self.mail_port) == '465':
                print(f"[Email] 使用 SSL 连接 (端口 465)...", file=sys.stderr)
                import ssl
                context = ssl.create_default_context()
                with smtplib.SMTP_SSL(self.mail_server, self.mail_port, timeout=30, context=context) as server:
                    print(f"[Email] 登录邮箱账户...", file=sys.stderr)
                    server.login(self.mail_username, self.mail_password)
                    print(f"[Email] 发送邮件...", file=sys.stderr)
                    server.sendmail(self.mail_username, recipient, msg.as_string())
            else:
                print(f"[Email] 使用 TLS 连接 (端口 {self.mail_port})...", file=sys.stderr)
                with smtplib.SMTP(self.mail_server, self.mail_port, timeout=30) as server:
                    print(f"[Email] 启动 TLS 加密...", file=sys.stderr)
                    server.starttls()
                    print(f"[Email] 登录邮箱账户...", file=sys.stderr)
                    server.login(self.mail_username, self.mail_password)
                    print(f"[Email] 发送邮件...", file=sys.stderr)
                    server.sendmail(self.mail_username, recipient, msg.as_string())
            
            # 邮件发送成功后，更新数据库中的 send_count
            update_send_count([recipient])
            
            print(f"[Email] ✓ 邮件发送成功到: {recipient}", file=sys.stderr)
            return True, "邮件发送成功"
                
        except smtplib.SMTPAuthenticationError as e:
            error_msg = f"SMTP 认证失败: {str(e)}。请检查邮箱用户名和密码/授权码是否正确"
            print(f"[Email] ✗ {error_msg}", file=sys.stderr)
            return False, error_msg
            
        except smtplib.SMTPException as e:
            error_msg = f"SMTP 错误: {str(e)}"
            print(f"[Email] ✗ {error_msg}", file=sys.stderr)
            return False, error_msg
            
        except ConnectionRefusedError:
            error_msg = f"连接被拒绝: 无法连接到 {self.mail_server}:{self.mail_port}。请检查服务器地址和端口是否正确"
            print(f"[Email] ✗ {error_msg}", file=sys.stderr)
            return False, error_msg
            
        except TimeoutError:
            error_msg = f"连接超时: 无法连接到 {self.mail_server}:{self.mail_port}。可能是网络问题或服务器被墙"
            print(f"[Email] ✗ {error_msg}", file=sys.stderr)
            return False, error_msg
            
        except Exception as e:
            error_msg = f"发送邮件失败: {str(e)}"
            print(f"[Email] ✗ {error_msg}", file=sys.stderr)
            return False, error_msg
    
    def test_connection(self):
        """
        测试 SMTP 服务器连接
        
        Returns:
            tuple: (success: bool, message: str)
        """
        try:
            print(f"[Email] 测试连接到 {self.mail_server}:{self.mail_port}...", file=sys.stderr)
            
            # 根据端口选择连接方式
            if str(self.mail_port) == '465':
                print(f"[Email] 使用 SSL 连接测试 (端口 465)...", file=sys.stderr)
                import ssl
                context = ssl.create_default_context()
                with smtplib.SMTP_SSL(self.mail_server, self.mail_port, timeout=10, context=context) as server:
                    server.login(self.mail_username, self.mail_password)
                    print(f"[Email] ✓ 连接测试成功", file=sys.stderr)
                    return True, "连接测试成功"
            else:
                print(f"[Email] 使用 TLS 连接测试 (端口 {self.mail_port})...", file=sys.stderr)
                with smtplib.SMTP(self.mail_server, self.mail_port, timeout=10) as server:
                    server.starttls()
                    server.login(self.mail_username, self.mail_password)
                    print(f"[Email] ✓ 连接测试成功", file=sys.stderr)
                    return True, "连接测试成功"
                    
        except Exception as e:
            error_msg = f"连接测试失败: {str(e)}"
            print(f"[Email] ✗ {error_msg}", file=sys.stderr)
            return False, error_msg