#!/usr/bin/env python3
"""
定时任务诊断脚本
检查定时任务的配置和执行状态
"""

import sqlite3
from datetime import datetime

DB_FILE = "data/business.db"

def check_task_config():
    """检查任务配置"""
    print("=" * 60)
    print("定时任务配置")
    print("=" * 60)
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT task_name, schedule_hour, schedule_minute, enabled, updated_at
        FROM scheduled_tasks
    """)
    
    for row in cursor.fetchall():
        task_name, hour, minute, enabled, updated_at = row
        status = "✅ 启用" if enabled else "❌ 禁用"
        print(f"任务名称: {task_name}")
        print(f"执行时间: {hour:02d}:{minute:02d}")
        print(f"状态: {status}")
        print(f"最后更新: {updated_at}")
    
    cursor.close()
    conn.close()
    print()

def check_execution_history():
    """检查执行历史"""
    print("=" * 60)
    print("最近10次执行历史")
    print("=" * 60)
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, task_name, start_time, end_time, status, 
               records_processed, records_success, records_failed, error_message
        FROM task_execution_history
        ORDER BY start_time DESC
        LIMIT 10
    """)
    
    for row in cursor.fetchall():
        id, task_name, start_time, end_time, status, processed, success, failed, error = row
        
        print(f"\n执行ID: {id}")
        print(f"任务名称: {task_name}")
        print(f"开始时间: {start_time}")
        print(f"结束时间: {end_time or '未完成'}")
        print(f"状态: {status}")
        
        if status == 'running':
            # 计算运行时长
            try:
                start = datetime.fromisoformat(start_time)
                now = datetime.now()
                duration = (now - start).total_seconds()
                print(f"⚠️  已运行: {duration/60:.1f} 分钟")
            except:
                pass
        else:
            print(f"处理记录: {processed}")
            print(f"成功: {success}, 失败: {failed}")
            if error:
                print(f"错误: {error}")
    
    cursor.close()
    conn.close()
    print()

def check_pending_records():
    """检查待处理记录数"""
    print("=" * 60)
    print("待处理记录统计")
    print("=" * 60)
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT COUNT(*) FROM business_records 
        WHERE website IS NOT NULL AND website != '' 
        AND (email IS NULL OR email = '')
    """)
    
    count = cursor.fetchone()[0]
    print(f"有网站但无邮箱的记录: {count} 条")
    print(f"预计处理时间: {count * 2 / 60:.1f} 分钟 (按每条2秒计算)")
    
    cursor.close()
    conn.close()
    print()

def check_running_tasks():
    """检查是否有卡住的任务"""
    print("=" * 60)
    print("运行中的任务检查")
    print("=" * 60)
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, task_name, start_time
        FROM task_execution_history
        WHERE status = 'running'
        ORDER BY start_time DESC
    """)
    
    running_tasks = cursor.fetchall()
    
    if not running_tasks:
        print("✅ 没有运行中的任务")
    else:
        print(f"⚠️  发现 {len(running_tasks)} 个运行中的任务:")
        for id, task_name, start_time in running_tasks:
            try:
                start = datetime.fromisoformat(start_time)
                now = datetime.now()
                duration = (now - start).total_seconds()
                
                if duration > 3600:  # 超过1小时
                    print(f"  ❌ ID {id}: {task_name} - 已运行 {duration/3600:.1f} 小时 (可能卡住)")
                elif duration > 600:  # 超过10分钟
                    print(f"  ⚠️  ID {id}: {task_name} - 已运行 {duration/60:.1f} 分钟")
                else:
                    print(f"  ✅ ID {id}: {task_name} - 已运行 {duration/60:.1f} 分钟 (正常)")
            except:
                print(f"  ❓ ID {id}: {task_name} - 无法解析时间")
    
    cursor.close()
    conn.close()
    print()

if __name__ == "__main__":
    print("\n🔍 定时任务诊断报告")
    print(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    check_task_config()
    check_pending_records()
    check_running_tasks()
    check_execution_history()
    
    print("=" * 60)
    print("诊断完成")
    print("=" * 60)
