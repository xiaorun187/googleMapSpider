"""
CitySelector - 城市选择器
实现国家列表获取和城市列表动态加载
"""
import json
import os
import sys
from typing import List, Optional

sys.path.insert(0, '.')
from models.country_city_mapping import CountryCityMapping


class CitySelector:
    """
    城市选择组件
    
    Features:
    - 国家列表获取
    - 城市列表动态加载
    - 配置文件加载
    """
    
    DEFAULT_CONFIG_PATH = 'config/countries.json'
    
    def __init__(self, mapping: CountryCityMapping = None, config_path: str = None):
        """
        初始化城市选择器
        
        Args:
            mapping: 国家城市映射对象
            config_path: 配置文件路径
        """
        if mapping:
            self._mapping = mapping
        elif config_path:
            self._mapping = self._load_from_file(config_path)
        else:
            # 尝试从默认配置文件加载
            if os.path.exists(self.DEFAULT_CONFIG_PATH):
                self._mapping = self._load_from_file(self.DEFAULT_CONFIG_PATH)
            else:
                # 使用默认映射
                self._mapping = CountryCityMapping.get_default_mapping()
    
    def _load_from_file(self, config_path: str) -> CountryCityMapping:
        """
        从配置文件加载映射
        
        Args:
            config_path: 配置文件路径
            
        Returns:
            CountryCityMapping: 映射对象
        """
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return CountryCityMapping(countries=data)
        except Exception as e:
            print(f"加载配置文件失败: {e}", file=sys.stderr)
            return CountryCityMapping.get_default_mapping()
    
    def get_countries(self) -> List[str]:
        """
        获取所有国家列表
        
        Returns:
            List[str]: 国家名称列表（按字母排序）
        """
        return sorted(self._mapping.get_countries())
    
    def get_cities_for_country(self, country: str) -> List[str]:
        """
        获取指定国家的城市列表
        
        Args:
            country: 国家名称
            
        Returns:
            List[str]: 城市列表（按字母排序）
        """
        cities = self._mapping.get_cities(country)
        return sorted(cities) if cities else []
    
    def search_countries(self, query: str) -> List[str]:
        """
        搜索国家
        
        Args:
            query: 搜索关键词
            
        Returns:
            List[str]: 匹配的国家列表
        """
        query_lower = query.lower()
        return [
            country for country in self.get_countries()
            if query_lower in country.lower()
        ]
    
    def search_cities(self, country: str, query: str) -> List[str]:
        """
        搜索城市
        
        Args:
            country: 国家名称
            query: 搜索关键词
            
        Returns:
            List[str]: 匹配的城市列表
        """
        query_lower = query.lower()
        cities = self.get_cities_for_country(country)
        return [
            city for city in cities
            if query_lower in city.lower()
        ]
    
    def get_mapping(self) -> CountryCityMapping:
        """
        获取映射对象
        
        Returns:
            CountryCityMapping: 映射对象
        """
        return self._mapping
    
    def reload_config(self, config_path: str = None) -> bool:
        """
        重新加载配置
        
        Args:
            config_path: 配置文件路径
            
        Returns:
            bool: 是否成功加载
        """
        try:
            path = config_path or self.DEFAULT_CONFIG_PATH
            self._mapping = self._load_from_file(path)
            return True
        except Exception as e:
            print(f"重新加载配置失败: {e}", file=sys.stderr)
            return False
    
    def to_json(self) -> str:
        """
        导出为JSON
        
        Returns:
            str: JSON字符串
        """
        return self._mapping.to_json()
    
    def get_country_count(self) -> int:
        """
        获取国家数量
        
        Returns:
            int: 国家数量
        """
        return len(self._mapping.get_countries())
    
    def get_total_city_count(self) -> int:
        """
        获取总城市数量
        
        Returns:
            int: 总城市数量
        """
        total = 0
        for country in self._mapping.get_countries():
            total += len(self._mapping.get_cities(country))
        return total
