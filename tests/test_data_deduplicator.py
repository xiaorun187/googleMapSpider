"""
DataDeduplicator 属性测试
使用 Hypothesis 进行属性测试，验证 DataDeduplicator 的正确性

**Feature: data-collection-optimization**
"""
import pytest
from hypothesis import given, strategies as st, settings, assume
import string
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.data_deduplicator import DataDeduplicator
from models.business_record import BusinessRecord


# ============================================================================
# 测试策略（Generators）
# ============================================================================

@st.composite
def valid_email(draw):
    """生成有效的邮箱地址"""
    local_length = draw(st.integers(min_value=3, max_value=10))
    local = draw(st.text(
        alphabet=string.ascii_lowercase + string.digits,
        min_size=local_length,
        max_size=local_length
    ))
    if not local:
        local = 'user'
    
    domain_length = draw(st.integers(min_value=3, max_value=8))
    domain = draw(st.text(
        alphabet=string.ascii_lowercase,
        min_size=domain_length,
        max_size=domain_length
    ))
    if not domain:
        domain = 'example'
    
    tld = draw(st.sampled_from(['com', 'org', 'net', 'io']))
    
    return f"{local}@{domain}.{tld}"


@st.composite
def business_record(draw, email=None):
    """生成商家记录"""
    if email is None:
        email = draw(st.one_of(st.none(), valid_email()))
    
    phones = draw(st.lists(
        st.text(alphabet=string.digits, min_size=8, max_size=15),
        min_size=0,
        max_size=3
    ))
    
    return BusinessRecord(
        id=draw(st.one_of(st.none(), st.integers(min_value=1, max_value=10000))),
        name=draw(st.text(min_size=0, max_size=50)),
        website=draw(st.one_of(st.none(), st.text(min_size=5, max_size=30))),
        email=email,
        phones=phones,
        facebook=draw(st.one_of(st.none(), st.text(min_size=5, max_size=30))),
        twitter=draw(st.one_of(st.none(), st.text(min_size=5, max_size=30))),
        instagram=draw(st.one_of(st.none(), st.text(min_size=5, max_size=30))),
        linkedin=draw(st.one_of(st.none(), st.text(min_size=5, max_size=30))),
        whatsapp=draw(st.one_of(st.none(), st.text(min_size=5, max_size=30))),
        youtube=draw(st.one_of(st.none(), st.text(min_size=5, max_size=30))),
        city=draw(st.one_of(st.none(), st.text(min_size=2, max_size=20))),
        send_count=draw(st.integers(min_value=0, max_value=100))
    )


@st.composite
def two_records_same_email(draw):
    """生成两条具有相同邮箱的记录"""
    email = draw(valid_email())
    record1 = draw(business_record(email=email))
    record2 = draw(business_record(email=email))
    return record1, record2


@st.composite
def two_records_different_completeness(draw):
    """生成两条完整度不同的记录（相同邮箱）"""
    email = draw(valid_email())
    
    # 生成完整度较低的记录
    sparse_record = BusinessRecord(
        email=email,
        name=draw(st.text(min_size=1, max_size=20))
    )
    
    # 生成完整度较高的记录
    complete_record = BusinessRecord(
        email=email,
        name=draw(st.text(min_size=1, max_size=20)),
        website=draw(st.text(min_size=5, max_size=30)),
        phones=[draw(st.text(alphabet=string.digits, min_size=8, max_size=15))],
        facebook=draw(st.text(min_size=5, max_size=30)),
        city=draw(st.text(min_size=2, max_size=20))
    )
    
    return sparse_record, complete_record


@st.composite
def two_records_with_different_phones(draw):
    """生成两条具有不同电话号码的记录"""
    email = draw(valid_email())
    
    phones1 = draw(st.lists(
        st.text(alphabet=string.digits, min_size=8, max_size=15),
        min_size=1,
        max_size=2,
        unique=True
    ))
    
    phones2 = draw(st.lists(
        st.text(alphabet=string.digits, min_size=8, max_size=15),
        min_size=1,
        max_size=2,
        unique=True
    ))
    
    record1 = BusinessRecord(email=email, phones=phones1, name='Business 1')
    record2 = BusinessRecord(email=email, phones=phones2, name='Business 2')
    
    return record1, record2


# ============================================================================
# Property 7: Duplicate Detection by Email
# **Feature: data-collection-optimization, Property 7: Duplicate Detection by Email**
# **Validates: Requirements 2.1**
# ============================================================================

class TestDuplicateDetectionByEmail:
    """Property 7: 基于邮箱的重复检测"""
    
    @given(data=two_records_same_email())
    @settings(max_examples=100)
    def test_same_email_detected_as_duplicate(self, data):
        """
        *For any* two BusinessRecord objects with the same email address,
        the DataDeduplicator SHALL identify them as duplicates.
        **Feature: data-collection-optimization, Property 7: Duplicate Detection by Email**
        **Validates: Requirements 2.1**
        """
        record1, record2 = data
        deduplicator = DataDeduplicator()
        
        # 检查 record2 是否被识别为 record1 的重复
        duplicate = deduplicator.check_duplicate(record2, [record1])
        
        assert duplicate is not None, \
            f"Records with same email '{record1.email}' not detected as duplicates"
    
    @given(record1=business_record(), record2=business_record())
    @settings(max_examples=100)
    def test_different_emails_not_duplicates(self, record1, record2):
        """
        *For any* two BusinessRecord objects with different email addresses,
        the DataDeduplicator SHALL NOT identify them as duplicates.
        **Feature: data-collection-optimization, Property 7: Duplicate Detection by Email**
        **Validates: Requirements 2.1**
        """
        # 确保邮箱不同
        assume(record1.email and record2.email)
        assume(record1.email.lower() != record2.email.lower())
        
        deduplicator = DataDeduplicator()
        duplicate = deduplicator.check_duplicate(record2, [record1])
        
        assert duplicate is None, \
            f"Records with different emails detected as duplicates"


