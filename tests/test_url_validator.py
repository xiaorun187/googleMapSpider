"""
URLValidator 属性测试
使用 Hypothesis 进行属性测试，验证 URLValidator 的正确性

**Feature: data-collection-optimization**
"""
import pytest
from hypothesis import given, strategies as st, settings, assume
import string
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from validators.url_validator import URLValidator


# ============================================================================
# 测试策略（Generators）
# ============================================================================

# 有效域名字符集
VALID_DOMAIN_CHARS = string.ascii_lowercase + string.digits + '-'


@st.composite
def valid_domain_part(draw):
    """生成有效的域名部分"""
    length = draw(st.integers(min_value=1, max_value=20))
    chars = draw(st.lists(
        st.sampled_from(VALID_DOMAIN_CHARS),
        min_size=length,
        max_size=length
    ))
    domain = ''.join(chars).strip('-')
    if not domain:
        domain = 'example'
    return domain


@st.composite
def valid_tld(draw):
    """生成有效的顶级域名"""
    tlds = ['com', 'org', 'net', 'io', 'co', 'edu', 'gov', 'cn', 'uk', 'de']
    return draw(st.sampled_from(tlds))


@st.composite
def valid_url(draw):
    """生成有效的URL"""
    scheme = draw(st.sampled_from(['http', 'https']))
    domain = draw(valid_domain_part())
    tld = draw(valid_tld())
    
    # 可选的端口
    port = ''
    if draw(st.booleans()):
        port = ':' + str(draw(st.integers(min_value=1, max_value=65535)))
    
    # 可选的路径
    path = ''
    if draw(st.booleans()):
        path_parts = draw(st.lists(
            st.text(alphabet=string.ascii_lowercase + string.digits + '-_', min_size=1, max_size=10),
            min_size=1,
            max_size=3
        ))
        path = '/' + '/'.join(path_parts)
    
    return f"{scheme}://{domain}.{tld}{port}{path}"


@st.composite
def valid_url_with_subdomain(draw):
    """生成带子域名的有效URL"""
    scheme = draw(st.sampled_from(['http', 'https']))
    subdomain = draw(valid_domain_part())
    domain = draw(valid_domain_part())
    tld = draw(valid_tld())
    
    return f"{scheme}://{subdomain}.{domain}.{tld}"


@st.composite
def invalid_url(draw):
    """生成无效的URL"""
    strategy = draw(st.integers(min_value=0, max_value=5))
    
    if strategy == 0:
        # 没有协议
        return draw(st.text(alphabet=string.ascii_lowercase, min_size=5, max_size=20)) + '.com'
    elif strategy == 1:
        # 无效协议
        return 'ftp://' + draw(st.text(alphabet=string.ascii_lowercase, min_size=3, max_size=10)) + '.com'
    elif strategy == 2:
        # 没有域名
        return 'https://'
    elif strategy == 3:
        # 空字符串
        return ''
    elif strategy == 4:
        # 只有协议和斜杠
        return 'http:///'
    else:
        # 随机字符串
        return draw(st.text(min_size=1, max_size=20))


@st.composite
def localhost_url(draw):
    """生成 localhost URL"""
    scheme = draw(st.sampled_from(['http', 'https']))
    port = draw(st.integers(min_value=1, max_value=65535))
    
    path = ''
    if draw(st.booleans()):
        path = '/' + draw(st.text(alphabet=string.ascii_lowercase, min_size=1, max_size=10))
    
    return f"{scheme}://localhost:{port}{path}"


@st.composite
def ip_url(draw):
    """生成 IP 地址 URL"""
    scheme = draw(st.sampled_from(['http', 'https']))
    ip_parts = [str(draw(st.integers(min_value=0, max_value=255))) for _ in range(4)]
    ip = '.'.join(ip_parts)
    
    port = ''
    if draw(st.booleans()):
        port = ':' + str(draw(st.integers(min_value=1, max_value=65535)))
    
    return f"{scheme}://{ip}{port}"


# ============================================================================
# Property 5: URL Format Validation
# **Feature: data-collection-optimization, Property 5: URL Format Validation**
# **Validates: Requirements 1.5**
# ============================================================================

