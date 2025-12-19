"""
DataDeduplicator - 数据去重组件
实现基于 name + website 的重复检测、完整度计算和记录合并
"""
import sys
sys.path.insert(0, '.')

from typing import Optional, List, Dict, Set, Tuple
from models.business_record import BusinessRecord


class DataDeduplicator:
    """
    数据去重组件，负责识别和处理重复的商家记录
    
    Features:
    - 基于 name + website 的重复检测 (Requirements 1.1, 1.2, 1.3)
    - 完整度计算算法
    - 记录合并逻辑（保留更完整的记录）
    - 联系信息合并（保留所有唯一值）
    """
    
    def __init__(self):
        """初始化去重器"""
        self._name_website_index: Dict[Tuple[str, str], BusinessRecord] = {}
    
    def check_duplicate(
        self, 
        record: BusinessRecord, 
        existing_records: List[BusinessRecord]
    ) -> Optional[BusinessRecord]:
        """
        检查是否存在重复记录，基于 name + website 判断
        
        Args:
            record: 待检查的记录
            existing_records: 现有记录列表
            
        Returns:
            Optional[BusinessRecord]: 匹配的现有记录，无重复则返回None
        """
        record_name = (record.name or '').strip().lower()
        record_website = (record.website or '').strip().lower()
        
        for existing in existing_records:
            existing_name = (existing.name or '').strip().lower()
            existing_website = (existing.website or '').strip().lower()
            
            if record_name == existing_name and record_website == existing_website:
                return existing
        
        return None
    
    def is_duplicate_by_name_website(
        self,
        name: str,
        website: str,
        existing_records: List[BusinessRecord]
    ) -> bool:
        """
        基于 name + website 检查是否为重复记录
        
        Args:
            name: 商家名称
            website: 商家网站
            existing_records: 现有记录列表
            
        Returns:
            bool: 是否为重复记录
        """
        name_lower = (name or '').strip().lower()
        website_lower = (website or '').strip().lower()
        
        for existing in existing_records:
            existing_name = (existing.name or '').strip().lower()
            existing_website = (existing.website or '').strip().lower()
            
            if name_lower == existing_name and website_lower == existing_website:
                return True
        
        return False
    
    def merge_records(
        self, 
        existing: BusinessRecord, 
        new: BusinessRecord
    ) -> BusinessRecord:
        """
        合并两条记录，保留更完整的信息
        
        Args:
            existing: 现有记录
            new: 新记录
            
        Returns:
            BusinessRecord: 合并后的记录
        """
        existing_score = self.calculate_completeness(existing)
        new_score = self.calculate_completeness(new)
        
        # 以完整度更高的记录为基础
        if new_score > existing_score:
            base = new
            other = existing
        else:
            base = existing
            other = new
        
        # 合并联系信息
        merged_contact = self.merge_contact_info(base, other)
        
        return BusinessRecord(
            id=base.id or other.id,
            name=base.name or other.name,
            website=base.website or other.website,
            email=base.email or other.email,
            phones=merged_contact.get('phones', []),
            facebook=base.facebook or other.facebook,
            twitter=base.twitter or other.twitter,
            instagram=base.instagram or other.instagram,
            linkedin=base.linkedin or other.linkedin,
            whatsapp=base.whatsapp or other.whatsapp,
            youtube=base.youtube or other.youtube,
            city=base.city or other.city,
            send_count=max(base.send_count, other.send_count),
            created_at=base.created_at or other.created_at,
            updated_at=base.updated_at or other.updated_at
        )
    
    def calculate_completeness(self, record: BusinessRecord) -> float:
        """
        计算记录的完整度分数（0-1）
        
        Args:
            record: 商家记录
            
        Returns:
            float: 完整度分数
        """
        fields = [
            record.name,
            record.website,
            record.email,
            bool(record.phones),
            record.facebook,
            record.twitter,
            record.instagram,
            record.linkedin,
            record.whatsapp,
            record.youtube,
            record.city
        ]
        
        filled_count = sum(1 for f in fields if f)
        return filled_count / len(fields)
    
    def merge_contact_info(
        self, 
        existing: BusinessRecord, 
        new: BusinessRecord
    ) -> dict:
        """
        合并联系信息，保留所有唯一值
        
        Args:
            existing: 现有记录
            new: 新记录
            
        Returns:
            dict: 合并后的联系信息
        """
        # 合并电话号码
        phones_set: Set[str] = set()
        if existing.phones:
            phones_set.update(existing.phones)
        if new.phones:
            phones_set.update(new.phones)
        
        return {
            'phones': list(phones_set),
            'facebook': existing.facebook or new.facebook,
            'twitter': existing.twitter or new.twitter,
            'instagram': existing.instagram or new.instagram,
            'linkedin': existing.linkedin or new.linkedin,
            'whatsapp': existing.whatsapp or new.whatsapp,
            'youtube': existing.youtube or new.youtube
        }
    
    def deduplicate_list(
        self, 
        records: List[BusinessRecord]
    ) -> List[BusinessRecord]:
        """
        对记录列表进行去重，基于 name + website 组合
        
        Args:
            records: 记录列表
            
        Returns:
            List[BusinessRecord]: 去重后的记录列表
        """
        result: Dict[Tuple[str, str], BusinessRecord] = {}
        
        for record in records:
            # 创建 name + website 组合键
            name_key = (record.name or '').strip().lower()
            website_key = (record.website or '').strip().lower()
            combination_key = (name_key, website_key)
            
            if combination_key in result:
                # 合并重复记录
                result[combination_key] = self.merge_records(
                    result[combination_key], 
                    record
                )
            else:
                result[combination_key] = record
        
        return list(result.values())
    
    def is_duplicate(
        self, 
        record: BusinessRecord, 
        existing_records: List[BusinessRecord]
    ) -> bool:
        """
        检查记录是否为重复，基于 name + website 判断
        
        Args:
            record: 待检查的记录
            existing_records: 现有记录列表
            
        Returns:
            bool: 是否为重复记录
        """
        return self.check_duplicate(record, existing_records) is not None
    
    def get_combination_key(self, record: BusinessRecord) -> Tuple[str, str]:
        """
        获取记录的 name + website 组合键
        
        Args:
            record: 商家记录
            
        Returns:
            Tuple[str, str]: (name, website) 组合键
        """
        name = (record.name or '').strip().lower()
        website = (record.website or '').strip().lower()
        return (name, website)
