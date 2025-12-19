"""
HistoryManager 属性测试
使用 Hypothesis 进行属性测试，验证 HistoryManager 的正确性

**Feature: data-collection-optimization**
"""
import pytest
from hypothesis import given, strategies as st, settings, assume
import string
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.history_manager import HistoryManager


# ============================================================================
# Property 25: Business Record Validation
# **Feature: data-collection-optimization, Property 25: Business Record Validation**
# **Validates: Requirements 11.3, 11.7**
# ============================================================================

class TestBusinessRecordValidation:
    """Property 25: 商家记录验证"""
    
    @pytest.fixture
    def manager(self):
        """创建 HistoryManager 实例"""
        return HistoryManager()
    
    def test_empty_name_rejected_for_create(self, manager):
        """
        *For any* business record without a name,
        the validation SHALL reject it for creation.
        **Feature: data-collection-optimization, Property 25: Business Record Validation**
        **Validates: Requirements 11.3, 11.7**
        """
        data = {
            'name': '',
            'email': 'test@example.com'
        }
        
        is_valid, errors = manager.validate_record(data, is_update=False)
        
        assert not is_valid
        assert any('名称' in e for e in errors)
    
    def test_empty_name_allowed_for_update(self, manager):
        """更新时允许空名称（只更新其他字段）"""
        data = {
            'name': '',
            'email': 'test@example.com'
        }
        
        is_valid, errors = manager.validate_record(data, is_update=True)
        
        # 更新时名称可以为空
        assert is_valid or not any('名称' in e for e in errors)
    
    @given(email=st.text(min_size=1, max_size=20))
    @settings(max_examples=50)
    def test_invalid_email_format_rejected(self, email):
        """
        *For any* invalid email format,
        the validation SHALL reject it.
        **Feature: data-collection-optimization, Property 25: Business Record Validation**
        **Validates: Requirements 11.3, 11.7**
        """
        manager = HistoryManager()
        
        # 确保生成的不是有效邮箱
        assume('@' not in email or '.' not in email)
        
        data = {
            'name': 'Test Business',
            'email': email
        }
        
        is_valid, errors = manager.validate_record(data)
        
        # 无效邮箱应该被拒绝
        if email and '@' not in email:
            assert not is_valid
            assert any('邮箱' in e for e in errors)
    
    def test_valid_email_accepted(self, manager):
        """有效邮箱应该被接受"""
        data = {
            'name': 'Test Business',
            'email': 'test@example.com'
        }
        
        is_valid, errors = manager.validate_record(data)
        
        assert is_valid
        assert len(errors) == 0
    
    def test_invalid_url_rejected(self, manager):
        """
        *For any* invalid URL format,
        the validation SHALL reject it.
        **Feature: data-collection-optimization, Property 25: Business Record Validation**
        **Validates: Requirements 11.3, 11.7**
        """
        data = {
            'name': 'Test Business',
            'website': 'not-a-valid-url'
        }
        
        is_valid, errors = manager.validate_record(data)
        
        assert not is_valid
        assert any('URL' in e or '网站' in e for e in errors)
    
    def test_valid_url_accepted(self, manager):
        """有效URL应该被接受"""
        data = {
            'name': 'Test Business',
            'website': 'https://example.com'
        }
        
        is_valid, errors = manager.validate_record(data)
        
        assert is_valid
        assert len(errors) == 0
    
    @given(phone=st.text(alphabet=string.digits, min_size=1, max_size=7))
    @settings(max_examples=50)
    def test_short_phone_rejected(self, phone):
        """
        *For any* phone number with fewer than 8 digits,
        the validation SHALL reject it.
        **Feature: data-collection-optimization, Property 25: Business Record Validation**
        **Validates: Requirements 11.3, 11.7**
        """
        manager = HistoryManager()
        assume(len(phone) < 8)
        
        data = {
            'name': 'Test Business',
            'phones': [phone]
        }
        
        is_valid, errors = manager.validate_record(data)
        
        assert not is_valid
        assert any('电话' in e for e in errors)
    
    def test_valid_phone_accepted(self, manager):
        """有效电话号码应该被接受"""
        data = {
            'name': 'Test Business',
            'phones': ['12345678901']
        }
        
        is_valid, errors = manager.validate_record(data)
        
        assert is_valid
        assert len(errors) == 0
    
    def test_complete_valid_record(self, manager):
        """完整的有效记录应该通过验证"""
        data = {
            'name': 'Test Business',
            'email': 'test@example.com',
            'website': 'https://example.com',
            'phones': ['12345678901'],
            'city': 'Beijing'
        }
        
        is_valid, errors = manager.validate_record(data)
        
        assert is_valid
        assert len(errors) == 0


# ============================================================================
# 边界情况测试
# ============================================================================

class TestEdgeCases:
    """边界情况测试"""
    
    @pytest.fixture
    def manager(self):
        """创建 HistoryManager 实例"""
        return HistoryManager()
    
    def test_empty_data(self, manager):
        """空数据应该被拒绝（创建时）"""
        data = {}
        
        is_valid, errors = manager.validate_record(data, is_update=False)
        
        assert not is_valid
    
    def test_none_values(self, manager):
        """None值应该被正确处理"""
        data = {
            'name': 'Test',
            'email': None,
            'website': None,
            'phones': None
        }
        
        is_valid, errors = manager.validate_record(data)
        
        assert is_valid
    
    def test_phones_as_string(self, manager):
        """电话号码作为字符串应该被正确处理"""
        data = {
            'name': 'Test',
            'phones': '12345678901, 98765432109'
        }
        
        is_valid, errors = manager.validate_record(data)
        
        assert is_valid
    
    def test_multiple_validation_errors(self, manager):
        """多个验证错误应该全部报告"""
        data = {
            'name': '',
            'email': 'invalid-email',
            'website': 'invalid-url',
            'phones': ['123']  # 太短
        }
        
        is_valid, errors = manager.validate_record(data, is_update=False)
        
        assert not is_valid
        assert len(errors) >= 3  # 至少3个错误
