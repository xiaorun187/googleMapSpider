"""
DataIntegrityValidator - 数据完整性验证器
实现数量验证、字段完整性验证、重复检测和质量评分计算
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime


@dataclass
class FieldReport:
    """字段完整性报告"""
    name: bool = False
    website: bool = False
    email: bool = False
    phones: bool = False
    city: bool = False
    completeness: float = 0.0
    
    def to_dict(self) -> dict:
        return {
            'name': self.name,
            'website': self.website,
            'email': self.email,
            'phones': self.phones,
            'city': self.city,
            'completeness': self.completeness
        }


@dataclass
class ValidationReport:
    """验证报告"""
    actual_count: int = 0
    expected_count: int = 0
    completeness_rate: float = 0.0
    duplicate_count: int = 0
    quality_score: float = 0.0
    field_reports: List[FieldReport] = field(default_factory=list)
    validation_time: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            'actual_count': self.actual_count,
            'expected_count': self.expected_count,
            'completeness_rate': self.completeness_rate,
            'duplicate_count': self.duplicate_count,
            'quality_score': self.quality_score,
            'field_reports': [fr.to_dict() for fr in self.field_reports],
            'validation_time': self.validation_time
        }


class DataIntegrityValidator:
    """
    数据完整性验证器
    
    Features:
    - 数量验证
    - 字段完整性验证
    - 重复检测
    - 质量评分计算
    """
    
    # 字段权重（用于计算完整性分数）
    FIELD_WEIGHTS = {
        'name': 0.25,
        'website': 0.20,
        'email': 0.25,
        'phones': 0.15,
        'city': 0.15
    }
    
    def __init__(self, expected_count: int = 0):
        """
        初始化验证器
        
        Args:
            expected_count: 预期记录数量
        """
        self.expected_count = expected_count
    
    def validate_extraction(self, records: List[Dict[str, Any]]) -> ValidationReport:
        """
        验证提取结果的完整性
        
        Args:
            records: 商家记录列表
            
        Returns:
            ValidationReport: 验证报告
        """
        report = ValidationReport()
        report.validation_time = datetime.now().isoformat()
        
        # 数量验证
        report.actual_count = len(records)
        report.expected_count = self.expected_count
        report.completeness_rate = (
            len(records) / self.expected_count 
            if self.expected_count > 0 else 1.0
        )
        
        # 字段完整性验证
        for record in records:
            field_report = self._validate_record_fields(record)
            report.field_reports.append(field_report)
        
        # 重复检测
        report.duplicate_count = self._count_duplicates(records)
        
        # 数据质量评分
        report.quality_score = self._calculate_quality_score(report)
        
        return report
    
    def _validate_record_fields(self, record: Dict[str, Any]) -> FieldReport:
        """
        验证单条记录的字段完整性
        
        Args:
            record: 商家记录
            
        Returns:
            FieldReport: 字段报告
        """
        field_report = FieldReport()
        
        # 检查各字段是否存在且有值
        field_report.name = bool(record.get('name'))
        field_report.website = bool(record.get('website'))
        field_report.email = bool(record.get('email'))
        
        phones = record.get('phones', [])
        field_report.phones = bool(phones and len(phones) > 0)
        
        field_report.city = bool(record.get('city'))
        
        # 计算字段完整度
        field_report.completeness = self._calculate_field_completeness(record)
        
        return field_report
    
    def _calculate_field_completeness(self, record: Dict[str, Any]) -> float:
        """
        计算单条记录的字段完整度
        
        Args:
            record: 商家记录
            
        Returns:
            float: 完整度分数 (0-1)
        """
        score = 0.0
        
        if record.get('name'):
            score += self.FIELD_WEIGHTS['name']
        
        if record.get('website'):
            score += self.FIELD_WEIGHTS['website']
        
        if record.get('email'):
            score += self.FIELD_WEIGHTS['email']
        
        phones = record.get('phones', [])
        if phones and len(phones) > 0:
            score += self.FIELD_WEIGHTS['phones']
        
        if record.get('city'):
            score += self.FIELD_WEIGHTS['city']
        
        return score

    def _count_duplicates(self, records: List[Dict[str, Any]]) -> int:
        """
        统计重复记录数量
        
        基于邮箱和名称进行重复检测
        
        Args:
            records: 商家记录列表
            
        Returns:
            int: 重复记录数量
        """
        seen_emails = set()
        seen_names = set()
        duplicate_count = 0
        
        for record in records:
            email = record.get('email', '').lower().strip()
            name = record.get('name', '').lower().strip()
            
            is_duplicate = False
            
            # 基于邮箱检测重复
            if email and email in seen_emails:
                is_duplicate = True
            elif email:
                seen_emails.add(email)
            
            # 基于名称检测重复（仅当没有邮箱时）
            if not email and name and name in seen_names:
                is_duplicate = True
            elif name:
                seen_names.add(name)
            
            if is_duplicate:
                duplicate_count += 1
        
        return duplicate_count
    
    def _calculate_quality_score(self, report: ValidationReport) -> float:
        """
        计算数据质量评分 (0-100)
        
        评分维度:
        - 完整性权重: 40%
        - 字段完整性权重: 40%
        - 无重复权重: 20%
        
        Args:
            report: 验证报告
            
        Returns:
            float: 质量评分 (0-100)
        """
        # 完整性权重: 40%
        completeness_score = min(report.completeness_rate, 1.0) * 40
        
        # 字段完整性权重: 40%
        if report.field_reports:
            avg_field_completeness = sum(
                fr.completeness for fr in report.field_reports
            ) / len(report.field_reports)
        else:
            avg_field_completeness = 0
        field_score = avg_field_completeness * 40
        
        # 无重复权重: 20%
        if report.actual_count > 0:
            duplicate_rate = report.duplicate_count / report.actual_count
        else:
            duplicate_rate = 0
        duplicate_score = (1 - duplicate_rate) * 20
        
        return completeness_score + field_score + duplicate_score
    
    def generate_summary(self, report: ValidationReport) -> str:
        """
        生成验证摘要
        
        Args:
            report: 验证报告
            
        Returns:
            str: 摘要文本
        """
        lines = [
            "=" * 50,
            "数据完整性验证报告",
            "=" * 50,
            f"验证时间: {report.validation_time}",
            "",
            "【数量统计】",
            f"  预期数量: {report.expected_count}",
            f"  实际数量: {report.actual_count}",
            f"  完成率: {report.completeness_rate * 100:.1f}%",
            f"  重复数量: {report.duplicate_count}",
            "",
            "【质量评分】",
            f"  总分: {report.quality_score:.1f}/100",
            "",
            "【字段完整性】"
        ]
        
        if report.field_reports:
            # 统计各字段的填充率
            total = len(report.field_reports)
            name_count = sum(1 for fr in report.field_reports if fr.name)
            website_count = sum(1 for fr in report.field_reports if fr.website)
            email_count = sum(1 for fr in report.field_reports if fr.email)
            phones_count = sum(1 for fr in report.field_reports if fr.phones)
            city_count = sum(1 for fr in report.field_reports if fr.city)
            
            lines.extend([
                f"  名称填充率: {name_count}/{total} ({name_count/total*100:.1f}%)",
                f"  网站填充率: {website_count}/{total} ({website_count/total*100:.1f}%)",
                f"  邮箱填充率: {email_count}/{total} ({email_count/total*100:.1f}%)",
                f"  电话填充率: {phones_count}/{total} ({phones_count/total*100:.1f}%)",
                f"  城市填充率: {city_count}/{total} ({city_count/total*100:.1f}%)",
            ])
        
        lines.append("=" * 50)
        
        return "\n".join(lines)
