"""
BusinessRecord 属性测试
使用 Hypothesis 进行属性测试，验证 BusinessRecord 的正确性

**Feature: data-collection-optimization**
"""
import pytest
from hypothesis import given, strategies as st, settings, assume
import string
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.business_record import BusinessRecord


# ============================================================================
# 测试策略（Generators）
# ============================================================================

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
def business_record_data(draw):
    """生成商家记录数据"""
    phones = draw(st.lists(
        st.text(alphabet=string.digits, min_size=8, max_size=15),
        min_size=0,
        max_size=3
    ))
    
    return BusinessRecord(
        id=draw(st.one_of(st.none(), st.integers(min_value=1, max_value=10000))),
        name=draw(st.text(min_size=0, max_size=50)),
        website=draw(st.one_of(st.none(), st.text(min_size=0, max_size=50))),
        email=draw(st.one_of(st.none(), valid_email())),
        phones=phones,
        facebook=draw(st.one_of(st.none(), st.text(min_size=0, max_size=50))),
        twitter=draw(st.one_of(st.none(), st.text(min_size=0, max_size=50))),
        instagram=draw(st.one_of(st.none(), st.text(min_size=0, max_size=50))),
        linkedin=draw(st.one_of(st.none(), st.text(min_size=0, max_size=50))),
        whatsapp=draw(st.one_of(st.none(), st.text(min_size=0, max_size=50))),
        youtube=draw(st.one_of(st.none(), st.text(min_size=0, max_size=50))),
        city=draw(st.one_of(st.none(), st.text(min_size=0, max_size=30))),
        send_count=draw(st.integers(min_value=0, max_value=1000)),
        created_at=draw(st.one_of(st.none(), st.text(min_size=0, max_size=30))),
        updated_at=draw(st.one_of(st.none(), st.text(min_size=0, max_size=30)))
    )


@st.composite
def business_record_with_city(draw):
    """生成带有城市字段的商家记录"""
    city = draw(st.text(
        alphabet=string.ascii_letters + ' ',
        min_size=2,
        max_size=20
    ))
    # 确保城市不为空
    if not city.strip():
        city = 'Beijing'
    
    return BusinessRecord(
        name=draw(st.text(min_size=1, max_size=30)),
        email=draw(valid_email()),
        city=city
    )


# ============================================================================
# Property 11: Business Record Round-Trip
# **Feature: data-collection-optimization, Property 11: Business Record Round-Trip**
# **Validates: Requirements 2.5**
# ============================================================================

class TestBusinessRecordRoundTrip:
    """Property 11: BusinessRecord 序列化往返"""
    
    @given(record=business_record_data())
    @settings(max_examples=100)
    def test_json_round_trip(self, record):
        """
        *For any* BusinessRecord object, serializing to JSON and then
        deserializing SHALL produce an equivalent BusinessRecord object.
        **Feature: data-collection-optimization, Property 11: Business Record Round-Trip**
        **Validates: Requirements 2.5**
        """
        # 序列化
        json_str = record.to_json()
        
        # 反序列化
        restored = BusinessRecord.from_json(json_str)
        
        # 验证等价性
        assert restored.id == record.id
        assert restored.name == record.name
        assert restored.website == record.website
        assert restored.email == record.email
        assert set(restored.phones) == set(record.phones)
        assert restored.facebook == record.facebook
        assert restored.twitter == record.twitter
        assert restored.instagram == record.instagram
        assert restored.linkedin == record.linkedin
        assert restored.whatsapp == record.whatsapp
        assert restored.youtube == record.youtube
        assert restored.city == record.city
        assert restored.send_count == record.send_count
    
    @given(record=business_record_data())
    @settings(max_examples=100)
    def test_dict_round_trip(self, record):
        """
        *For any* BusinessRecord object, converting to dict and back
        SHALL produce an equivalent BusinessRecord object.
        **Feature: data-collection-optimization, Property 11: Business Record Round-Trip**
        **Validates: Requirements 2.5**
        """
        # 转换为字典
        data = record.to_dict()
        
        # 从字典恢复
        restored = BusinessRecord.from_dict(data)
        
        # 验证等价性
        assert restored.id == record.id
        assert restored.name == record.name
        assert restored.website == record.website
        assert restored.email == record.email
        assert set(restored.phones) == set(record.phones)
        assert restored.facebook == record.facebook
        assert restored.city == record.city


