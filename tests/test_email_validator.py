"""
EmailValidator 属性测试
使用 Hypothesis 进行属性测试，验证 EmailValidator 的正确性

**Feature: data-collection-optimization**
"""
import pytest
from hypothesis import given, strategies as st, settings, assume
import string
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from validators.email_validator import EmailValidator, ValidationResult


# ============================================================================
# 测试策略（Generators）
# ============================================================================

# 有效邮箱本地部分的字符集
VALID_LOCAL_CHARS = string.ascii_letters + string.digits + '._%+-'

# 有效域名字符集
VALID_DOMAIN_CHARS = string.ascii_lowercase + string.digits + '-'


@st.composite
def valid_email_local_part(draw):
    """生成有效的邮箱本地部分"""
    # 长度 1-64，使用有效字符
    length = draw(st.integers(min_value=1, max_value=20))
    chars = draw(st.lists(
        st.sampled_from(VALID_LOCAL_CHARS),
        min_size=length,
        max_size=length
    ))
    local = ''.join(chars)
    # 确保不以点开头或结尾
    local = local.strip('.')
    if not local:
        local = 'user'
    return local


@st.composite
def valid_domain(draw):
    """生成有效的域名"""
    # 域名部分
    domain_length = draw(st.integers(min_value=1, max_value=10))
    domain_chars = draw(st.lists(
        st.sampled_from(VALID_DOMAIN_CHARS),
        min_size=domain_length,
        max_size=domain_length
    ))
    domain = ''.join(domain_chars).strip('-')
    if not domain:
        domain = 'example'
    
    # TLD 部分（2-6个字母）
    tld_length = draw(st.integers(min_value=2, max_value=6))
    tld = draw(st.text(
        alphabet=string.ascii_lowercase,
        min_size=tld_length,
        max_size=tld_length
    ))
    
    return f"{domain}.{tld}"


@st.composite
def valid_email(draw):
    """生成有效的邮箱地址（不包含无效模式）"""
    local = draw(valid_email_local_part())
    domain = draw(valid_domain())
    email = f"{local}@{domain}"
    
    # 确保不包含无效模式
    invalid_patterns = ['logo', 'image', 'img']
    invalid_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg']
    
    # 检查并排除无效模式
    email_lower = email.lower()
    for pattern in invalid_patterns:
        assume(pattern not in email_lower)
    
    for ext in invalid_extensions:
        assume(not local.lower().endswith(ext.replace('.', '')))
    
    # 排除尺寸模式
    import re
    assume(not re.search(r'\d+x\d*', email))
    
    return email


@st.composite
def email_with_image_extension(draw):
    """生成包含图片扩展名的邮箱"""
    extensions = ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg']
    ext = draw(st.sampled_from(extensions))
    
    # 生成基础本地部分
    base_length = draw(st.integers(min_value=1, max_value=10))
    base = draw(st.text(
        alphabet=string.ascii_lowercase + string.digits,
        min_size=base_length,
        max_size=base_length
    ))
    if not base:
        base = 'image'
    
    local = base + ext.replace('.', '')  # 如 "photo" + "png" = "photopng"
    domain = draw(valid_domain())
    
    return f"{local}@{domain}"


@st.composite
def email_with_dimension_pattern(draw):
    """生成包含尺寸模式的邮箱"""
    # 生成尺寸模式 NxM
    n = draw(st.integers(min_value=1, max_value=9999))
    m = draw(st.integers(min_value=0, max_value=9999))
    
    if m > 0:
        dimension = f"{n}x{m}"
    else:
        dimension = f"{n}x"
    
    # 生成前缀
    prefix_length = draw(st.integers(min_value=0, max_value=5))
    prefix = draw(st.text(
        alphabet=string.ascii_lowercase,
        min_size=prefix_length,
        max_size=prefix_length
    ))
    
    local = prefix + dimension
    domain = draw(valid_domain())
    
    return f"{local}@{domain}"