# ============================================================================
# Property 8: Completeness-Based Merge
# **Feature: data-collection-optimization, Property 8: Completeness-Based Merge**
# **Validates: Requirements 2.2**
# ============================================================================

class TestCompletenessBasedMerge:
    """Property 8: 基于完整度的合并"""
    
    @given(data=two_records_different_completeness())
    @settings(max_examples=100)
    def test_higher_completeness_retained(self, data):
        """
        *For any* two duplicate BusinessRecord objects with different completeness scores,
        the DataDeduplicator SHALL retain the record with the higher completeness score.
        **Feature: data-collection-optimization, Property 8: Completeness-Based Merge**
        **Validates: Requirements 2.2**
        """
        sparse_record, complete_record = data
        deduplicator = DataDeduplicator()
        
        sparse_score = deduplicator.calculate_completeness(sparse_record)
        complete_score = deduplicator.calculate_completeness(complete_record)
        
        # 确保完整度确实不同
        assume(complete_score > sparse_score)
        
        # 合并记录
        merged = deduplicator.merge_records(sparse_record, complete_record)
        merged_score = deduplicator.calculate_completeness(merged)
        
        # 合并后的完整度应该至少等于较高的完整度
        assert merged_score >= complete_score, \
            f"Merged score {merged_score} < complete score {complete_score}"
    
    @given(record=business_record())
    @settings(max_examples=100)
    def test_completeness_score_in_valid_range(self, record):
        """完整度分数应该在 0-1 范围内"""
        deduplicator = DataDeduplicator()
        score = deduplicator.calculate_completeness(record)
        
        assert 0 <= score <= 1, f"Completeness score {score} out of range [0, 1]"


# ============================================================================
# Property 9: Contact Information Preservation
# **Feature: data-collection-optimization, Property 9: Contact Information Preservation**
# **Validates: Requirements 2.3**
# ============================================================================

class TestContactInformationPreservation:
    """Property 9: 联系信息保留"""
    
    @given(data=two_records_with_different_phones())
    @settings(max_examples=100)
    def test_all_phones_preserved_after_merge(self, data):
        """
        *For any* two BusinessRecord objects being merged,
        the resulting record SHALL contain the union of all unique phone numbers.
        **Feature: data-collection-optimization, Property 9: Contact Information Preservation**
        **Validates: Requirements 2.3**
        """
        record1, record2 = data
        deduplicator = DataDeduplicator()
        
        # 收集所有原始电话号码
        all_phones = set(record1.phones) | set(record2.phones)
        
        # 合并记录
        merged = deduplicator.merge_records(record1, record2)
        merged_phones = set(merged.phones)
        
        # 验证所有电话号码都被保留
        assert all_phones == merged_phones, \
            f"Phones not preserved: expected {all_phones}, got {merged_phones}"
    
    @given(data=two_records_same_email())
    @settings(max_examples=100)
    def test_social_media_preserved_after_merge(self, data):
        """
        *For any* two BusinessRecord objects being merged,
        the resulting record SHALL contain social media links from both records.
        **Feature: data-collection-optimization, Property 9: Contact Information Preservation**
        **Validates: Requirements 2.3**
        """
        record1, record2 = data
        deduplicator = DataDeduplicator()
        
        merged = deduplicator.merge_records(record1, record2)
        
        # 验证社交媒体链接被保留（至少保留一个非空值）
        if record1.facebook or record2.facebook:
            assert merged.facebook is not None
        if record1.twitter or record2.twitter:
            assert merged.twitter is not None
        if record1.instagram or record2.instagram:
            assert merged.instagram is not None


# ============================================================================
# 边界情况测试
# ============================================================================

class TestEdgeCases:
    """边界情况测试"""
    
    def test_empty_record_list(self):
        """空记录列表应该返回 None"""
        deduplicator = DataDeduplicator()
        record = BusinessRecord(email='test@example.com')
        
        duplicate = deduplicator.check_duplicate(record, [])
        assert duplicate is None
    
    def test_record_without_email(self):
        """没有邮箱的记录不应该被检测为重复"""
        deduplicator = DataDeduplicator()
        record1 = BusinessRecord(name='Business 1')
        record2 = BusinessRecord(name='Business 2')
        
        duplicate = deduplicator.check_duplicate(record1, [record2])
        assert duplicate is None
    
    def test_case_insensitive_email_matching(self):
        """邮箱匹配应该不区分大小写"""
        deduplicator = DataDeduplicator()
        record1 = BusinessRecord(email='Test@Example.COM')
        record2 = BusinessRecord(email='test@example.com')
        
        duplicate = deduplicator.check_duplicate(record2, [record1])
        assert duplicate is not None
    
    def test_deduplicate_list(self):
        """测试列表去重功能"""
        deduplicator = DataDeduplicator()
        records = [
            BusinessRecord(email='a@test.com', name='A1'),
            BusinessRecord(email='b@test.com', name='B'),
            BusinessRecord(email='a@test.com', name='A2', website='http://a.com'),
        ]
        
        result = deduplicator.deduplicate_list(records)
        
        # 应该只有2条记录（a@test.com 被合并）
        assert len(result) == 2
        
        # 找到合并后的 a@test.com 记录
        a_record = next((r for r in result if r.email == 'a@test.com'), None)
        assert a_record is not None
        # 应该保留 website（来自更完整的记录）
        assert a_record.website == 'http://a.com'
