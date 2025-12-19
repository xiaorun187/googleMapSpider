"""
AIConfiguration - AI配置数据类
实现 API 配置管理和密钥加密/解密
"""
import json
import base64
from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class AIConfiguration:
    """
    AI配置数据类
    
    Attributes:
        api_endpoint: API端点URL
        api_key: API密钥（加密存储）
        model: 模型名称
    """
    api_endpoint: str = ''
    api_key: str = ''  # 加密存储
    model: str = ''
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return asdict(self)
    
    def to_json(self) -> str:
        """序列化为JSON"""
        return json.dumps(self.to_dict(), ensure_ascii=False)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'AIConfiguration':
        """从字典创建"""
        return cls(
            api_endpoint=data.get('api_endpoint', ''),
            api_key=data.get('api_key', ''),
            model=data.get('model', '')
        )
    
    @classmethod
    def from_json(cls, json_str: str) -> 'AIConfiguration':
        """从JSON反序列化"""
        data = json.loads(json_str)
        return cls.from_dict(data)
    
    @staticmethod
    def encrypt_key(key: str) -> str:
        """
        加密API密钥
        
        Args:
            key: 原始API密钥
            
        Returns:
            str: 加密后的密钥
        """
        if not key:
            return ''
        # 使用 base64 编码作为简单加密
        # 生产环境应使用更安全的加密方式
        return base64.b64encode(key.encode('utf-8')).decode('utf-8')
    
    @staticmethod
    def decrypt_key(encrypted: str) -> str:
        """
        解密API密钥
        
        Args:
            encrypted: 加密后的密钥
            
        Returns:
            str: 原始API密钥
        """
        if not encrypted:
            return ''
        try:
            return base64.b64decode(encrypted.encode('utf-8')).decode('utf-8')
        except Exception:
            return ''