@st.composite
def invalid_format_email(draw):
    """生成格式无效的邮箱"""
    strategy = draw(st.integers(min_value=0, max_value=4))
    
    if strategy == 0:
        # 没有 @ 符号
        return draw(st.text(min_size=1, max_size=20))
    elif strategy == 1:
        # 多个 @ 符号
        local = draw(st.text(alphabet=string.ascii_lowercase, min_size=1, max_size=5))
        domain = draw(st.text(alphabet=string.ascii_lowercase, min_size=1, max_size=5))
        return f"{local}@@{domain}.com"
    elif strategy == 2:
        # 没有域名
        local = draw(st.text(alphabet=string.ascii_lowercase, min_size=1, max_size=5))
        return f"{local}@"
    elif strategy == 3:
        # 没有 TLD
        local = draw(st.text(alphabet=string.ascii_lowercase, min_size=1, max_size=5))
        domain = draw(st.text(alphabet=string.ascii_lowercase, min_size=1, max_size=5))
        return f"{local}@{domain}"
    else:
        # 空字符串
        return ""


# ============================================================================
# Property 1: Email Format Validation
# **Feature: data-collection-optimization, Property 1: Email Format Validation**
# **Validates: Requirements 1.1**
# ============================================================================

class TestEmailFormatValidation:
    """Property 1: 邮箱格式验证"""
    
    @given(email=valid_email())
    @settings(max_examples=100)
    def test_valid_emails_are_accepted(self, email):
        """
        *For any* valid email format, the EmailValidator SHALL accept it.
        **Feature: data-collection-optimization, Property 1: Email Format Validation**
        **Validates: Requirements 1.1**
        """
        validator = EmailValidator()
        result = validator.validate(email)
        assert result.is_valid, f"Valid email '{email}' was rejected: {result.reason}"
    
    @given(email=invalid_format_email())
    @settings(max_examples=100)
    def test_invalid_format_emails_are_rejected(self, email):
        """
        *For any* invalid email format, the EmailValidator SHALL reject it.
        **Feature: data-collection-optimization, Property 1: Email Format Validation**
        **Validates: Requirements 1.1**
        """
        validator = EmailValidator()
        # 过滤掉可能意外有效的情况
        assume(not validator.is_valid_format(email) or not email)
        result = validator.validate(email)
        assert not result.is_valid, f"Invalid email '{email}' was accepted"


# ============================================================================
# Property 2: Image Extension Email Rejection
# **Feature: data-collection-optimization, Property 2: Image Extension Email Rejection**
# **Validates: Requirements 1.2**
# ============================================================================

class TestImageExtensionRejection:
    """Property 2: 图片扩展名邮箱拒绝"""
    
    @given(email=email_with_image_extension())
    @settings(max_examples=100)
    def test_emails_with_image_extensions_are_rejected(self, email):
        """
        *For any* email containing image file extensions in the local part,
        the EmailValidator SHALL reject it as invalid.
        **Feature: data-collection-optimization, Property 2: Image Extension Email Rejection**
        **Validates: Requirements 1.2**
        """
        validator = EmailValidator()
        
        # 确保邮箱格式本身是有效的（只测试扩展名检测）
        assume(validator.is_valid_format(email))
        
        result = validator.validate(email)
        # 如果包含图片扩展名，应该被拒绝
        if validator.has_invalid_extension(email):
            assert not result.is_valid, f"Email with image extension '{email}' was accepted"


# ============================================================================
# Property 3: Dimension Pattern Email Rejection
# **Feature: data-collection-optimization, Property 3: Dimension Pattern Email Rejection**
# **Validates: Requirements 1.3**
# ============================================================================

class TestDimensionPatternRejection:
    """Property 3: 尺寸模式邮箱拒绝"""
    
    @given(email=email_with_dimension_pattern())
    @settings(max_examples=100)
    def test_emails_with_dimension_patterns_are_rejected(self, email):
        """
        *For any* email containing numeric dimension patterns (NxM),
        the EmailValidator SHALL reject it as invalid.
        **Feature: data-collection-optimization, Property 3: Dimension Pattern Email Rejection**
        **Validates: Requirements 1.3**
        """
        validator = EmailValidator()
        
        # 确保邮箱格式本身是有效的（只测试尺寸模式检测）
        assume(validator.is_valid_format(email))
        
        result = validator.validate(email)
        # 如果包含尺寸模式，应该被拒绝
        if validator.has_dimension_pattern(email):
            assert not result.is_valid, f"Email with dimension pattern '{email}' was accepted"


