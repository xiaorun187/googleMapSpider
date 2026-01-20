"""
数据导出工具函数
"""
import os
import sys
import pandas as pd
from datetime import datetime
from config import OUTPUT_DIR


def normalize_export_data(business_data):
    """
    标准化导出数据格式
    
    Args:
        business_data: 商家数据列表
        
    Returns:
        list: 标准化后的数据列表
    """
    normalized = []
    for item in business_data:
        if not isinstance(item, dict):
            continue
        
        # 处理 emails 字段（可能是列表或字符串）
        emails = item.get('emails', [])
        if isinstance(emails, list):
            email = emails[0] if emails else ''
        else:
            email = emails or ''
        
        # 处理 phones 字段（可能是列表或字符串）
        phones = item.get('phones', [])
        if isinstance(phones, list):
            phone_str = ', '.join(phones)
        else:
            phone_str = phones or ''
        
        normalized.append({
            'name': item.get('name', ''),
            'website': item.get('website', ''),
            'email': email,
            'phones': phone_str,
            'city': item.get('city', ''),
            'product': item.get('product', ''),
            'facebook': item.get('facebook', ''),
            'twitter': item.get('twitter', ''),
            'instagram': item.get('instagram', ''),
            'linkedin': item.get('linkedin', ''),
            'whatsapp': item.get('whatsapp', ''),
            'youtube': item.get('youtube', ''),
        })
    
    return normalized


def has_city_field(business_data):
    """
    检查数据是否包含 city 字段
    
    Args:
        business_data: 商家数据列表
        
    Returns:
        bool: 是否包含 city 字段
    """
    if not business_data:
        return False
    
    for item in business_data:
        if isinstance(item, dict) and item.get('city'):
            return True
    
    return False


def save_to_csv(business_data, filename=None):
    """
    保存商家数据到 CSV 文件
    
    Args:
        business_data: 商家数据列表
        filename: 文件名（可选）
        
    Returns:
        str: 保存的文件名
    """
    if not business_data:
        print("没有数据可保存", file=sys.stderr)
        return None
    
    # 确保输出目录存在
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # 生成文件名
    if not filename:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'business_data_{timestamp}.csv'
    
    filepath = os.path.join(OUTPUT_DIR, filename)
    
    try:
        # 标准化数据
        normalized_data = normalize_export_data(business_data)
        
        # 创建 DataFrame
        df = pd.DataFrame(normalized_data)
        
        # 保存到 CSV
        df.to_csv(filepath, index=False, encoding='utf-8-sig')
        
        print(f"数据已保存到 CSV: {filepath}", file=sys.stderr)
        return filename
    except Exception as e:
        print(f"保存 CSV 失败: {e}", file=sys.stderr)
        return None


def save_to_excel(business_data, filename=None):
    """
    保存商家数据到 Excel 文件
    
    Args:
        business_data: 商家数据列表
        filename: 文件名（可选）
        
    Returns:
        str: 保存的文件名
    """
    if not business_data:
        print("没有数据可保存", file=sys.stderr)
        return None
    
    # 确保输出目录存在
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # 生成文件名
    if not filename:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'business_data_{timestamp}.xlsx'
    
    filepath = os.path.join(OUTPUT_DIR, filename)
    
    try:
        # 标准化数据
        normalized_data = normalize_export_data(business_data)
        
        # 创建 DataFrame
        df = pd.DataFrame(normalized_data)
        
        # 保存到 Excel
        df.to_excel(filepath, index=False, engine='openpyxl')
        
        print(f"数据已保存到 Excel: {filepath}", file=sys.stderr)
        return filename
    except Exception as e:
        print(f"保存 Excel 失败: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return None
