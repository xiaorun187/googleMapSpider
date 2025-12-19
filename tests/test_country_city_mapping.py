"""
CountryCityMapping 属性测试
使用 Hypothesis 进行属性测试，验证 CountryCityMapping 的正确性

**Feature: data-collection-optimization**
"""
import pytest
from hypothesis import given, strategies as st, settings
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.country_city_mapping import CountryCityMapping


# ============================================================================
# 测试策略（Generators）
# ============================================================================

@st.composite
def country_city_data(draw):
    """生成国家城市映射数据"""
    num_countries = draw(st.integers(min_value=1, max_value=5))
    
    countries = {}
    for _ in range(num_countries):
        country = draw(st.text(
            alphabet='abcdefghijklmnopqrstuvwxyz ',
            min_size=3,
            max_size=15
        )).strip()
        if not country:
            country = 'TestCountry'
        
        num_cities = draw(st.integers(min_value=1, max_value=5))
        cities = []
        for _ in range(num_cities):
            city = draw(st.text(
                alphabet='abcdefghijklmnopqrstuvwxyz ',
                min_size=2,
                max_size=15
            )).strip()
            if city and city not in cities:
                cities.append(city)
        
        if not cities:
            cities = ['TestCity']
        
        countries[country] = cities
    
    return countries


# ============================================================================
# Property 24: Country-City Mapping Round-Trip
# **Feature: data-collection-optimization, Property 24: Country-City Mapping Round-Trip**
# **Validates: Requirements 10.6**
# ============================================================================

class TestCountryCityMappingRoundTrip:
    """Property 24: 国家城市映射序列化往返"""
    
    @given(countries=country_city_data())
    @settings(max_examples=100)
    def test_json_round_trip(self, countries):
        """
        *For any* CountryCityMapping object,
        serializing to JSON and then deserializing SHALL produce an equivalent mapping.
        **Feature: data-collection-optimization, Property 24: Country-City Mapping Round-Trip**
        **Validates: Requirements 10.6**
        """
        original = CountryCityMapping(countries=countries)
        
        # 序列化
        json_str = original.to_json()
        
        # 反序列化
        restored = CountryCityMapping.from_json(json_str)
        
        # 验证等价性
        assert restored.countries == original.countries
    
    @given(countries=country_city_data())
    @settings(max_examples=100)
    def test_dict_round_trip(self, countries):
        """
        *For any* CountryCityMapping object,
        converting to dict and back SHALL produce an equivalent mapping.
        **Feature: data-collection-optimization, Property 24: Country-City Mapping Round-Trip**
        **Validates: Requirements 10.6**
        """
        original = CountryCityMapping(countries=countries)
        
        # 转换为字典
        data = original.to_dict()
        
        # 从字典恢复
        restored = CountryCityMapping.from_dict(data)
        
        # 验证等价性
        assert restored.countries == original.countries
    
    @given(countries=country_city_data())
    @settings(max_examples=100)
    def test_get_countries_returns_all_keys(self, countries):
        """
        *For any* CountryCityMapping,
        get_countries SHALL return all country names.
        **Feature: data-collection-optimization, Property 24: Country-City Mapping Round-Trip**
        **Validates: Requirements 10.6**
        """
        mapping = CountryCityMapping(countries=countries)
        
        country_list = mapping.get_countries()
        
        assert set(country_list) == set(countries.keys())
    
    @given(countries=country_city_data())
    @settings(max_examples=100)
    def test_get_cities_returns_correct_cities(self, countries):
        """
        *For any* CountryCityMapping and country,
        get_cities SHALL return the correct city list.
        **Feature: data-collection-optimization, Property 24: Country-City Mapping Round-Trip**
        **Validates: Requirements 10.6**
        """
        mapping = CountryCityMapping(countries=countries)
        
        for country, expected_cities in countries.items():
            actual_cities = mapping.get_cities(country)
            assert actual_cities == expected_cities


# ============================================================================
# 边界情况测试
# ============================================================================

class TestEdgeCases:
    """边界情况测试"""
    
    def test_empty_mapping(self):
        """空映射应该正常工作"""
        mapping = CountryCityMapping()
        
        assert mapping.get_countries() == []
        assert mapping.get_cities('NonExistent') == []
    
    def test_add_country(self):
        """添加国家应该正常工作"""
        mapping = CountryCityMapping()
        
        mapping.add_country('TestCountry', ['City1', 'City2'])
        
        assert mapping.has_country('TestCountry')
        assert mapping.get_cities('TestCountry') == ['City1', 'City2']
    
    def test_add_city(self):
        """添加城市应该正常工作"""
        mapping = CountryCityMapping()
        
        mapping.add_city('TestCountry', 'City1')
        mapping.add_city('TestCountry', 'City2')
        
        assert mapping.has_city('TestCountry', 'City1')
        assert mapping.has_city('TestCountry', 'City2')
    
    def test_remove_country(self):
        """移除国家应该正常工作"""
        mapping = CountryCityMapping(countries={'TestCountry': ['City1']})
        
        assert mapping.remove_country('TestCountry')
        assert not mapping.has_country('TestCountry')
    
    def test_remove_city(self):
        """移除城市应该正常工作"""
        mapping = CountryCityMapping(countries={'TestCountry': ['City1', 'City2']})
        
        assert mapping.remove_city('TestCountry', 'City1')
        assert not mapping.has_city('TestCountry', 'City1')
        assert mapping.has_city('TestCountry', 'City2')
    
    def test_default_mapping_has_countries(self):
        """默认映射应该包含国家"""
        mapping = CountryCityMapping.get_default_mapping()
        
        countries = mapping.get_countries()
        assert len(countries) > 0
        
        # 验证一些预期的国家
        assert 'United States' in countries
        assert 'China' in countries
    
    def test_nonexistent_country_returns_empty_list(self):
        """不存在的国家应该返回空列表"""
        mapping = CountryCityMapping(countries={'TestCountry': ['City1']})
        
        assert mapping.get_cities('NonExistent') == []
    
    def test_has_country_and_city(self):
        """has_country 和 has_city 应该正确工作"""
        mapping = CountryCityMapping(countries={'TestCountry': ['City1']})
        
        assert mapping.has_country('TestCountry')
        assert not mapping.has_country('NonExistent')
        assert mapping.has_city('TestCountry', 'City1')
        assert not mapping.has_city('TestCountry', 'NonExistent')
        assert not mapping.has_city('NonExistent', 'City1')
