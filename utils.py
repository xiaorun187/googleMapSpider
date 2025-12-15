import pandas as pd
from datetime import datetime
from config import OUTPUT_DIR
import os

def save_to_csv(data):
    if not data:
        print("没有数据可保存")
        return None

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"google_maps_data_{timestamp}.csv"
    filepath = os.path.join(OUTPUT_DIR, filename)

    df = pd.DataFrame(data)
    df.to_csv(filepath, sep=';', encoding='utf-8-sig', index=False)
    print(f"数据已保存到 {filepath}")
    return filename


def save_to_excel(data):
    if not data:
        print("没有数据可保存")
        return None

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"google_maps_data_{timestamp}.xlsx"  # 改为 .xlsx 后缀
    filepath = os.path.join(OUTPUT_DIR, filename)

    # 创建目录（如果不存在）
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 将数据转换为 DataFrame
    df = pd.DataFrame(data)

    # 保存为 Excel 文件
    df.to_excel(filepath, engine='openpyxl', index=False)  # 使用 openpyxl 引擎
    print(f"数据已保存到 {filepath}")
    return filename