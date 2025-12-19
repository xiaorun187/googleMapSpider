"""
CountryCityMapping - 国家城市映射数据结构
实现国家城市映射数据类和 JSON 序列化/反序列化
"""
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class CountryCityMapping:
    """
    国家城市映射数据结构
    
    Attributes:
        countries: 国家与城市列表的映射 {country_name: [city1, city2, ...]}
    """
    countries: Dict[str, List[str]] = field(default_factory=dict)
    
    def to_json(self) -> str:
        """序列化为JSON"""
        return json.dumps(self.countries, ensure_ascii=False, indent=2)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'CountryCityMapping':
        """从JSON反序列化"""
        data = json.loads(json_str)
        return cls(countries=data)
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {'countries': self.countries}
    
    @classmethod
    def from_dict(cls, data: dict) -> 'CountryCityMapping':
        """从字典创建"""
        return cls(countries=data.get('countries', {}))
    
    def get_countries(self) -> List[str]:
        """
        获取所有国家列表
        
        Returns:
            List[str]: 国家名称列表
        """
        return list(self.countries.keys())
    
    def get_cities(self, country: str) -> List[str]:
        """
        获取指定国家的城市列表
        
        Args:
            country: 国家名称
            
        Returns:
            List[str]: 城市列表
        """
        return self.countries.get(country, [])
    
    def add_country(self, country: str, cities: List[str] = None) -> None:
        """
        添加国家
        
        Args:
            country: 国家名称
            cities: 城市列表
        """
        self.countries[country] = cities or []
    
    def add_city(self, country: str, city: str) -> None:
        """
        添加城市到指定国家
        
        Args:
            country: 国家名称
            city: 城市名称
        """
        if country not in self.countries:
            self.countries[country] = []
        if city not in self.countries[country]:
            self.countries[country].append(city)
    
    def remove_country(self, country: str) -> bool:
        """
        移除国家
        
        Args:
            country: 国家名称
            
        Returns:
            bool: 是否成功移除
        """
        if country in self.countries:
            del self.countries[country]
            return True
        return False
    
    def remove_city(self, country: str, city: str) -> bool:
        """
        从指定国家移除城市
        
        Args:
            country: 国家名称
            city: 城市名称
            
        Returns:
            bool: 是否成功移除
        """
        if country in self.countries and city in self.countries[country]:
            self.countries[country].remove(city)
            return True
        return False
    
    def has_country(self, country: str) -> bool:
        """
        检查是否存在指定国家
        
        Args:
            country: 国家名称
            
        Returns:
            bool: 是否存在
        """
        return country in self.countries
    
    def has_city(self, country: str, city: str) -> bool:
        """
        检查指定国家是否存在指定城市
        
        Args:
            country: 国家名称
            city: 城市名称
            
        Returns:
            bool: 是否存在
        """
        return country in self.countries and city in self.countries[country]
    
    @classmethod
    def get_default_mapping(cls) -> 'CountryCityMapping':
        """
        获取默认的国家城市映射
        
        Returns:
            CountryCityMapping: 默认映射
        """
        return cls(countries={
            "United States": [
                "New York", "Los Angeles", "Chicago", "Houston", "Phoenix",
                "Philadelphia", "San Antonio", "San Diego", "Dallas", "San Jose",
                "Austin", "Jacksonville", "Fort Worth", "Columbus", "Charlotte",
                "Seattle", "Denver", "Boston", "Detroit", "Miami"
            ],
            "United Kingdom": [
                "London", "Birmingham", "Manchester", "Glasgow", "Liverpool",
                "Leeds", "Sheffield", "Edinburgh", "Bristol", "Leicester"
            ],
            "Canada": [
                "Toronto", "Montreal", "Vancouver", "Calgary", "Edmonton",
                "Ottawa", "Winnipeg", "Quebec City", "Hamilton", "Kitchener"
            ],
            "Australia": [
                "Sydney", "Melbourne", "Brisbane", "Perth", "Adelaide",
                "Gold Coast", "Newcastle", "Canberra", "Sunshine Coast", "Wollongong"
            ],
            "Germany": [
                "Berlin", "Hamburg", "Munich", "Cologne", "Frankfurt",
                "Stuttgart", "Düsseldorf", "Dortmund", "Essen", "Leipzig"
            ],
            "France": [
                "Paris", "Marseille", "Lyon", "Toulouse", "Nice",
                "Nantes", "Strasbourg", "Montpellier", "Bordeaux", "Lille"
            ],
            "Japan": [
                "Tokyo", "Yokohama", "Osaka", "Nagoya", "Sapporo",
                "Fukuoka", "Kobe", "Kyoto", "Kawasaki", "Saitama"
            ],
            "China": [
                "Shanghai", "Beijing", "Guangzhou", "Shenzhen", "Chengdu",
                "Hangzhou", "Wuhan", "Xi'an", "Suzhou", "Nanjing"
            ],
            "India": [
                "Mumbai", "Delhi", "Bangalore", "Hyderabad", "Chennai",
                "Kolkata", "Pune", "Ahmedabad", "Jaipur", "Surat"
            ],
            "Brazil": [
                "São Paulo", "Rio de Janeiro", "Brasília", "Salvador", "Fortaleza",
                "Belo Horizonte", "Manaus", "Curitiba", "Recife", "Porto Alegre"
            ]
        })
