"""
PhoneValidator 属性测试
使用 Hypothesis 进行属性测试，验证 PhoneValidator 的正确性

**Feature: data-collection-optimization**
"""
import pytest
from hypothesis import given, strategies as st, settings, assume
import string
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from validators.phone_validator import PhoneValidator


# ============================================================================
# 测试策略（Generators）
# ============================================================================

@st.composite
def valid_phone_number(draw):
    """生成有效的电话号码（8-15位数字）"""
    digit_count = draw(st.integers(min_value=8, max_value=15))
    digits = draw(st.lists(
        st.sampled_from(string.digits),
        min_size=digit_count,
        max_size=digit_count
    ))
    return ''.join(digits)


@st.composite
def valid_phone_with_formatting(draw):
    """生成带格式的有效电话号码"""
    digit_count = draw(st.integers(min_value=8, max_value=15))
    digits = draw(st.lists(
        st.sampled_from(string.digits),
        min_size=digit_count,
        max_size=digit_count
    ))
    
    # 随机添加格式字符
    format_chars = [' ', '-', '(', ')', '.', '+']
    result = []
    
    for i, digit in enumerate(digits):
        # 随机在数字前添加格式字符
        if draw(st.booleans()) and i > 0:
            result.append(draw(st.sampled_from(format_chars)))
        result.append(digit)
    
    return ''.join(result)


@st.composite
def too_short_phone(draw):
    """生成过短的电话号码（少于8位数字）"""
    digit_count = draw(st.integers(min_value=1, max_value=7))
    digits = draw(st.lists(
        st.sampled_from(string.digits),
        min_size=digit_count,
        max_size=digit_count
    ))
    return ''.join(digits)


@st.composite
def too_long_phone(draw):
    """生成过长的电话号码（超过15位数字）"""
    digit_count = draw(st.integers(min_value=16, max_value=30))
    digits = draw(st.lists(
        st.sampled_from(string.digits),
        min_size=digit_count,
        max_size=digit_count
    ))
    return ''.join(digits)


@st.composite
def phone_with_mixed_content(draw):
    """生成混合内容的字符串，包含指定数量的数字"""
    digit_count = draw(st.integers(min_value=0, max_value=20))
    
    # 生成数字
    digits = [draw(st.sampled_from(string.digits)) for _ in range(digit_count)]
    
    # 生成非数字字符
    non_digit_count = draw(st.integers(min_value=0, max_value=10))
    non_digits = [draw(st.sampled_from(string.ascii_letters + ' -()./+')) 
                  for _ in range(non_digit_count)]
    
    # 混合并打乱
    all_chars = digits + non_digits
    draw(st.randoms()).shuffle(all_chars)
    
    return ''.join(all_chars), digit_count


# ============================================================================
# Property 4: Phone Number Length Validation
# **Feature: data-collection-optimization, Property 4: Phone Number Length Validation**
# **Validates: Requirements 1.4**
# ============================================================================

