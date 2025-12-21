"""
用户业务逻辑层
"""
from dataclasses import dataclass
from typing import Optional, Tuple

from repositories.user_repository import UserRepository
from utils.password_hasher import PasswordHasher


@dataclass
class ValidationResult:
    """验证结果"""
    is_valid: bool
    error_message: Optional[str] = None


@dataclass
class AuthResult:
    """认证结果"""
    success: bool
    user_id: Optional[int] = None
    username: Optional[str] = None
    error_message: Optional[str] = None


class UserService:
    """用户业务逻辑层"""
    
    # 验证常量
    MIN_USERNAME_LENGTH = 3
    MAX_USERNAME_LENGTH = 50
    MIN_PASSWORD_LENGTH = 6
    
    def __init__(self):
        self.user_repository = UserRepository()
        self.password_hasher = PasswordHasher()
    
    def validate_registration_input(self, username: str, password: str) -> ValidationResult:
        """
        验证注册输入
        
        Args:
            username: 用户名
            password: 密码
            
        Returns:
            ValidationResult: 验证结果
        """
        # 检查空值
        if not username or not username.strip():
            return ValidationResult(False, "用户名不能为空")
        
        if not password or not password.strip():
            return ValidationResult(False, "密码不能为空")
        
        username = username.strip()
        
        # 检查用户名长度
        if len(username) < self.MIN_USERNAME_LENGTH:
            return ValidationResult(False, f"用户名至少需要{self.MIN_USERNAME_LENGTH}个字符")
        
        if len(username) > self.MAX_USERNAME_LENGTH:
            return ValidationResult(False, f"用户名不能超过{self.MAX_USERNAME_LENGTH}个字符")
        
        # 检查密码长度
        if len(password) < self.MIN_PASSWORD_LENGTH:
            return ValidationResult(False, f"密码至少需要{self.MIN_PASSWORD_LENGTH}个字符")
        
        return ValidationResult(True)
    
    def validate_login_input(self, username: str, password: str) -> ValidationResult:
        """
        验证登录输入
        
        Args:
            username: 用户名
            password: 密码
            
        Returns:
            ValidationResult: 验证结果
        """
        if not username or not username.strip():
            return ValidationResult(False, "请输入用户名")
        
        if not password:
            return ValidationResult(False, "请输入密码")
        
        return ValidationResult(True)
    
    def register_user(self, username: str, password: str) -> Tuple[bool, str]:
        """
        注册新用户
        
        Args:
            username: 用户名
            password: 密码
            
        Returns:
            Tuple[bool, str]: (成功标志, 消息)
        """
        # 验证输入
        validation = self.validate_registration_input(username, password)
        if not validation.is_valid:
            return False, validation.error_message
        
        username = username.strip()
        
        # 检查用户名是否已存在
        if self.user_repository.username_exists(username):
            return False, "用户名已被使用"
        
        # 加密密码
        password_hash = self.password_hasher.hash_password(password)
        
        # 创建用户
        user_id = self.user_repository.create_user(username, password_hash)
        
        if user_id:
            return True, "注册成功"
        else:
            return False, "系统错误，请稍后重试"
    
    def authenticate(self, username: str, password: str) -> AuthResult:
        """
        验证用户凭据
        
        Args:
            username: 用户名
            password: 密码
            
        Returns:
            AuthResult: 认证结果
        """
        # 验证输入
        validation = self.validate_login_input(username, password)
        if not validation.is_valid:
            return AuthResult(False, error_message=validation.error_message)
        
        username = username.strip()
        
        # 查询用户
        user = self.user_repository.get_user_by_username(username)
        
        if not user:
            # 不区分用户不存在和密码错误，防止用户名枚举
            return AuthResult(False, error_message="用户名或密码错误")
        
        # 验证密码
        if not self.password_hasher.verify_password(password, user.password_hash):
            return AuthResult(False, error_message="用户名或密码错误")
        
        return AuthResult(
            success=True,
            user_id=user.id,
            username=user.username
        )