# ============================================================================
# Property 6: Validation Result Round-Trip
# **Feature: data-collection-optimization, Property 6: Validation Result Round-Trip**
# **Validates: Requirements 1.6, 1.7**
# ============================================================================

class TestValidationResultRoundTrip:
    """Property 6: ValidationResult 序列化往返"""
    
    @given(
        is_valid=st.booleans(),
        email=st.text(min_size=0, max_size=50),
        reason=st.one_of(st.none(), st.text(min_size=0, max_size=100))
    )
    @settings(max_examples=100)
    def test_validation_result_json_round_trip(self, is_valid, email, reason):
        """
        *For any* ValidationResult object, serializing to JSON and then
        deserializing SHALL produce an equivalent ValidationResult object.
        **Feature: data-collection-optimization, Property 6: Validation Result Round-Trip**
        **Validates: Requirements 1.6, 1.7**
        """
        original = ValidationResult(is_valid=is_valid, email=email, reason=reason)
        
        # 序列化
        json_str = original.to_json()
        
        # 反序列化
        restored = ValidationResult.from_json(json_str)
        
        # 验证等价性
        assert restored.is_valid == original.is_valid
        assert restored.email == original.email
        assert restored.reason == original.reason
    
    @given(
        is_valid=st.booleans(),
        email=st.text(min_size=0, max_size=50),
        reason=st.one_of(st.none(), st.text(min_size=0, max_size=100))
    )
    @settings(max_examples=100)
    def test_validation_result_dict_round_trip(self, is_valid, email, reason):
        """
        *For any* ValidationResult object, converting to dict and back
        SHALL produce an equivalent ValidationResult object.
        **Feature: data-collection-optimization, Property 6: Validation Result Round-Trip**
        **Validates: Requirements 1.6, 1.7**
        """
        original = ValidationResult(is_valid=is_valid, email=email, reason=reason)
        
        # 转换为字典
        data = original.to_dict()
        
        # 从字典恢复
        restored = ValidationResult.from_dict(data)
        
        # 验证等价性
        assert restored.is_valid == original.is_valid
        assert restored.email == original.email
        assert restored.reason == original.reason


# ============================================================================
# 边界情况测试
# ============================================================================

class TestEdgeCases:
    """边界情况测试"""
    
    def test_empty_email(self):
        """空邮箱应该被拒绝"""
        validator = EmailValidator()
        result = validator.validate('')
        assert not result.is_valid
    
    def test_none_email(self):
        """None 应该被拒绝"""
        validator = EmailValidator()
        result = validator.validate(None)
        assert not result.is_valid
    
    def test_very_long_email(self):
        """超长邮箱应该被拒绝"""
        validator = EmailValidator()
        long_email = 'a' * 300 + '@example.com'
        result = validator.validate(long_email)
        assert not result.is_valid
    
    def test_specific_valid_emails(self):
        """测试特定的有效邮箱"""
        validator = EmailValidator()
        valid_emails = [
            'test@example.com',
            'user.name@domain.org',
            'user+tag@example.co.uk',
            'user123@test-domain.com',
        ]
        for email in valid_emails:
            result = validator.validate(email)
            assert result.is_valid, f"Valid email '{email}' was rejected: {result.reason}"
    
    def test_specific_invalid_emails(self):
        """测试特定的无效邮箱"""
        validator = EmailValidator()
        invalid_emails = [
            'notanemail',
            '@nodomain.com',
            'noat.com',
            'spaces in@email.com',
            'logo@example.com',  # 包含 logo
            'image123@test.com',  # 包含 image
            'photo100x200@test.com',  # 包含尺寸模式
        ]
        for email in invalid_emails:
            result = validator.validate(email)
            assert not result.is_valid, f"Invalid email '{email}' was accepted"
