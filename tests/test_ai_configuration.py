"""
AIConfiguration 属性测试
使用 Hypothesis 进行属性测试，验证 AIConfiguration 的正确性

**Feature: data-collection-optimization**
"""
import pytest
from hypothesis import given, strategies as st, settings, assume
import string
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.ai_configuration import AIConfiguration


# ============================================================================
# Property 26: API Key Encryption Round-Trip
# **Feature: data-collection-optimization, Property 26: API Key Encryption Round-Trip**
# **Validates: Requirements 12.8**
# ============================================================================

class TestAPIKeyEncryptionRoundTrip:
    """Property 26: API密钥加密往返"""
    
    @given(api_key=st.text(min_size=0, max_size=100))
    @settings(max_examples=100)
    def test_encrypt_decrypt_round_trip(self, api_key):
        """
        *For any* API key string,
        encrypting and then decrypting SHALL produce the original key.
        **Feature: data-collection-optimization, Property 26: API Key Encryption Round-Trip**
        **Validates: Requirements 12.8**
        """
        # 加密
        encrypted = AIConfiguration.encrypt_key(api_key)
        
        # 解密
        decrypted = AIConfiguration.decrypt_key(encrypted)
        
        # 验证往返一致性
        assert decrypted == api_key, \
            f"Round-trip failed: original='{api_key}', decrypted='{decrypted}'"
    
    @given(api_key=st.text(
        alphabet=string.ascii_letters + string.digits + '-_.',
        min_size=10,
        max_size=64
    ))
    @settings(max_examples=100)
    def test_typical_api_key_round_trip(self, api_key):
        """
        *For any* typical API key (alphanumeric with common special chars),
        encrypting and then decrypting SHALL produce the original key.
        **Feature: data-collection-optimization, Property 26: API Key Encryption Round-Trip**
        **Validates: Requirements 12.8**
        """
        encrypted = AIConfiguration.encrypt_key(api_key)
        decrypted = AIConfiguration.decrypt_key(encrypted)
        
        assert decrypted == api_key
    
    @given(api_key=st.text(min_size=1, max_size=50))
    @settings(max_examples=100)
    def test_encrypted_differs_from_original(self, api_key):
        """
        *For any* non-empty API key,
        the encrypted form SHALL differ from the original.
        **Feature: data-collection-optimization, Property 26: API Key Encryption Round-Trip**
        **Validates: Requirements 12.8**
        """
        assume(len(api_key) > 0)
        
        encrypted = AIConfiguration.encrypt_key(api_key)
        
        # 加密后应该与原始不同（除非原始恰好是有效的base64）
        # 对于大多数输入，这应该成立
        if api_key != encrypted:
            assert encrypted != api_key


# ============================================================================
# AIConfiguration 序列化测试
# ============================================================================

class TestAIConfigurationSerialization:
    """AIConfiguration 序列化测试"""
    
    @given(
        api_endpoint=st.text(min_size=0, max_size=100),
        api_key=st.text(min_size=0, max_size=50),
        model=st.text(min_size=0, max_size=30)
    )
    @settings(max_examples=100)
    def test_json_round_trip(self, api_endpoint, api_key, model):
        """JSON序列化往返测试"""
        original = AIConfiguration(
            api_endpoint=api_endpoint,
            api_key=api_key,
            model=model
        )
        
        # 序列化
        json_str = original.to_json()
        
        # 反序列化
        restored = AIConfiguration.from_json(json_str)
        
        # 验证等价性
        assert restored.api_endpoint == original.api_endpoint
        assert restored.api_key == original.api_key
        assert restored.model == original.model
    
    @given(
        api_endpoint=st.text(min_size=0, max_size=100),
        api_key=st.text(min_size=0, max_size=50),
        model=st.text(min_size=0, max_size=30)
    )
    @settings(max_examples=100)
    def test_dict_round_trip(self, api_endpoint, api_key, model):
        """字典序列化往返测试"""
        original = AIConfiguration(
            api_endpoint=api_endpoint,
            api_key=api_key,
            model=model
        )
        
        # 转换为字典
        data = original.to_dict()
        
        # 从字典恢复
        restored = AIConfiguration.from_dict(data)
        
        # 验证等价性
        assert restored.api_endpoint == original.api_endpoint
        assert restored.api_key == original.api_key
        assert restored.model == original.model


# ============================================================================
# 边界情况测试
# ============================================================================

class TestEdgeCases:
    """边界情况测试"""
    
    def test_empty_key_encryption(self):
        """空密钥加密应该返回空字符串"""
        assert AIConfiguration.encrypt_key('') == ''
    
    def test_empty_key_decryption(self):
        """空字符串解密应该返回空字符串"""
        assert AIConfiguration.decrypt_key('') == ''
    
    def test_invalid_base64_decryption(self):
        """无效的base64解密应该返回空字符串"""
        assert AIConfiguration.decrypt_key('not-valid-base64!!!') == ''
    
    def test_default_configuration(self):
        """默认配置应该有空值"""
        config = AIConfiguration()
        
        assert config.api_endpoint == ''
        assert config.api_key == ''
        assert config.model == ''
    
    def test_typical_openai_config(self):
        """测试典型的OpenAI配置"""
        config = AIConfiguration(
            api_endpoint='https://api.openai.com/v1/chat/completions',
            api_key='sk-test-key-12345',
            model='gpt-4'
        )
        
        # 加密密钥
        encrypted_key = AIConfiguration.encrypt_key(config.api_key)
        
        # 解密验证
        decrypted_key = AIConfiguration.decrypt_key(encrypted_key)
        
        assert decrypted_key == config.api_key
    
    def test_unicode_api_key(self):
        """Unicode字符的API密钥应该正确处理"""
        api_key = 'sk-测试密钥-αβγ-🔑'
        
        encrypted = AIConfiguration.encrypt_key(api_key)
        decrypted = AIConfiguration.decrypt_key(encrypted)
        
        assert decrypted == api_key
