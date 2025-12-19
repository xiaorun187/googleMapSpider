"""
数据库唯一性判断逻辑属性测试
使用 Hypothesis 进行属性测试，验证基于 name + website 的唯一性判断

**Feature: database-uniqueness-refactor**
"""
import pytest
from hypothesis import given, strategies as st, settings, assume
import string
import sys
import os
import sqlite3
import tempfile
import uuid

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.business_record import BusinessRecord
from utils.data_deduplicator import DataDeduplicator


# ============================================================================
# 测试策略（Generators）
# ============================================================================

@st.composite
def valid_name(draw):
    """生成有效的商家名称"""
    name = draw(st.text(
        alphabet=string.ascii_letters + string.digits + ' ',
        min_size=1,
        max_size=50
    ))
    # 确保名称不为空白
    if not name.strip():
        name = 'Business'
    return name.strip()


@st.composite
def valid_website(draw):
    """生成有效的网站地址"""
    protocol = draw(st.sampled_from(['http://', 'https://']))
    domain = draw(st.text(
        alphabet=string.ascii_lowercase + string.digits,
        min_size=3,
        max_size=20
    ))
    if not domain:
        domain = 'example'
    tld = draw(st.sampled_from(['.com', '.org', '.net', '.io']))
    return f"{protocol}{domain}{tld}"


@st.composite
def valid_email(draw):
    """生成有效的邮箱地址"""
    local = draw(st.text(
        alphabet=string.ascii_lowercase + string.digits,
        min_size=3,
        max_size=10
    ))
    if not local:
        local = 'user'
    domain = draw(st.text(
        alphabet=string.ascii_lowercase,
        min_size=3,
        max_size=8
    ))
    if not domain:
        domain = 'example'
    tld = draw(st.sampled_from(['com', 'org', 'net', 'io']))
    return f"{local}@{domain}.{tld}"


@st.composite
def business_record_with_name_website(draw):
    """生成带有 name 和 website 的商家记录"""
    return BusinessRecord(
        name=draw(valid_name()),
        website=draw(st.one_of(st.none(), valid_website())),
        email=draw(st.one_of(st.none(), valid_email())),
        city=draw(st.one_of(st.none(), st.text(min_size=0, max_size=30)))
    )


@st.composite
def two_records_same_name_website(draw):
    """生成两条具有相同 name 和 website 的记录"""
    name = draw(valid_name())
    website = draw(st.one_of(st.none(), valid_website()))
    
    record1 = BusinessRecord(
        name=name,
        website=website,
        email=draw(st.one_of(st.none(), valid_email())),
        city=draw(st.one_of(st.none(), st.text(min_size=0, max_size=30)))
    )
    record2 = BusinessRecord(
        name=name,
        website=website,
        email=draw(st.one_of(st.none(), valid_email())),
        city=draw(st.one_of(st.none(), st.text(min_size=0, max_size=30)))
    )
    return record1, record2


@st.composite
def two_records_different_name(draw):
    """生成两条具有不同 name 的记录"""
    name1 = draw(valid_name())
    name2 = draw(valid_name())
    assume(name1.lower() != name2.lower())
    
    website = draw(st.one_of(st.none(), valid_website()))
    
    record1 = BusinessRecord(name=name1, website=website)
    record2 = BusinessRecord(name=name2, website=website)
    return record1, record2


@st.composite
def two_records_different_website(draw):
    """生成两条具有不同 website 的记录"""
    name = draw(valid_name())
    website1 = draw(valid_website())
    website2 = draw(valid_website())
    assume(website1.lower() != website2.lower())
    
    record1 = BusinessRecord(name=name, website=website1)
    record2 = BusinessRecord(name=name, website=website2)
    return record1, record2


# ============================================================================
# Property 4: Unique ID Generation
# **Feature: database-uniqueness-refactor, Property 4: Unique ID Generation**
# **Validates: Requirements 2.1, 2.2**
# ============================================================================