class TestPhoneNumberLengthValidation:
    """Property 4: 电话号码长度验证"""
    
    @given(phone=valid_phone_number())
    @settings(max_examples=100)
    def test_valid_length_phones_are_accepted(self, phone):
        """
        *For any* phone number with 8-15 digits, the PhoneValidator SHALL accept it.
        **Feature: data-collection-optimization, Property 4: Phone Number Length Validation**
        **Validates: Requirements 1.4**
        """
        validator = PhoneValidator()
        assert validator.validate(phone), f"Valid phone '{phone}' with {len(phone)} digits was rejected"
    
    @given(phone=valid_phone_with_formatting())
    @settings(max_examples=100)
    def test_formatted_valid_phones_are_accepted(self, phone):
        """
        *For any* formatted phone number with 8-15 digits, the PhoneValidator SHALL accept it.
        **Feature: data-collection-optimization, Property 4: Phone Number Length Validation**
        **Validates: Requirements 1.4**
        """
        validator = PhoneValidator()
        digit_count = validator.get_digit_count(phone)
        assume(8 <= digit_count <= 15)
        assert validator.validate(phone), f"Valid formatted phone '{phone}' was rejected"
    
    @given(phone=too_short_phone())
    @settings(max_examples=100)
    def test_too_short_phones_are_rejected(self, phone):
        """
        *For any* phone number with fewer than 8 digits, the PhoneValidator SHALL reject it.
        **Feature: data-collection-optimization, Property 4: Phone Number Length Validation**
        **Validates: Requirements 1.4**
        """
        validator = PhoneValidator()
        assert not validator.validate(phone), f"Too short phone '{phone}' was accepted"
    
    @given(phone=too_long_phone())
    @settings(max_examples=100)
    def test_too_long_phones_are_rejected(self, phone):
        """
        *For any* phone number with more than 15 digits, the PhoneValidator SHALL reject it.
        **Feature: data-collection-optimization, Property 4: Phone Number Length Validation**
        **Validates: Requirements 1.4**
        """
        validator = PhoneValidator()
        assert not validator.validate(phone), f"Too long phone '{phone}' was accepted"
    
    @given(data=phone_with_mixed_content())
    @settings(max_examples=100)
    def test_digit_count_determines_validity(self, data):
        """
        *For any* string, the PhoneValidator SHALL accept it if and only if
        it contains between 8 and 15 digits (inclusive).
        **Feature: data-collection-optimization, Property 4: Phone Number Length Validation**
        **Validates: Requirements 1.4**
        """
        phone, expected_digit_count = data
        validator = PhoneValidator()
        
        is_valid = validator.validate(phone)
        expected_valid = 8 <= expected_digit_count <= 15
        
        assert is_valid == expected_valid, \
            f"Phone '{phone}' with {expected_digit_count} digits: expected valid={expected_valid}, got {is_valid}"


# ============================================================================
# 数字提取测试
# ============================================================================

class TestDigitExtraction:
    """数字提取功能测试"""
    
    @given(digits=st.text(alphabet=string.digits, min_size=0, max_size=20))
    @settings(max_examples=100)
    def test_extract_digits_from_pure_digits(self, digits):
        """纯数字字符串应该原样返回"""
        validator = PhoneValidator()
        extracted = validator.extract_digits(digits)
        assert extracted == digits
    
    @given(
        digits=st.text(alphabet=string.digits, min_size=1, max_size=10),
        non_digits=st.text(alphabet=string.ascii_letters + ' -().', min_size=1, max_size=10)
    )
    @settings(max_examples=100)
    def test_extract_digits_removes_non_digits(self, digits, non_digits):
        """应该只保留数字，移除所有非数字字符"""
        validator = PhoneValidator()
        mixed = digits + non_digits
        extracted = validator.extract_digits(mixed)
        assert extracted == digits


# ============================================================================
# 边界情况测试
# ============================================================================

class TestEdgeCases:
    """边界情况测试"""
    
    def test_empty_phone(self):
        """空字符串应该被拒绝"""
        validator = PhoneValidator()
        assert not validator.validate('')
    
    def test_none_phone(self):
        """None 应该被拒绝"""
        validator = PhoneValidator()
        assert not validator.validate(None)
    
    def test_exactly_8_digits(self):
        """正好8位数字应该被接受"""
        validator = PhoneValidator()
        assert validator.validate('12345678')
    
    def test_exactly_15_digits(self):
        """正好15位数字应该被接受"""
        validator = PhoneValidator()
        assert validator.validate('123456789012345')
    
    def test_7_digits_rejected(self):
        """7位数字应该被拒绝"""
        validator = PhoneValidator()
        assert not validator.validate('1234567')
    
    def test_16_digits_rejected(self):
        """16位数字应该被拒绝"""
        validator = PhoneValidator()
        assert not validator.validate('1234567890123456')
    
    def test_common_phone_formats(self):
        """测试常见电话格式"""
        validator = PhoneValidator()
        valid_phones = [
            '+1-234-567-8901',
            '(123) 456-7890',
            '123.456.7890',
            '+86 138 0000 0000',
            '13800000000',
        ]
        for phone in valid_phones:
            assert validator.validate(phone), f"Common format phone '{phone}' was rejected"
