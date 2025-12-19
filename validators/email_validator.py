"""
EmailValidator - 邮箱验证组件
实现 RFC 5322 兼容的邮箱格式验证，包含图片扩展名和尺寸模式检测
"""
import re
import json
from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class ValidationResult:
    """验证结果数据类"""
    is_valid: bool
    email: str
    reason: Optional[str] = None
    
    def to_json(self) -> str:
        """序列化为JSON"""
        return json.dumps(asdict(self), ensure_ascii=False)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'ValidationResult':
        """从JSON反序列化"""
        data = json.loads(json_str)
        return cls(**data)
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'ValidationResult':
        """从字典创建"""
        return cls(**data)


class EmailValidator:
    """
    邮箱验证组件，负责验证提取的邮箱地址是否有效
    
    Features:
    - RFC 5322 兼容的邮箱格式验证
    - 图片扩展名检测（png, jpg, jpeg, gif, bmp, svg）
    - 尺寸模式检测（NxM格式）
    - 无效模式检测（logo, image, img）
    """
    
    # RFC 5322 兼容的邮箱正则表达式
    EMAIL_PATTERN = re.compile(
        r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    )
    
    # 无效的图片扩展名
    INVALID_EXTENSIONS: tuple = ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg')
    
    # 无效模式列表
    INVALID_PATTERNS: list = [
        r'\d+x\d+',  # 尺寸模式 如 100x200
        r'\d+x\d*',  # 尺寸模式变体 如 100x
        r'logo',
        r'image',
        r'img'
    ]
    
    # 预编译无效模式正则
    _compiled_patterns: list = None
    
    def __init__(self):
        """初始化验证器，预编译正则表达式"""
        if EmailValidator._compiled_patterns is None:
            EmailValidator._compiled_patterns = [
                re.compile(pattern, re.IGNORECASE) 
                for pattern in self.INVALID_PATTERNS
            ]
    
    def validate(self, email: str) -> ValidationResult:
        """
        验证邮箱地址是否有效
        
        Args:
            email: 待验证的邮箱地址
            
        Returns:
            ValidationResult: 验证结果对象
        """
        if not email or not isinstance(email, str):
            return ValidationResult(
                is_valid=False,
                email=email or '',
                reason='邮箱地址为空或类型无效'
            )
        
        email = email.strip().lower()
        
        # 检查长度
        if len(email) > 254:
            return ValidationResult(
                is_valid=False,
                email=email,
                reason='邮箱地址超过最大长度254字符'
            )
        
        # 检查格式
        if not self.is_valid_format(email):
            return ValidationResult(
                is_valid=False,
                email=email,
                reason='邮箱格式不符合RFC 5322标准'
            )
        
        # 检查图片扩展名
        if self.has_invalid_extension(email):
            return ValidationResult(
                is_valid=False,
                email=email,
                reason='邮箱包含图片文件扩展名'
            )
        
        # 检查尺寸模式
        if self.has_dimension_pattern(email):
            return ValidationResult(
                is_valid=False,
                email=email,
                reason='邮箱包含尺寸模式（如NxM）'
            )
        
        # 检查其他无效模式
        if self.has_invalid_pattern(email):
            return ValidationResult(
                is_valid=False,
                email=email,
                reason='邮箱包含无效模式（logo/image/img）'
            )
        
        return ValidationResult(
            is_valid=True,
            email=email,
            reason=None
        )
    
    def is_valid_format(self, email: str) -> bool:
        """
        检查邮箱格式是否符合RFC 5322
        
        Args:
            email: 待验证的邮箱地址
            
        Returns:
            bool: 格式是否有效
        """
        if not email:
            return False
        return bool(self.EMAIL_PATTERN.match(email))
    
    def has_invalid_extension(self, email: str) -> bool:
        """
        检查邮箱是否包含图片扩展名
        
        Args:
            email: 待验证的邮箱地址
            
        Returns:
            bool: 是否包含无效扩展名
        """
        if not email or '@' not in email:
            return False
        
        local_part = email.split('@')[0].lower()
        return any(local_part.endswith(ext) for ext in self.INVALID_EXTENSIONS)
    
    def has_dimension_pattern(self, email: str) -> bool:
        """
        检查邮箱是否包含尺寸模式（如100x200）
        
        Args:
            email: 待验证的邮箱地址
            
        Returns:
            bool: 是否包含尺寸模式
        """
        if not email:
            return False
        
        # 专门检测尺寸模式：至少两位数字 + x + 至少一位数字
        # 例如: 100x200, 50x50, 1920x1080
        # 排除: 0x (十六进制前缀), 单个数字+x
        dimension_pattern = re.compile(r'\d{2,}x\d+', re.IGNORECASE)
        return bool(dimension_pattern.search(email))
    
    def has_invalid_pattern(self, email: str) -> bool:
        """
        检查邮箱是否包含其他无效模式（logo, image, img）
        
        Args:
            email: 待验证的邮箱地址
            
        Returns:
            bool: 是否包含无效模式
        """
        if not email:
            return False
        
        email_lower = email.lower()
        # 只检查 logo, image, img 模式，不包括尺寸模式
        for pattern in ['logo', 'image', 'img']:
            if pattern in email_lower:
                return True
        return False
    
    def is_valid(self, email: str) -> bool:
        """
        简化的验证方法，只返回布尔值
        
        Args:
            email: 待验证的邮箱地址
            
        Returns:
            bool: 邮箱是否有效
        """
        return self.validate(email).is_valid
