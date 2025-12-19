"""
BusinessRecord - 商家记录数据模型
包含新增的 city 字段，支持 JSON 序列化/反序列化
"""
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, List


@dataclass
class BusinessRecord:
    """
    商家记录数据模型
    
    Attributes:
        id: 记录ID
        name: 商家名称
        website: 商家网站
        email: 邮箱地址
        phones: 电话号码列表
        facebook: Facebook链接
        twitter: Twitter链接
        instagram: Instagram链接
        linkedin: LinkedIn链接
        whatsapp: WhatsApp链接
        youtube: YouTube链接
        city: 城市字段
        product: 商品名/搜索关键词字段
        send_count: 发送次数
        created_at: 创建时间
        updated_at: 更新时间
    """
    id: Optional[int] = None
    name: str = ''
    website: Optional[str] = None
    email: Optional[str] = None
    phones: List[str] = field(default_factory=list)
    facebook: Optional[str] = None
    twitter: Optional[str] = None
    instagram: Optional[str] = None
    linkedin: Optional[str] = None
    whatsapp: Optional[str] = None
    youtube: Optional[str] = None
    city: Optional[str] = None  # 城市字段
    product: Optional[str] = None  # 商品名/搜索关键词字段
    send_count: int = 0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    
    def to_dict(self) -> dict:
        """转换为字典"""
        data = asdict(self)
        # 确保 phones 是列表
        if data.get('phones') is None:
            data['phones'] = []
        return data
    
    def to_json(self) -> str:
        """序列化为JSON"""
        return json.dumps(self.to_dict(), ensure_ascii=False, default=str)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'BusinessRecord':
        """从字典创建"""
        # 处理 phones 字段
        phones = data.get('phones', [])
        if isinstance(phones, str):
            phones = [p.strip() for p in phones.split(',') if p.strip()]
        elif phones is None:
            phones = []
        
        # 处理 emails 字段（兼容旧格式）
        email = data.get('email')
        if not email and 'emails' in data:
            emails = data.get('emails', [])
            if isinstance(emails, list) and emails:
                email = emails[0]
            elif isinstance(emails, str):
                email = emails
        
        return cls(
            id=data.get('id'),
            name=data.get('name', ''),
            website=data.get('website'),
            email=email,
            phones=phones,
            facebook=data.get('facebook'),
            twitter=data.get('twitter'),
            instagram=data.get('instagram'),
            linkedin=data.get('linkedin'),
            whatsapp=data.get('whatsapp'),
            youtube=data.get('youtube'),
            city=data.get('city'),
            product=data.get('product'),
            send_count=data.get('send_count', 0),
            created_at=data.get('created_at'),
            updated_at=data.get('updated_at')
        )
    
    @classmethod
    def from_json(cls, json_str: str) -> 'BusinessRecord':
        """从JSON反序列化"""
        data = json.loads(json_str)
        return cls.from_dict(data)
    
    def get_completeness_score(self) -> float:
        """
        计算记录的完整度分数（0-1）
        
        Returns:
            float: 完整度分数
        """
        fields = [
            self.name,
            self.website,
            self.email,
            bool(self.phones),
            self.facebook,
            self.twitter,
            self.instagram,
            self.linkedin,
            self.whatsapp,
            self.youtube,
            self.city,
            self.product
        ]
        
        filled_count = sum(1 for f in fields if f)
        return filled_count / len(fields)
    
    def merge_with(self, other: 'BusinessRecord') -> 'BusinessRecord':
        """
        与另一条记录合并，保留更完整的信息
        
        Args:
            other: 另一条商家记录
            
        Returns:
            BusinessRecord: 合并后的记录
        """
        # 合并电话号码
        merged_phones = list(set(self.phones + other.phones))
        
        # 选择非空值
        return BusinessRecord(
            id=self.id or other.id,
            name=self.name or other.name,
            website=self.website or other.website,
            email=self.email or other.email,
            phones=merged_phones,
            facebook=self.facebook or other.facebook,
            twitter=self.twitter or other.twitter,
            instagram=self.instagram or other.instagram,
            linkedin=self.linkedin or other.linkedin,
            whatsapp=self.whatsapp or other.whatsapp,
            youtube=self.youtube or other.youtube,
            city=self.city or other.city,
            product=self.product or other.product,
            send_count=max(self.send_count, other.send_count),
            created_at=self.created_at or other.created_at,
            updated_at=datetime.now().isoformat()
        )
    
    def __eq__(self, other) -> bool:
        """判断两条记录是否相等（基于邮箱）"""
        if not isinstance(other, BusinessRecord):
            return False
        if self.email and other.email:
            return self.email.lower() == other.email.lower()
        return False
    
    def __hash__(self) -> int:
        """哈希值（基于邮箱）"""
        if self.email:
            return hash(self.email.lower())
        return hash(id(self))