class TestUniqueIdGeneration:
    """Property 4: unique_id 唯一性生成"""
    
    @given(count=st.integers(min_value=2, max_value=50))
    @settings(max_examples=100)
    def test_unique_id_uniqueness(self, count):
        """
        *For any* set of generated unique_ids, each id SHALL be distinct.
        **Feature: database-uniqueness-refactor, Property 4: Unique ID Generation**
        **Validates: Requirements 2.1, 2.2**
        """
        from db import generate_unique_id
        
        ids = [generate_unique_id() for _ in range(count)]
        
        # 验证所有 ID 都是唯一的
        assert len(ids) == len(set(ids)), \
            f"Generated {count} IDs but only {len(set(ids))} are unique"
    
    @given(st.data())
    @settings(max_examples=100)
    def test_unique_id_format(self, data):
        """
        *For any* generated unique_id, it SHALL be a valid UUID format.
        **Feature: database-uniqueness-refactor, Property 4: Unique ID Generation**
        **Validates: Requirements 2.1**
        """
        from db import generate_unique_id
        
        uid = generate_unique_id()
        
        # 验证是有效的 UUID 格式
        try:
            uuid.UUID(uid)
        except ValueError:
            pytest.fail(f"Generated ID '{uid}' is not a valid UUID")


# ============================================================================
# Property 1: Duplicate Detection by Name and Website
# **Feature: database-uniqueness-refactor, Property 1: Duplicate Detection**
# **Validates: Requirements 1.1**
# ============================================================================

class TestDuplicateDetection:
    """Property 1: 基于 name + website 的重复检测"""
    
    @given(records=two_records_same_name_website())
    @settings(max_examples=100)
    def test_same_name_website_is_duplicate(self, records):
        """
        *For any* two records with identical name and website,
        the system SHALL identify them as duplicates.
        **Feature: database-uniqueness-refactor, Property 1: Duplicate Detection**
        **Validates: Requirements 1.1**
        """
        record1, record2 = records
        deduplicator = DataDeduplicator()
        
        # 检查重复
        duplicate = deduplicator.check_duplicate(record2, [record1])
        
        assert duplicate is not None, \
            f"Records with same name '{record1.name}' and website '{record1.website}' should be duplicates"
    
    @given(records=two_records_same_name_website())
    @settings(max_examples=100)
    def test_equality_by_name_website(self, records):
        """
        *For any* two BusinessRecord objects with same name and website,
        they SHALL be equal according to __eq__.
        **Feature: database-uniqueness-refactor, Property 1: Duplicate Detection**
        **Validates: Requirements 1.1**
        """
        record1, record2 = records
        
        assert record1 == record2, \
            f"Records with same name and website should be equal"
        assert hash(record1) == hash(record2), \
            f"Records with same name and website should have same hash"


# ============================================================================
# Property 2: Distinct Records with Different Name
# **Feature: database-uniqueness-refactor, Property 2: Different Name**
# **Validates: Requirements 1.2, 1.4**
# ============================================================================

class TestDistinctRecordsDifferentName:
    """Property 2: 不同 name 的记录应被识别为不同数据"""
    
    @given(records=two_records_different_name())
    @settings(max_examples=100)
    def test_different_name_not_duplicate(self, records):
        """
        *For any* two records with different name values,
        the system SHALL identify them as distinct entries.
        **Feature: database-uniqueness-refactor, Property 2: Different Name**
        **Validates: Requirements 1.2, 1.4**
        """
        record1, record2 = records
        deduplicator = DataDeduplicator()
        
        # 检查不应该是重复
        duplicate = deduplicator.check_duplicate(record2, [record1])
        
        assert duplicate is None, \
            f"Records with different names '{record1.name}' and '{record2.name}' should not be duplicates"
    
    @given(records=two_records_different_name())
    @settings(max_examples=100)
    def test_inequality_by_different_name(self, records):
        """
        *For any* two BusinessRecord objects with different names,
        they SHALL NOT be equal according to __eq__.
        **Feature: database-uniqueness-refactor, Property 2: Different Name**
        **Validates: Requirements 1.2, 1.4**
        """
        record1, record2 = records
        
        assert record1 != record2, \
            f"Records with different names should not be equal"


