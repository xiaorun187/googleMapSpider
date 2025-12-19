"""
PhoneValidator - 电话号码验证组件
实现 8-15 位数字长度验证和数字提取功能
"""
import re
from typing import Optional


class PhoneValidator:
    """
    电话号码验证组件
    
    Features:
    - 8-15 位数字长度验证
    - 数字提取功能
    - 支持各种格式的电话号码
    """
    
    MIN_DIGITS: int = 8
    MAX_DIGITS: int = 15
    
    # 数字提取正则
    DIGIT_PATTERN = re.compile(r'\d')
    
    def validate(self, phone: str) -> bool:
        """
        验证电话号码是否有效（8-15位数字）
        
        Args:
            phone: 待验证的电话号码
            
        Returns:
            bool: 电话号码是否有效
        """
        if not phone or not isinstance(phone, str):
            return False
        
        digits = self.extract_digits(phone)
        digit_count = len(digits)
        
        return self.MIN_DIGITS <= digit_count <= self.MAX_DIGITS
    
    def extract_digits(self, phone: str) -> str:
        """
        提取电话号码中的数字
        
        Args:
            phone: 电话号码字符串
            
        Returns:
            str: 仅包含数字的字符串
        """
        if not phone:
            return ''
        
        return ''.join(self.DIGIT_PATTERN.findall(phone))
    
    def format_phone(self, phone: str) -> Optional[str]:
        """
        格式化电话号码，保留数字和加号
        
        Args:
            phone: 电话号码字符串
            
        Returns:
            Optional[str]: 格式化后的电话号码，无效则返回None
        """
        if not phone:
            return None
        
        # 保留数字和加号
        formatted = ''.join(c for c in phone if c.isdigit() or c == '+')
        
        if not self.validate(formatted):
            return None
        
        return formatted
    
    def get_digit_count(self, phone: str) -> int:
        """
        获取电话号码中的数字数量
        
        Args:
            phone: 电话号码字符串
            
        Returns:
            int: 数字数量
        """
        return len(self.extract_digits(phone))
