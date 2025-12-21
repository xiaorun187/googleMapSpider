#!/usr/bin/env python3
"""检查 AI 配置和测试邮件生成功能"""
import sys
sys.path.insert(0, '.')

from db import get_db_connection, release_connection
from models.ai_configuration import AIConfiguration
from utils.ai_email_assistant import AIEmailAssistant

def check_ai_config():
    """检查数据库中的 AI 配置"""
    print("=== 检查 AI 配置 ===")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, provider, api_endpoint, api_key_encrypted, model_name, is_active FROM ai_configurations')
    rows = cursor.fetchall()
    
    if not rows:
        print("❌ 没有找到 AI 配置记录")
        cursor.close()
        release_connection(conn)
        return None
    
    for row in rows:
        print(f"ID: {row[0]}")
        print(f"Provider: {row[1]}")
        print(f"API Endpoint: {row[2]}")
        key = row[3]
        print(f"API Key (encrypted): {key[:50] if key else 'None'}...")
        print(f"Model: {row[4]}")
        print(f"Is Active: {row[5]}")
        
        # 尝试解密 API Key
        if key:
            decrypted = AIConfiguration.decrypt_key(key)
            print(f"API Key (decrypted): {decrypted[:20] if decrypted else 'FAILED TO DECRYPT'}...")
        print("---")
    
    cursor.close()
    release_connection(conn)
    return rows[0] if rows else None

def test_ai_email_generation():
    """测试 AI 邮件生成"""
    print("\n=== 测试 AI 邮件生成 ===")
    
    # 从数据库获取配置
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT api_endpoint, api_key_encrypted, model_name FROM ai_configurations ORDER BY id DESC LIMIT 1')
    row = cursor.fetchone()
    cursor.close()
    release_connection(conn)
    
    if not row:
        print("❌ 没有 AI 配置，无法测试")
        return
    
    api_endpoint = row[0] or ''
    encrypted_key = row[1] or ''
    model = row[2] or ''
    
    print(f"API Endpoint: {api_endpoint}")
    print(f"Model: {model}")
    
    # 创建配置对象 - 注意这里 api_key 应该是加密后的
    config = AIConfiguration(
        api_endpoint=api_endpoint,
        api_key=encrypted_key,  # 传入加密的 key
        model=model
    )
    
    print(f"\n配置检查:")
    print(f"  - api_endpoint: {bool(config.api_endpoint)}")
    print(f"  - api_key: {bool(config.api_key)}")
    print(f"  - model: {bool(config.model)}")
    
    # 创建助手
    assistant = AIEmailAssistant(config)
    print(f"  - is_configured: {assistant.is_configured}")
    
    if not assistant.is_configured:
        print("❌ AI 助手未正确配置")
        return
    
    # 测试生成邮件
    print("\n正在调用 AI 生成邮件...")
    result = assistant.generate_email({'business_name': '测试公司', 'product': '软件服务'})
    
    print(f"\n生成结果:")
    print(f"  - success: {result.success}")
    print(f"  - error_message: {result.error_message}")
    if result.content:
        print(f"  - content (前200字): {result.content[:200]}...")
    else:
        print("  - content: (空)")

if __name__ == '__main__':
    check_ai_config()
    test_ai_email_generation()
