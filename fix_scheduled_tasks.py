#!/usr/bin/env python3
"""
定时任务修复脚本
清理卡住的任务记录，重置配置
"""

import sqlite3
from datetime import datetime

DB_FILE = "data/business.db"

def fix_stuck_tasks():
    """修复卡住的任务"""
    print("=" * 60)
    print("修复卡住的任务")
    print("=" * 60)
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # 查找所有 running 状态的任务
    cursor.execute("""
        SELECT id, task_name, start_time
        FROM task_execution_history
        WHERE status = 'running'
    """)
    
    stuck_tasks = cursor.fetchall()
    
    if not stuck_tasks:
        print("✅ 没有卡住的任务")
    else:
        print(f"发现 {len(stuck_tasks)} 个卡住的任务，正在修复...")
        
        # 将所有 running 状态的任务标记为 failed
        cursor.execute("""
            UPDATE task_execution_history
            SET status = 'failed',
                end_time = datetime('now'),
                error_message = '任务超时或异常终止（自动清理）'
            WHERE status = 'running'
        """)
        
        conn.commit()
        print(f"✅ 已修复 {cursor.rowcount} 个任务")
    
    cursor.close()
    conn.close()
    print()

def delete_test_tasks():
    """删除测试任务记录"""
    print("=" * 60)
    print("清理测试任务记录")
    print("=" * 60)
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # 删除所有 test_task
    cursor.execute("""
        DELETE FROM task_execution_history
        WHERE task_name = 'test_task'
    """)
    
    deleted_count = cursor.rowcount
    conn.commit()
    
    if deleted_count > 0:
        print(f"✅ 已删除 {deleted_count} 条测试任务记录")
    else:
        print("✅ 没有测试任务记录需要删除")
    
    cursor.close()
    conn.close()
    print()

def reset_task_config():
    """重置任务配置为凌晨2点"""
    print("=" * 60)
    print("重置任务配置")
    print("=" * 60)
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # 更新任务配置为凌晨2点
    cursor.execute("""
        UPDATE scheduled_tasks
        SET schedule_hour = 2,
            schedule_minute = 0,
            enabled = 1,
            updated_at = datetime('now')
        WHERE task_name = 'contact_extraction'
    """)
    
    conn.commit()
    
    if cursor.rowcount > 0:
        print("✅ 已将任务配置重置为每天凌晨 02:00")
    else:
        print("⚠️  未找到任务配置")
    
    cursor.close()
    conn.close()
    print()

def show_summary():
    """显示修复后的摘要"""
    print("=" * 60)
    print("修复后的状态")
    print("=" * 60)
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # 任务配置
    cursor.execute("""
        SELECT task_name, schedule_hour, schedule_minute, enabled
        FROM scheduled_tasks
        WHERE task_name = 'contact_extraction'
    """)
    
    row = cursor.fetchone()
    if row:
        task_name, hour, minute, enabled = row
        status = "✅ 启用" if enabled else "❌ 禁用"
        print(f"任务配置: {task_name}")
        print(f"执行时间: 每天 {hour:02d}:{minute:02d}")
        print(f"状态: {status}")
    
    # 运行中的任务
    cursor.execute("""
        SELECT COUNT(*) FROM task_execution_history
        WHERE status = 'running'
    """)
    
    running_count = cursor.fetchone()[0]
    print(f"\n运行中的任务: {running_count} 个")
    
    # 最近的执行记录
    cursor.execute("""
        SELECT task_name, start_time, status
        FROM task_execution_history
        WHERE task_name = 'contact_extraction'
        ORDER BY start_time DESC
        LIMIT 3
    """)
    
    print("\n最近3次执行:")
    for task_name, start_time, status in cursor.fetchall():
        print(f"  - {start_time}: {status}")
    
    cursor.close()
    conn.close()
    print()

if __name__ == "__main__":
    print("\n🔧 定时任务修复工具")
    print(f"执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    fix_stuck_tasks()
    delete_test_tasks()
    reset_task_config()
    show_summary()
    
    print("=" * 60)
    print("修复完成！")
    print("=" * 60)
    print("\n⚠️  注意: 需要重启应用才能使配置生效")
    print("建议操作:")
    print("1. 停止当前运行的 app.py")
    print("2. 重新启动 app.py")
    print("3. 检查前端界面确认配置正确\n")