# ============================================================================
# Property 3: Distinct Records with Different Website
# **Feature: database-uniqueness-refactor, Property 3: Different Website**
# **Validates: Requirements 1.3, 1.4**
# ============================================================================

class TestDistinctRecordsDifferentWebsite:
    """Property 3: 不同 website 的记录应被识别为不同数据"""
    
    @given(records=two_records_different_website())
    @settings(max_examples=100)
    def test_different_website_not_duplicate(self, records):
        """
        *For any* two records with different website values,
        the system SHALL identify them as distinct entries.
        **Feature: database-uniqueness-refactor, Property 3: Different Website**
        **Validates: Requirements 1.3, 1.4**
        """
        record1, record2 = records
        deduplicator = DataDeduplicator()
        
        # 检查不应该是重复
        duplicate = deduplicator.check_duplicate(record2, [record1])
        
        assert duplicate is None, \
            f"Records with different websites '{record1.website}' and '{record2.website}' should not be duplicates"
    
    @given(records=two_records_different_website())
    @settings(max_examples=100)
    def test_inequality_by_different_website(self, records):
        """
        *For any* two BusinessRecord objects with different websites,
        they SHALL NOT be equal according to __eq__.
        **Feature: database-uniqueness-refactor, Property 3: Different Website**
        **Validates: Requirements 1.3, 1.4**
        """
        record1, record2 = records
        
        assert record1 != record2, \
            f"Records with different websites should not be equal"


# ============================================================================
# Property 5: Unique ID Presence in Query Results
# **Feature: database-uniqueness-refactor, Property 5: Unique ID in Results**
# **Validates: Requirements 2.3**
# ============================================================================

class TestUniqueIdInQueryResults:
    """Property 5: 查询结果中包含 unique_id"""
    
    @given(record=business_record_with_name_website())
    @settings(max_examples=50)
    def test_unique_id_in_serialization(self, record):
        """
        *For any* BusinessRecord with a unique_id,
        the serialized form SHALL include the unique_id field.
        **Feature: database-uniqueness-refactor, Property 5: Unique ID in Results**
        **Validates: Requirements 2.3**
        """
        # 设置 unique_id
        record.unique_id = str(uuid.uuid4())
        
        # 序列化
        data = record.to_dict()
        
        assert 'unique_id' in data, "unique_id field missing from dict"
        assert data['unique_id'] == record.unique_id, \
            f"unique_id mismatch: expected '{record.unique_id}', got '{data['unique_id']}'"


# ============================================================================
# Property 6: Duplicate Insertion Error Handling
# **Feature: database-uniqueness-refactor, Property 6: Error Handling**
# **Validates: Requirements 4.1, 4.2, 4.3**
# ============================================================================

class TestDuplicateInsertionErrorHandling:
    """Property 6: 重复插入错误处理"""
    
    @given(records=two_records_same_name_website())
    @settings(max_examples=50)
    def test_deduplicate_list_merges_duplicates(self, records):
        """
        *For any* list containing duplicate records (same name + website),
        deduplicate_list SHALL merge them into a single record.
        **Feature: database-uniqueness-refactor, Property 6: Error Handling**
        **Validates: Requirements 4.1, 4.2, 4.3**
        """
        record1, record2 = records
        deduplicator = DataDeduplicator()
        
        # 去重
        result = deduplicator.deduplicate_list([record1, record2])
        
        # 应该只有一条记录
        assert len(result) == 1, \
            f"Expected 1 record after deduplication, got {len(result)}"


# ============================================================================
# Property 7: BusinessRecord Round-Trip with Unique ID
# **Feature: database-uniqueness-refactor, Property 7: Round-Trip**
# **Validates: Requirements 2.3**
# ============================================================================

