import sqlite3
from sqlite3 import Error
import sys
import threading
import uuid
from queue import Queue
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Optional

# SQLite database file path
DB_FILE = "business.db"


@dataclass
class ValidationResult:
    """验证结果数据类"""
    is_valid: bool
    error_message: Optional[str] = None
    existing_record: Optional[dict] = None


def generate_unique_id() -> str:
    """生成 UUID 格式的唯一标识符"""
    return str(uuid.uuid4())


# ============================================================================
# 连接池管理
# ============================================================================
MAX_CONNECTIONS = 5
_connection_pool = Queue(maxsize=MAX_CONNECTIONS)
_pool_lock = threading.Lock()
_pool_initialized = False


def _init_connection_pool():
    """初始化连接池"""
    global _pool_initialized
    with _pool_lock:
        if _pool_initialized:
            return
        for _ in range(MAX_CONNECTIONS):
            try:
                conn = sqlite3.connect(DB_FILE, check_same_thread=False)
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA synchronous=NORMAL")
                _connection_pool.put(conn)
            except Error as e:
                print(f"初始化连接池失败: {e}", file=sys.stderr)
        _pool_initialized = True


def get_db_connection():
    """从连接池获取数据库连接"""
    _init_connection_pool()
    try:
        conn = _connection_pool.get(timeout=5)
        return conn
    except Exception:
        try:
            conn = sqlite3.connect(DB_FILE, check_same_thread=False)
            return conn
        except Error as e:
            print(f"Error connecting to database: {e}", file=sys.stderr)
            return None


def release_connection(connection):
    """将连接归还到连接池"""
    if connection:
        try:
            if not _connection_pool.full():
                _connection_pool.put_nowait(connection)
            else:
                connection.close()
        except Exception:
            try:
                connection.close()
            except Exception:
                pass


@contextmanager
def get_connection():
    """上下文管理器：自动获取和释放连接"""
    connection = get_db_connection()
    try:
        yield connection
    finally:
        release_connection(connection)


