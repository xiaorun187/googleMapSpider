#!/usr/bin/env python3
"""
初始化AI配置脚本
用于在服务器上设置默认的AI配置
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from db import get_db_connection, release_connection
from models.ai_configuration import AIConfiguration


def init_default_ai_config():
    """初始化默认AI配置"""
    try:
        # 检查是否已有配置
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM ai_configurations LIMIT 1')
        existing = cursor.fetchone()
        
        if existing:
            print("AI配置已存在，跳过初始化")
            cursor.close()
            release_connection(conn)
            return True
        
        # 创建默认配置
        default_config = AIConfiguration(
            api_endpoint='https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent',
            api_key=AIConfiguration.encrypt_key('AIzaSyCWxgCgsgL9Ku2MdnolX7YNolLME9OP0QE'),
            model='gemini-1.5-flash-latest'
        )
        
        # 保存到数据库
        cursor.execute('''
            INSERT INTO ai_configurations (provider, api_endpoint, api_key_encrypted, model_name, is_active)
            VALUES (?, ?, ?, ?, ?)
        ''', ('google', default_config.api_endpoint, default_config.api_key, default_config.model, 1))
        
        conn.commit()
        cursor.close()
        release_connection(conn)
        
        print("默认AI配置初始化成功")
        print(f"API端点: {default_config.api_endpoint}")
        print(f"模型: {default_config.model}")
        
        return True
        
    except Exception as e:
        print(f"初始化AI配置失败: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return False


if __name__ == '__main__':
    success = init_default_ai_config()
    sys.exit(0 if success else 1)