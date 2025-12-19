import pandas as pd
from datetime import datetime
from config import OUTPUT_DIR
import os

# 标准导出列顺序（包含 city 字段）
EXPORT_COLUMNS = [
    'name', 'website', 'emails', 'phones', 'city',
    'facebook', 'twitter', 'instagram', 'linkedin', 'whatsapp', 'youtube'
]


def normalize_export_data(data):
    """
    标准化导出数据，确保所有必要字段存在
    
    Features:
    - 确保 city 字段存在 (Requirements 9.5)
    - 处理列表类型字段（emails, phones）
    - 统一字段顺序
    """
    normalized = []
    for item in data:
        record = {}
        for col in EXPORT_COLUMNS:
            value = item.get(col, '')
            # 处理列表类型字段
            if isinstance(value, list):
                value = ', '.join(str(v) for v in value if v)
            record[col] = value or ''
        normalized.append(record)
    return normalized


def save_to_csv(data):
    """
    保存数据到 CSV 文件
    
    Features:
    - 包含 city 字段 (Requirements 9.5)
    - UTF-8 编码支持中文
    """
    if not data:
        print("没有数据可保存")
        return None

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"google_maps_data_{timestamp}.csv"
    filepath = os.path.join(OUTPUT_DIR, filename)

    # 创建目录（如果不存在）
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 标准化数据
    normalized_data = normalize_export_data(data)
    df = pd.DataFrame(normalized_data)
    
    # 确保列顺序
    available_cols = [col for col in EXPORT_COLUMNS if col in df.columns]
    df = df[available_cols]
    
    df.to_csv(filepath, sep=';', encoding='utf-8-sig', index=False)
    print(f"数据已保存到 {filepath}")
    return filename


def save_to_excel(data):
    """
    保存数据到 Excel 文件
    
    Features:
    - 包含 city 字段 (Requirements 9.5)
    - 使用 openpyxl 引擎
    """
    if not data:
        print("没有数据可保存")
        return None

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"google_maps_data_{timestamp}.xlsx"
    filepath = os.path.join(OUTPUT_DIR, filename)

    # 创建目录（如果不存在）
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 标准化数据
    normalized_data = normalize_export_data(data)
    df = pd.DataFrame(normalized_data)
    
    # 确保列顺序
    available_cols = [col for col in EXPORT_COLUMNS if col in df.columns]
    df = df[available_cols]

    # 保存为 Excel 文件
    df.to_excel(filepath, engine='openpyxl', index=False)
    print(f"数据已保存到 {filepath}")
    return filename


def has_city_field(data):
    """
    检查数据是否包含 city 字段
    
    用于测试验证 (Property 23)
    """
    if not data:
        return False
    return any('city' in item for item in data)