def init_database():
    """初始化数据库表结构"""
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # 创建 business_records 表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS business_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                unique_id TEXT,
                name TEXT,
                website TEXT,
                email TEXT,
                phones TEXT,
                facebook TEXT,
                twitter TEXT,
                instagram TEXT,
                linkedin TEXT,
                whatsapp TEXT,
                youtube TEXT,
                city TEXT,
                product TEXT,
                send_count INTEGER DEFAULT 0,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 创建 ai_configurations 表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ai_configurations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider TEXT NOT NULL DEFAULT 'custom',
                api_endpoint TEXT,
                api_key_encrypted TEXT,
                model_name TEXT,
                temperature REAL DEFAULT 0.7,
                max_tokens INTEGER DEFAULT 1024,
                is_active INTEGER DEFAULT 1,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 创建 last_extraction_positions 表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS last_extraction_positions (
                url TEXT PRIMARY KEY,
                last_position INTEGER,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 创建索引
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_business_email ON business_records(email)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_business_city ON business_records(city)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_business_name_website ON business_records(name, website)")
        
        connection.commit()
        print("数据库初始化完成", file=sys.stderr)
        
    except Error as e:
        print(f"数据库初始化失败: {e}", file=sys.stderr)
        if connection:
            connection.rollback()
    finally:
        if cursor:
            cursor.close()
        release_connection(connection)


# 启动时初始化数据库
init_database()


def check_duplicate_exists(name: str, website: str) -> Optional[dict]:
    """检查是否存在相同 name + website 的记录"""
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("""
            SELECT id, unique_id, name, website, email
            FROM business_records
            WHERE name = ? AND website = ?
        """, (name, website))
        row = cursor.fetchone()
        if row:
            return {
                'id': row[0],
                'unique_id': row[1],
                'name': row[2],
                'website': row[3],
                'email': row[4]
            }
        return None
    finally:
        if cursor:
            cursor.close()
        release_connection(connection)


def validate_business_data(business: dict) -> tuple:
    """验证单条商家数据的有效性"""
    if not isinstance(business, dict):
        return False, "数据格式无效：不是字典类型"
    
    name = business.get('name', '')
    if not name or not isinstance(name, str) or not name.strip():
        return False, "商家名称为空或无效"
    
    if 'results' in business or 'validation' in business:
        return False, "数据包含无效的嵌套结构"
    
    return True, ""


def save_single_business_to_db(business: dict) -> dict:
    """
    实时保存单条商家数据到数据库
    
    Args:
        business: 单条商家数据字典
        
    Returns:
        dict: 包含 success, action, error, record_id 的结果
    """
    result = {
        'success': False,
        'action': None,
        'error': None,
        'record_id': None,
        'name': business.get('name', 'Unknown')
    }
    
    # 数据验证
    is_valid, error_msg = validate_business_data(business)
    if not is_valid:
        result['error'] = error_msg
        result['action'] = 'skipped'
        print(f"[DB] 数据验证失败 [{result['name']}]: {error_msg}", file=sys.stderr)
        return result
    
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        if not connection:
            result['error'] = "无法获取数据库连接"
            print("[DB ERROR] 无法获取数据库连接", file=sys.stderr)
            return result
        
        cursor = connection.cursor()
        
        # 提取数据字段
        name = business.get('name', '').strip()
        website = business.get('website', '') or ''
        emails = business.get('emails', []) if business.get('emails') else []
        phones = ', '.join(business.get('phones', [])) if business.get('phones') else ''
        facebook = business.get('facebook', '') or ''
        twitter = business.get('twitter', '') or ''
        instagram = business.get('instagram', '') or ''
        linkedin = business.get('linkedin', '') or ''
        whatsapp = business.get('whatsapp', '') or ''
        youtube = business.get('youtube', '') or ''
        city = business.get('city', '') or ''
        product = business.get('product', '') or ''
        email_value = emails[0] if emails else None
        
        # 检查数据库中是否存在重复
        existing = check_duplicate_exists(name, website)
        
        if existing:
            # 更新现有记录
            cursor.execute("""
                UPDATE business_records 
                SET email = COALESCE(?, email),
                    phones = COALESCE(NULLIF(?, ''), phones),
                    facebook = COALESCE(NULLIF(?, ''), facebook),
                    twitter = COALESCE(NULLIF(?, ''), twitter),
                    instagram = COALESCE(NULLIF(?, ''), instagram),
                    linkedin = COALESCE(NULLIF(?, ''), linkedin),
                    whatsapp = COALESCE(NULLIF(?, ''), whatsapp),
                    youtube = COALESCE(NULLIF(?, ''), youtube),
                    city = COALESCE(NULLIF(?, ''), city),
                    product = COALESCE(NULLIF(?, ''), product),
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (email_value, phones, facebook, twitter, instagram, 
                  linkedin, whatsapp, youtube, city, product, existing['id']))
            
            connection.commit()
            result['success'] = True
            result['action'] = 'updated'
            result['record_id'] = existing['id']
            print(f"[DB] 更新记录 [{name}] ID={existing['id']}", file=sys.stderr)
        else:
            # 插入新记录
            unique_id = generate_unique_id()
            cursor.execute("""
                INSERT INTO business_records 
                (unique_id, name, website, email, phones, facebook, twitter, 
                 instagram, linkedin, whatsapp, youtube, city, product, send_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            """, (unique_id, name, website, email_value, phones, facebook, 
                  twitter, instagram, linkedin, whatsapp, youtube, city, product))
            
            connection.commit()
            result['success'] = True
            result['action'] = 'inserted'
            result['record_id'] = cursor.lastrowid
            print(f"[DB] 插入新记录 [{name}] ID={result['record_id']}", file=sys.stderr)
        
    except Error as e:
        if connection:
            try:
                connection.rollback()
            except Exception:
                pass
        result['error'] = str(e)
        print(f"[DB ERROR] 保存失败 [{result['name']}]: {e}", file=sys.stderr)
    finally:
        if cursor:
            try:
                cursor.close()
            except Exception:
                pass
        release_connection(connection)
    
    return result


def save_business_data_to_db(data: list, product: str = '', city: str = '') -> dict:
    """
    批量保存商家数据到数据库
    
    Args:
        data: 商家数据列表
        product: 产品/关键词
        city: 城市名称
        
    Returns:
        dict: 包含 inserted, updated, skipped, errors 的统计结果
    """
    stats = {
        'inserted': 0,
        'updated': 0,
        'skipped': 0,
        'errors': 0,
        'total': len(data) if data else 0
    }
    
    if not data or not isinstance(data, list):
        print("[DB] 没有数据需要保存", file=sys.stderr)
        return stats
    
    for business in data:
        if not isinstance(business, dict):
            stats['skipped'] += 1
            continue
        
        # 添加 city 和 product 信息
        if city and not business.get('city'):
            business['city'] = city
        if product and not business.get('product'):
            business['product'] = product
        
        result = save_single_business_to_db(business)
        
        if result['success']:
            if result['action'] == 'inserted':
                stats['inserted'] += 1
            elif result['action'] == 'updated':
                stats['updated'] += 1
        elif result['action'] == 'skipped':
            stats['skipped'] += 1
        else:
            stats['errors'] += 1
    
    print(f"[DB] 批量保存完成: 插入={stats['inserted']}, 更新={stats['updated']}, 跳过={stats['skipped']}, 错误={stats['errors']}", file=sys.stderr)
    return stats


def get_history_records(page: int = 1, per_page: int = 20, search: str = '', 
                        show_empty_email: bool = True) -> dict:
    """
    获取历史记录（分页）
    
    Args:
        page: 页码
        per_page: 每页数量
        search: 搜索关键词
        show_empty_email: 是否显示空邮箱记录
        
    Returns:
        dict: 包含 records, total, page, per_page, total_pages
    """
    connection = None
    cursor = None
    result = {
        'records': [],
        'total': 0,
        'page': page,
        'per_page': per_page,
        'total_pages': 0
    }
    
    try:
        connection = get_db_connection()
        if not connection:
            return result
        
        cursor = connection.cursor()
        
        # 构建查询条件
        conditions = []
        params = []
        
        if not show_empty_email:
            conditions.append("email IS NOT NULL AND email != ''")
        
        if search:
            conditions.append("(name LIKE ? OR email LIKE ? OR city LIKE ? OR product LIKE ?)")
            search_param = f"%{search}%"
            params.extend([search_param, search_param, search_param, search_param])
            print(f"[DEBUG] Search conditions: {conditions}, params: {params}", file=sys.stderr)
        
        where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
        
        # 获取总数
        count_sql = f"SELECT COUNT(*) FROM business_records{where_clause}"
        cursor.execute(count_sql, params)
        total = cursor.fetchone()[0]
        result['total'] = total
        result['total_pages'] = (total + per_page - 1) // per_page if per_page > 0 else 0
        
        # 获取分页数据
        offset = (page - 1) * per_page
        data_sql = f"""
            SELECT id, unique_id, name, website, email, phones, facebook, twitter,
                   instagram, linkedin, whatsapp, youtube, city, product, send_count,
                   updated_at, created_at
            FROM business_records
            {where_clause}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """
        cursor.execute(data_sql, params + [per_page, offset])
        
        columns = ['id', 'unique_id', 'name', 'website', 'email', 'phones', 'facebook',
                   'twitter', 'instagram', 'linkedin', 'whatsapp', 'youtube', 'city',
                   'product', 'send_count', 'updated_at', 'created_at']
        
        for row in cursor.fetchall():
            record = dict(zip(columns, row))
            result['records'].append(record)
        
    except Error as e:
        print(f"[DB ERROR] 获取历史记录失败: {e}", file=sys.stderr)
    finally:
        if cursor:
            cursor.close()
        release_connection(connection)
    
    return result


def update_send_count(record_ids: list) -> bool:
    """
    更新发送次数
    
    Args:
        record_ids: 记录ID列表
        
    Returns:
        bool: 是否成功
    """
    if not record_ids:
        return False
    
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        if not connection:
            return False
        
        cursor = connection.cursor()
        placeholders = ','.join(['?' for _ in record_ids])
        cursor.execute(f"""
            UPDATE business_records 
            SET send_count = send_count + 1, updated_at = CURRENT_TIMESTAMP
            WHERE id IN ({placeholders})
        """, record_ids)
        connection.commit()
        print(f"[DB] 更新发送次数: {len(record_ids)} 条记录", file=sys.stderr)
        return True
        
    except Error as e:
        print(f"[DB ERROR] 更新发送次数失败: {e}", file=sys.stderr)
        if connection:
            connection.rollback()
        return False
    finally:
        if cursor:
            cursor.close()
        release_connection(connection)


def get_last_position(url: str) -> int:
    """
    获取上次抓取位置
    
    Args:
        url: 抓取URL标识
        
    Returns:
        int: 上次位置，默认0
    """
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        if not connection:
            return 0
        
        cursor = connection.cursor()
        cursor.execute("SELECT last_position FROM last_extraction_positions WHERE url = ?", (url,))
        row = cursor.fetchone()
        return row[0] if row else 0
        
    except Error as e:
        print(f"[DB ERROR] 获取位置失败: {e}", file=sys.stderr)
        return 0
    finally:
        if cursor:
            cursor.close()
        release_connection(connection)


def save_last_position(url: str, position: int) -> bool:
    """
    保存抓取位置
    
    Args:
        url: 抓取URL标识
        position: 当前位置
        
    Returns:
        bool: 是否成功
    """
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        if not connection:
            return False
        
        cursor = connection.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO last_extraction_positions (url, last_position, timestamp)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        """, (url, position))
        connection.commit()
        return True
        
    except Error as e:
        print(f"[DB ERROR] 保存位置失败: {e}", file=sys.stderr)
        if connection:
            connection.rollback()
        return False
    finally:
        if cursor:
            cursor.close()
        release_connection(connection)


def get_facebook_non_email() -> list:
    """
    获取有Facebook但无邮箱的记录
    
    Returns:
        list: 记录列表
    """
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        if not connection:
            return []
        
        cursor = connection.cursor()
        cursor.execute("""
            SELECT id, unique_id, name, website, facebook
            FROM business_records
            WHERE facebook IS NOT NULL AND facebook != ''
            AND (email IS NULL OR email = '')
        """)
        
        columns = ['id', 'unique_id', 'name', 'website', 'facebook']
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
        
    except Error as e:
        print(f"[DB ERROR] 获取Facebook记录失败: {e}", file=sys.stderr)
        return []
    finally:
        if cursor:
            cursor.close()
        release_connection(connection)


def update_business_email(record_id: int, email: str) -> bool:
    """
    更新商家邮箱
    
    Args:
        record_id: 记录ID
        email: 邮箱地址
        
    Returns:
        bool: 是否成功
    """
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        if not connection:
            return False
        
        cursor = connection.cursor()
        cursor.execute("""
            UPDATE business_records 
            SET email = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (email, record_id))
        connection.commit()
        return cursor.rowcount > 0
        
    except Error as e:
        print(f"[DB ERROR] 更新邮箱失败: {e}", file=sys.stderr)
        if connection:
            connection.rollback()
        return False
    finally:
        if cursor:
            cursor.close()
        release_connection(connection)


def delete_business_email(record_id: int) -> bool:
    """
    删除商家记录
    
    Args:
        record_id: 记录ID
        
    Returns:
        bool: 是否成功
    """
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        if not connection:
            return False
        
        cursor = connection.cursor()
        cursor.execute("DELETE FROM business_records WHERE id = ?", (record_id,))
        connection.commit()
        return cursor.rowcount > 0
        
    except Error as e:
        print(f"[DB ERROR] 删除记录失败: {e}", file=sys.stderr)
        if connection:
            connection.rollback()
        return False
    finally:
        if cursor:
            cursor.close()
        release_connection(connection)


# ============================================================================
# AI 配置相关函数
# ============================================================================

def get_ai_configuration() -> Optional[dict]:
    """
    获取AI配置
    
    Returns:
        dict: AI配置信息，或None
    """
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        if not connection:
            return None
        
        cursor = connection.cursor()
        cursor.execute("""
            SELECT id, provider, api_endpoint, api_key_encrypted, model_name,
                   temperature, max_tokens, is_active, updated_at, created_at
            FROM ai_configurations
            WHERE is_active = 1
            ORDER BY updated_at DESC
            LIMIT 1
        """)
        
        row = cursor.fetchone()
        if row:
            return {
                'id': row[0],
                'provider': row[1],
                'api_endpoint': row[2],
                'api_key': row[3],  # 注意：这里返回的是加密的key
                'model_name': row[4],
                'temperature': row[5],
                'max_tokens': row[6],
                'is_active': row[7],
                'updated_at': row[8],
                'created_at': row[9]
            }
        return None
        
    except Error as e:
        print(f"[DB ERROR] 获取AI配置失败: {e}", file=sys.stderr)
        return None
    finally:
        if cursor:
            cursor.close()
        release_connection(connection)


def save_ai_configuration(config: dict) -> bool:
    """
    保存AI配置
    
    Args:
        config: 配置字典，包含 api_endpoint, api_key, model_name 等
        
    Returns:
        bool: 是否成功
    """
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        if not connection:
            return False
        
        cursor = connection.cursor()
        
        # 先将所有配置设为非活跃
        cursor.execute("UPDATE ai_configurations SET is_active = 0")
        
        # 检查是否存在配置
        cursor.execute("SELECT id FROM ai_configurations LIMIT 1")
        existing = cursor.fetchone()
        
        if existing:
            # 更新现有配置
            cursor.execute("""
                UPDATE ai_configurations 
                SET provider = ?,
                    api_endpoint = ?,
                    api_key_encrypted = ?,
                    model_name = ?,
                    temperature = ?,
                    max_tokens = ?,
                    is_active = 1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (
                config.get('provider', 'custom'),
                config.get('api_endpoint', ''),
                config.get('api_key', ''),
                config.get('model_name', ''),
                config.get('temperature', 0.7),
                config.get('max_tokens', 1024),
                existing[0]
            ))
        else:
            # 插入新配置
            cursor.execute("""
                INSERT INTO ai_configurations 
                (provider, api_endpoint, api_key_encrypted, model_name, temperature, max_tokens, is_active)
                VALUES (?, ?, ?, ?, ?, ?, 1)
            """, (
                config.get('provider', 'custom'),
                config.get('api_endpoint', ''),
                config.get('api_key', ''),
                config.get('model_name', ''),
                config.get('temperature', 0.7),
                config.get('max_tokens', 1024)
            ))
        
        connection.commit()
        print("[DB] AI配置保存成功", file=sys.stderr)
        return True
        
    except Error as e:
        print(f"[DB ERROR] 保存AI配置失败: {e}", file=sys.stderr)
        if connection:
            connection.rollback()
        return False
    finally:
        if cursor:
            cursor.close()
        release_connection(connection)


def get_all_business_records() -> list:
    """
    获取所有商家记录（用于导出）
    
    Returns:
        list: 所有记录列表
    """
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        if not connection:
            return []
        
        cursor = connection.cursor()
        cursor.execute("""
            SELECT id, unique_id, name, website, email, phones, facebook, twitter,
                   instagram, linkedin, whatsapp, youtube, city, product, send_count,
                   updated_at, created_at
            FROM business_records
            ORDER BY created_at DESC
        """)
        
        columns = ['id', 'unique_id', 'name', 'website', 'email', 'phones', 'facebook',
                   'twitter', 'instagram', 'linkedin', 'whatsapp', 'youtube', 'city',
                   'product', 'send_count', 'updated_at', 'created_at']
        
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
        
    except Error as e:
        print(f"[DB ERROR] 获取所有记录失败: {e}", file=sys.stderr)
        return []
    finally:
        if cursor:
            cursor.close()
        release_connection(connection)


def get_records_by_ids(record_ids: list) -> list:
    """
    根据ID列表获取记录
    
    Args:
        record_ids: 记录ID列表
        
    Returns:
        list: 记录列表
    """
    if not record_ids:
        return []
    
    connection = None
    cursor = None
    
    try:
        connection = get_db_connection()
        if not connection:
            return []
        
        cursor = connection.cursor()
        placeholders = ','.join(['?' for _ in record_ids])
        cursor.execute(f"""
            SELECT id, unique_id, name, website, email, phones, facebook, twitter,
                   instagram, linkedin, whatsapp, youtube, city, product, send_count,
                   updated_at, created_at
            FROM business_records
            WHERE id IN ({placeholders})
        """, record_ids)
        
        columns = ['id', 'unique_id', 'name', 'website', 'email', 'phones', 'facebook',
                   'twitter', 'instagram', 'linkedin', 'whatsapp', 'youtube', 'city',
                   'product', 'send_count', 'updated_at', 'created_at']
        
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
        
    except Error as e:
        print(f"[DB ERROR] 根据ID获取记录失败: {e}", file=sys.stderr)
        return []
    finally:
        if cursor:
            cursor.close()
        release_connection(connection)
