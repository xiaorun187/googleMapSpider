"""
密码加密工具类
使用 bcrypt 算法进行密码哈希和验证
"""
import bcrypt


class PasswordHasher:
    """密码加密工具类"""
    
    @staticmethod
    def hash_password(password: str) -> str:
        """
        将明文密码转换为 bcrypt 哈希值
        
        Args:
            password: 明文密码
            
        Returns:
            str: bcrypt 哈希后的密码
        """
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')
    
    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        """
        验证密码是否匹配哈希值
        
        Args:
            password: 明文密码
            password_hash: 存储的哈希值
            
        Returns:
            bool: 密码是否匹配
        """
        try:
            return bcrypt.checkpw(
                password.encode('utf-8'), 
                password_hash.encode('utf-8')
            )
        except Exception:
            return False
