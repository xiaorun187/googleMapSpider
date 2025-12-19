"""
URLValidator - URL验证组件
实现 URL 格式验证
"""
import re
from urllib.parse import urlparse
from typing import Optional


class URLValidator:
    """
    URL验证组件
    
    Features:
    - URL 格式验证
    - 协议检查（http/https）
    - 域名验证
    """
    
    # URL 正则表达式
    URL_PATTERN = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain
        r'localhost|'  # localhost
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE
    )
    
    # 有效的协议
    VALID_SCHEMES = ('http', 'https')
    
    def validate(self, url: str) -> bool:
        """
        验证URL格式是否有效
        
        Args:
            url: 待验证的URL
            
        Returns:
            bool: URL是否有效
        """
        if not url or not isinstance(url, str):
            return False
        
        url = url.strip()
        
        # 使用正则验证
        if not self.URL_PATTERN.match(url):
            return False
        
        # 使用 urlparse 进一步验证
        try:
            parsed = urlparse(url)
            
            # 检查协议
            if parsed.scheme not in self.VALID_SCHEMES:
                return False
            
            # 检查域名
            if not parsed.netloc:
                return False
            
            return True
        except Exception:
            return False
    
    def is_valid_format(self, url: str) -> bool:
        """
        检查URL格式是否有效（别名方法）
        
        Args:
            url: 待验证的URL
            
        Returns:
            bool: URL格式是否有效
        """
        return self.validate(url)
    
    def extract_domain(self, url: str) -> Optional[str]:
        """
        提取URL中的域名
        
        Args:
            url: URL字符串
            
        Returns:
            Optional[str]: 域名，无效则返回None
        """
        if not self.validate(url):
            return None
        
        try:
            parsed = urlparse(url)
            return parsed.netloc
        except Exception:
            return None
    
    def normalize_url(self, url: str) -> Optional[str]:
        """
        规范化URL
        
        Args:
            url: URL字符串
            
        Returns:
            Optional[str]: 规范化后的URL，无效则返回None
        """
        if not url:
            return None
        
        url = url.strip()
        
        # 如果没有协议，添加 https://
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        if not self.validate(url):
            return None
        
        return url
