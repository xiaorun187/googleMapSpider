import sqlite3

# 连接数据库
conn = sqlite3.connect('business.db')
cursor = conn.cursor()

# 检查表是否存在
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='business_records'")
table_exists = cursor.fetchone()
print(f"Table exists: {table_exists is not None}")

if table_exists:
    # 获取记录总数
    cursor.execute('SELECT COUNT(*) FROM business_records')
    total_records = cursor.fetchone()[0]
    print(f'Total records: {total_records}')
    
    # 获取前5条记录
    cursor.execute('SELECT name, email, city FROM business_records LIMIT 5')
    records = cursor.fetchall()
    print('Sample records:')
    for row in records:
        print(f'  Name: {row[0]}, Email: {row[1]}, City: {row[2]}')
    
    # 测试搜索功能
    print('\nTesting search with "餐厅":')
    cursor.execute("SELECT name, email, city FROM business_records WHERE name LIKE '%餐厅%' OR email LIKE '%餐厅%' OR city LIKE '%餐厅%' OR product LIKE '%餐厅%'")
    search_results = cursor.fetchall()
    print(f'Search results: {len(search_results)} records')
    for row in search_results:
        print(f'  Name: {row[0]}, Email: {row[1]}, City: {row[2]}')

conn.close()