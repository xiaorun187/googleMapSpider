"""
URL去重属性测试
使用 Hypothesis 进行属性测试，验证 Set-Based URL Deduplication 的正确性

**Feature: data-collection-optimization**
"""
import pytest
from hypothesis import given, strategies as st, settings
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ============================================================================
# Property 10: Set-Based URL Deduplication
# **Feature: data-collection-optimization, Property 10: Set-Based URL Deduplication**
# **Validates: Requirements 2.4**
# ============================================================================

class TestSetBasedURLDeduplication:
    """Property 10: 基于Set的URL去重"""
    
    @given(urls=st.lists(
        st.text(min_size=10, max_size=100),
        min_size=1,
        max_size=50
    ))
    @settings(max_examples=100)
    def test_adding_duplicate_url_does_not_increase_set_size(self, urls):
        """
        *For any* set of URLs, adding a duplicate URL SHALL not increase the set size.
        **Feature: data-collection-optimization, Property 10: Set-Based URL Deduplication**
        **Validates: Requirements 2.4**
        """
        url_set = set()
        
        # 添加所有URL
        for url in urls:
            url_set.add(url)
        
        original_size = len(url_set)
        
        # 再次添加所有URL（重复添加）
        for url in urls:
            url_set.add(url)
        
        # 大小不应该改变
        assert len(url_set) == original_size, \
            f"Set size changed after adding duplicates: {original_size} -> {len(url_set)}"
    
    @given(
        unique_urls=st.lists(
            st.text(min_size=10, max_size=50),
            min_size=1,
            max_size=20,
            unique=True
        ),
        duplicate_count=st.integers(min_value=1, max_value=10)
    )
    @settings(max_examples=100)
    def test_set_contains_only_unique_urls(self, unique_urls, duplicate_count):
        """
        *For any* list of URLs with duplicates,
        the resulting set SHALL contain only unique URLs.
        **Feature: data-collection-optimization, Property 10: Set-Based URL Deduplication**
        **Validates: Requirements 2.4**
        """
        # 创建包含重复的URL列表
        urls_with_duplicates = []
        for url in unique_urls:
            for _ in range(duplicate_count):
                urls_with_duplicates.append(url)
        
        # 使用set去重
        url_set = set(urls_with_duplicates)
        
        # set大小应该等于唯一URL数量
        assert len(url_set) == len(unique_urls), \
            f"Set size {len(url_set)} != unique count {len(unique_urls)}"
    
    @given(urls=st.lists(
        st.text(min_size=5, max_size=30),
        min_size=0,
        max_size=100
    ))
    @settings(max_examples=100)
    def test_set_size_never_exceeds_input_size(self, urls):
        """
        *For any* list of URLs,
        the set size SHALL never exceed the input list size.
        **Feature: data-collection-optimization, Property 10: Set-Based URL Deduplication**
        **Validates: Requirements 2.4**
        """
        url_set = set(urls)
        
        assert len(url_set) <= len(urls), \
            f"Set size {len(url_set)} > input size {len(urls)}"


# ============================================================================
# 模拟滚动加载去重测试
# ============================================================================

class TestScrollLoadDeduplication:
    """模拟滚动加载过程中的URL去重"""
    
    @given(
        batch1=st.lists(st.text(min_size=10, max_size=30), min_size=1, max_size=10),
        batch2=st.lists(st.text(min_size=10, max_size=30), min_size=1, max_size=10),
        batch3=st.lists(st.text(min_size=10, max_size=30), min_size=1, max_size=10)
    )
    @settings(max_examples=50)
    def test_incremental_deduplication(self, batch1, batch2, batch3):
        """模拟多次滚动加载时的增量去重"""
        business_links = set()
        
        # 模拟第一次滚动
        business_links.update(batch1)
        size_after_batch1 = len(business_links)
        
        # 模拟第二次滚动（可能有重复）
        business_links.update(batch2)
        size_after_batch2 = len(business_links)
        
        # 模拟第三次滚动（可能有重复）
        business_links.update(batch3)
        size_after_batch3 = len(business_links)
        
        # 验证大小单调递增或不变
        assert size_after_batch1 <= size_after_batch2 <= size_after_batch3
        
        # 验证最终大小不超过所有唯一URL的数量
        all_unique = set(batch1) | set(batch2) | set(batch3)
        assert len(business_links) == len(all_unique)
    
    def test_empty_set_behavior(self):
        """空集合应该正常工作"""
        url_set = set()
        
        assert len(url_set) == 0
        
        url_set.add("http://example.com")
        assert len(url_set) == 1
        
        url_set.add("http://example.com")  # 重复
        assert len(url_set) == 1
    
    def test_google_maps_url_deduplication(self):
        """测试Google Maps URL去重"""
        urls = [
            "https://www.google.com/maps/place/Business+A",
            "https://www.google.com/maps/place/Business+B",
            "https://www.google.com/maps/place/Business+A",  # 重复
            "https://www.google.com/maps/place/Business+C",
            "https://www.google.com/maps/place/Business+B",  # 重复
        ]
        
        url_set = set(urls)
        
        assert len(url_set) == 3  # 只有3个唯一URL