class TestBusinessRecordRoundTripWithUniqueId:
    """Property 7: BusinessRecord 序列化往返（包含 unique_id）"""
    
    @given(record=business_record_with_name_website())
    @settings(max_examples=100)
    def test_json_round_trip_with_unique_id(self, record):
        """
        *For any* BusinessRecord with unique_id, serializing to JSON
        and deserializing SHALL produce an equivalent object.
        **Feature: database-uniqueness-refactor, Property 7: Round-Trip**
        **Validates: Requirements 2.3**
        """
        # 设置 unique_id
        record.unique_id = str(uuid.uuid4())
        
        # 序列化
        json_str = record.to_json()
        
        # 反序列化
        restored = BusinessRecord.from_json(json_str)
        
        # 验证 unique_id 被保留
        assert restored.unique_id == record.unique_id, \
            f"unique_id not preserved: expected '{record.unique_id}', got '{restored.unique_id}'"
        assert restored.name == record.name
        assert restored.website == record.website
    
    @given(record=business_record_with_name_website())
    @settings(max_examples=100)
    def test_dict_round_trip_with_unique_id(self, record):
        """
        *For any* BusinessRecord with unique_id, converting to dict
        and back SHALL produce an equivalent object.
        **Feature: database-uniqueness-refactor, Property 7: Round-Trip**
        **Validates: Requirements 2.3**
        """
        # 设置 unique_id
        record.unique_id = str(uuid.uuid4())
        
        # 转换为字典
        data = record.to_dict()
        
        # 从字典恢复
        restored = BusinessRecord.from_dict(data)
        
        # 验证 unique_id 被保留
        assert restored.unique_id == record.unique_id
        assert restored.name == record.name
        assert restored.website == record.website


# ============================================================================
# 边界情况测试
# ============================================================================

class TestEdgeCases:
    """边界情况测试"""
    
    def test_null_name_and_website(self):
        """测试 name 和 website 都为 None 的情况"""
        record1 = BusinessRecord(name='', website=None)
        record2 = BusinessRecord(name='', website=None)
        
        # 应该被视为相同
        assert record1 == record2
    
    def test_empty_string_vs_none(self):
        """测试空字符串和 None 的等价性"""
        record1 = BusinessRecord(name='Test', website='')
        record2 = BusinessRecord(name='Test', website=None)
        
        # 空字符串和 None 应该被视为等价
        assert record1 == record2
    
    def test_whitespace_handling(self):
        """测试空白字符处理"""
        record1 = BusinessRecord(name='  Test  ', website='http://test.com')
        record2 = BusinessRecord(name='Test', website='http://test.com')
        
        # 应该被视为相同（去除首尾空白）
        assert record1 == record2
    
    def test_case_insensitive_comparison(self):
        """测试大小写不敏感比较"""
        record1 = BusinessRecord(name='TEST', website='HTTP://TEST.COM')
        record2 = BusinessRecord(name='test', website='http://test.com')
        
        # 应该被视为相同（大小写不敏感）
        assert record1 == record2
    
    def test_special_characters_in_name(self):
        """测试名称中的特殊字符"""
        record1 = BusinessRecord(name='Test & Co.', website='http://test.com')
        record2 = BusinessRecord(name='Test & Co.', website='http://test.com')
        
        assert record1 == record2
    
    def test_unicode_characters(self):
        """测试 Unicode 字符"""
        record1 = BusinessRecord(name='测试公司', website='http://test.com')
        record2 = BusinessRecord(name='测试公司', website='http://test.com')
        
        assert record1 == record2
    
    def test_deduplicator_with_mixed_records(self):
        """测试去重器处理混合记录"""
        deduplicator = DataDeduplicator()
        
        records = [
            BusinessRecord(name='A', website='http://a.com'),
            BusinessRecord(name='A', website='http://a.com'),  # 重复
            BusinessRecord(name='B', website='http://a.com'),  # 不同 name
            BusinessRecord(name='A', website='http://b.com'),  # 不同 website
        ]
        
        result = deduplicator.deduplicate_list(records)
        
        # 应该有 3 条不同的记录
        assert len(result) == 3