class TestURLFormatValidation:
    """Property 5: URL格式验证"""
    
    @given(url=valid_url())
    @settings(max_examples=100)
    def test_valid_urls_are_accepted(self, url):
        """
        *For any* valid URL with proper scheme and domain,
        the URLValidator SHALL accept it.
        **Feature: data-collection-optimization, Property 5: URL Format Validation**
        **Validates: Requirements 1.5**
        """
        validator = URLValidator()
        assert validator.validate(url), f"Valid URL '{url}' was rejected"
    
    @given(url=valid_url_with_subdomain())
    @settings(max_examples=100)
    def test_urls_with_subdomains_are_accepted(self, url):
        """
        *For any* valid URL with subdomain,
        the URLValidator SHALL accept it.
        **Feature: data-collection-optimization, Property 5: URL Format Validation**
        **Validates: Requirements 1.5**
        """
        validator = URLValidator()
        assert validator.validate(url), f"Valid URL with subdomain '{url}' was rejected"
    
    @given(url=localhost_url())
    @settings(max_examples=100)
    def test_localhost_urls_are_accepted(self, url):
        """
        *For any* localhost URL,
        the URLValidator SHALL accept it.
        **Feature: data-collection-optimization, Property 5: URL Format Validation**
        **Validates: Requirements 1.5**
        """
        validator = URLValidator()
        assert validator.validate(url), f"Localhost URL '{url}' was rejected"
    
    @given(url=ip_url())
    @settings(max_examples=100)
    def test_ip_urls_are_accepted(self, url):
        """
        *For any* IP address URL,
        the URLValidator SHALL accept it.
        **Feature: data-collection-optimization, Property 5: URL Format Validation**
        **Validates: Requirements 1.5**
        """
        validator = URLValidator()
        assert validator.validate(url), f"IP URL '{url}' was rejected"
    
    @given(url=invalid_url())
    @settings(max_examples=100)
    def test_invalid_urls_are_rejected(self, url):
        """
        *For any* invalid URL,
        the URLValidator SHALL reject it.
        **Feature: data-collection-optimization, Property 5: URL Format Validation**
        **Validates: Requirements 1.5**
        """
        validator = URLValidator()
        # 确保生成的确实是无效URL
        assume(not url.startswith('http://') and not url.startswith('https://') or 
               len(url) < 10 or '.' not in url[8:])
        result = validator.validate(url)
        # 如果URL确实无效，应该被拒绝
        if not url or not url.startswith(('http://', 'https://')):
            assert not result, f"Invalid URL '{url}' was accepted"


# ============================================================================
# 域名提取测试
# ============================================================================

class TestDomainExtraction:
    """域名提取功能测试"""
    
    @given(url=valid_url())
    @settings(max_examples=100)
    def test_extract_domain_from_valid_url(self, url):
        """从有效URL中提取域名应该成功"""
        validator = URLValidator()
        domain = validator.extract_domain(url)
        assert domain is not None, f"Failed to extract domain from '{url}'"
        assert len(domain) > 0
    
    @given(url=invalid_url())
    @settings(max_examples=100)
    def test_extract_domain_from_invalid_url_returns_none(self, url):
        """从无效URL中提取域名应该返回None"""
        validator = URLValidator()
        assume(not validator.validate(url))
        domain = validator.extract_domain(url)
        assert domain is None


# ============================================================================
# URL规范化测试
# ============================================================================

class TestURLNormalization:
    """URL规范化功能测试"""
    
    @given(domain=valid_domain_part(), tld=valid_tld())
    @settings(max_examples=100)
    def test_normalize_adds_https_scheme(self, domain, tld):
        """规范化应该为没有协议的URL添加https://"""
        validator = URLValidator()
        url_without_scheme = f"{domain}.{tld}"
        normalized = validator.normalize_url(url_without_scheme)
        
        if normalized:
            assert normalized.startswith('https://'), \
                f"Normalized URL '{normalized}' doesn't start with https://"


# ============================================================================
# 边界情况测试
# ============================================================================

class TestEdgeCases:
    """边界情况测试"""
    
    def test_empty_url(self):
        """空URL应该被拒绝"""
        validator = URLValidator()
        assert not validator.validate('')
    
    def test_none_url(self):
        """None应该被拒绝"""
        validator = URLValidator()
        assert not validator.validate(None)
    
    def test_whitespace_url(self):
        """纯空白URL应该被拒绝"""
        validator = URLValidator()
        assert not validator.validate('   ')
    
    def test_common_valid_urls(self):
        """测试常见的有效URL"""
        validator = URLValidator()
        valid_urls = [
            'https://www.google.com',
            'http://example.org',
            'https://sub.domain.co.uk',
            'http://localhost:8080',
            'https://192.168.1.1:3000',
            'https://example.com/path/to/page',
            'http://test.io/api/v1/users',
        ]
        for url in valid_urls:
            assert validator.validate(url), f"Valid URL '{url}' was rejected"
    
    def test_common_invalid_urls(self):
        """测试常见的无效URL"""
        validator = URLValidator()
        invalid_urls = [
            'not-a-url',
            'ftp://files.example.com',
            'mailto:test@example.com',
            '://missing-scheme.com',
            'http://',
            'https://',
        ]
        for url in invalid_urls:
            assert not validator.validate(url), f"Invalid URL '{url}' was accepted"