# ============================================================================
# Property 22: City Field Presence
# **Feature: data-collection-optimization, Property 22: City Field Presence**
# **Validates: Requirements 9.2**
# ============================================================================

class TestCityFieldPresence:
    """Property 22: 城市字段存在性"""
    
    @given(record=business_record_with_city())
    @settings(max_examples=100)
    def test_city_field_preserved_in_serialization(self, record):
        """
        *For any* BusinessRecord with a city field,
        the city field SHALL be preserved after serialization.
        **Feature: data-collection-optimization, Property 22: City Field Presence**
        **Validates: Requirements 9.2**
        """
        # 确保原始记录有城市
        assume(record.city and record.city.strip())
        
        # 序列化并反序列化
        json_str = record.to_json()
        restored = BusinessRecord.from_json(json_str)
        
        # 验证城市字段被保留
        assert restored.city == record.city, \
            f"City field not preserved: expected '{record.city}', got '{restored.city}'"
    
    @given(record=business_record_with_city())
    @settings(max_examples=100)
    def test_city_field_in_dict(self, record):
        """
        *For any* BusinessRecord with a city field,
        the dict representation SHALL include the city field.
        **Feature: data-collection-optimization, Property 22: City Field Presence**
        **Validates: Requirements 9.2**
        """
        assume(record.city and record.city.strip())
        
        data = record.to_dict()
        
        assert 'city' in data, "City field missing from dict"
        assert data['city'] == record.city


# ============================================================================
# 边界情况测试
# ============================================================================

class TestEdgeCases:
    """边界情况测试"""
    
    def test_empty_record(self):
        """空记录应该能正常序列化"""
        record = BusinessRecord()
        json_str = record.to_json()
        restored = BusinessRecord.from_json(json_str)
        
        assert restored.name == ''
        assert restored.email is None
        assert restored.phones == []
    
    def test_record_with_all_fields(self):
        """所有字段都有值的记录应该能正常序列化"""
        record = BusinessRecord(
            id=1,
            name='Test Business',
            website='https://test.com',
            email='test@test.com',
            phones=['12345678', '87654321'],
            facebook='fb.com/test',
            twitter='twitter.com/test',
            instagram='instagram.com/test',
            linkedin='linkedin.com/test',
            whatsapp='+1234567890',
            youtube='youtube.com/test',
            city='Beijing',
            send_count=5,
            created_at='2024-01-01',
            updated_at='2024-01-02'
        )
        
        json_str = record.to_json()
        restored = BusinessRecord.from_json(json_str)
        
        assert restored.id == 1
        assert restored.name == 'Test Business'
        assert restored.city == 'Beijing'
        assert len(restored.phones) == 2
    
    def test_completeness_score(self):
        """测试完整度分数计算"""
        empty_record = BusinessRecord()
        full_record = BusinessRecord(
            name='Test',
            website='https://test.com',
            email='test@test.com',
            phones=['12345678'],
            facebook='fb',
            twitter='tw',
            instagram='ig',
            linkedin='li',
            whatsapp='wa',
            youtube='yt',
            city='Beijing',
            product='sofa'  # 添加 product 字段
        )
        
        empty_score = empty_record.get_completeness_score()
        full_score = full_record.get_completeness_score()
        
        assert empty_score == 0
        assert full_score == 1.0
    
    def test_merge_with(self):
        """测试记录合并功能"""
        record1 = BusinessRecord(
            email='test@test.com',
            name='Business 1',
            phones=['111']
        )
        record2 = BusinessRecord(
            email='test@test.com',
            website='https://test.com',
            phones=['222']
        )
        
        merged = record1.merge_with(record2)
        
        assert merged.name == 'Business 1'
        assert merged.website == 'https://test.com'
        assert set(merged.phones) == {'111', '222'}
