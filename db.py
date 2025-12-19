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


# ============================================================================
# 数据验证结果类 (Requirements 4.1, 4.2)
# ============================================================================
@dataclass
class ValidationResult:
    """验证结果数据类"""
    is_valid: bool
    error_message: Optional[str] = None
    existing_record: Optional[dict] = None


def generate_unique_id() -> str:
    """
    生成 UUID 格式的唯一标识符
    
    Returns:
        str: UUID 字符串
    """
    return str(uuid.uuid4())

# ============================================================================
# 连接池管理 (Requirements 4.5)
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
                conn.execute("PRAGMA journal_mode=WAL")  # 启用WAL模式提高并发性能
                conn.execute("PRAGMA synchronous=NORMAL")  # 平衡性能和安全
                _connection_pool.put(conn)
            except Error as e:
                print(f"初始化连接池失败: {e}", file=sys.stderr)
        _pool_initialized = True


def get_db_connection():
    """从连接池获取数据库连接"""
    _init_connection_pool()
    try:
        # 尝试从池中获取连接，超时5秒
        conn = _connection_pool.get(timeout=5)
        return conn
    except Exception:
        # 如果池为空，创建新连接
        try:
            conn = sqlite3.connect(DB_FILE, check_same_thread=False)
            return conn
        except Error as e:
            print(f"Error connecting to database: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)
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
        
        # 创建 business_records 表（基于 name + website 唯一性判断）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS business_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                unique_id TEXT NOT NULL,
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
        
        # 创建 ai_configurations 表 (Requirements 12.6)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ai_configurations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider TEXT NOT NULL DEFAULT 'gemini',
                api_endpoint TEXT,
                api_key_encrypted TEXT,
                model_name TEXT DEFAULT 'gemini-1.5-flash',
                temperature REAL DEFAULT 0.7,
                max_tokens INTEGER DEFAULT 1024,
                is_active INTEGER DEFAULT 1,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 添加 api_endpoint 字段到现有表（如果不存在）
        try:
            cursor.execute("ALTER TABLE ai_configurations ADD COLUMN api_endpoint TEXT")
        except Error:
            pass  # 列已存在
        
        # 创建 country_city_mappings 表 (Requirements 10.3)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS country_city_mappings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                country_code TEXT NOT NULL,
                country_name TEXT NOT NULL,
                city_name TEXT NOT NULL,
                is_active INTEGER DEFAULT 1,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(country_code, city_name)
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
        
        # 添加 city 字段到现有表（如果不存在）
        try:
            cursor.execute("ALTER TABLE business_records ADD COLUMN city TEXT")
        except Error:
            pass  # 列已存在
        
        # 添加 product 字段到现有表（如果不存在）
        try:
            cursor.execute("ALTER TABLE business_records ADD COLUMN product TEXT")
        except Error:
            pass  # 列已存在
        
        # 添加 unique_id 字段到现有表（如果不存在）
        try:
            cursor.execute("ALTER TABLE business_records ADD COLUMN unique_id TEXT")
        except Error:
            pass  # 列已存在
        
        # 为现有记录生成 unique_id（迁移逻辑）
        cursor.execute("SELECT id FROM business_records WHERE unique_id IS NULL OR unique_id = ''")
        records_without_uid = cursor.fetchall()
        for (record_id,) in records_without_uid:
            cursor.execute(
                "UPDATE business_records SET unique_id = ? WHERE id = ?",
                (generate_unique_id(), record_id)
            )
        
        # 移除旧的 email 唯一索引（如果存在）
        try:
            cursor.execute("DROP INDEX IF EXISTS idx_business_email_unique")
        except Error:
            pass
        
        # 创建索引以提高查询性能
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_business_email ON business_records(email)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_business_city ON business_records(city)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_business_product ON business_records(product)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_business_updated ON business_records(updated_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_country_city ON country_city_mappings(country_code)")
        
        # 创建 unique_id 唯一索引 (Requirements 3.3)
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_id ON business_records(unique_id)")
        
        # 创建 (name, website) 复合唯一索引 (Requirements 3.1)
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_name_website ON business_records(name, website)")
        
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


# ============================================================================
# 数据唯一性验证函数 (Requirements 4.1, 4.2)
# ============================================================================

def check_duplicate_exists(name: str, website: str, exclude_id: int = None) -> Optional[dict]:
    """
    检查是否存在相同 name + website 的记录
    
    Args:
        name: 商家名称
        website: 商家网站
        exclude_id: 排除的记录ID（用于更新操作）
        
    Returns:
        Optional[dict]: 存在重复时返回现有记录，否则返回 None
    """
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        if exclude_id:
            cursor.execute("""
                SELECT id, unique_id, name, website, email
                FROM business_records
                WHERE name = ? AND website = ? AND id != ?
            """, (name, website, exclude_id))
        else:
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


def validate_uniqueness(name: str, website: str, exclude_id: int = None) -> ValidationResult:
    """
    验证 name + website 组合的唯一性
    
    Args:
        name: 商家名称
        website: 商家网站
        exclude_id: 排除的记录ID（用于更新操作）
        
    Returns:
        ValidationResult: 验证结果
    """
    existing = check_duplicate_exists(name, website, exclude_id)
    
    if existing:
        return ValidationResult(
            is_valid=False,
            error_message=f"Record with name '{name}' and website '{website}' already exists (ID: {existing['id']})",
            existing_record=existing
        )
    
    return ValidationResult(is_valid=True)


def validate_business_data(business: dict) -> tuple[bool, str]:
    """
    验证单条商家数据的有效性
    
    Args:
        business: 商家数据字典
        
    Returns:
        tuple: (是否有效, 错误信息)
    """
    if not isinstance(business, dict):
        return False, "数据格式无效：不是字典类型"
    
    name = business.get('name', '')
    if not name or not isinstance(name, str) or not name.strip():
        return False, "商家名称为空或无效"
    
    # 检查是否包含无效的嵌套结构
    if 'results' in business or 'validation' in business:
        return False, "数据包含无效的嵌套结构"
    
    return True, ""


def save_single_business_to_db(business: dict) -> dict:
    """
    实时保存单条商家数据到数据库
    
    Features:
    - 单条数据验证
    - 基于 name + website 的唯一性判断
    - 事务完整性保证
    - 详细的日志记录
    
    Args:
        business: 单条商家数据字典
        
    Returns:
        dict: 包含 success, action (inserted/updated/skipped), error 的结果
    """
    result = {
        'success': False,
        'action': None,  # 'inserted', 'updated', 'skipped'
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
            print(f"[DB ERROR] 无法获取数据库连接", file=sys.stderr)
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
        
        # 检查数据库中是否存在重复
        existing = check_duplicate_exists(name, website)
        
        if existing:
            # 更新现有记录
            email_value = emails[0] if emails else None
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
            email_value = emails[0] if emails else None
            
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
    except Exception as e:
        if connection:
            try:
                connection.rollback()
            except Exception:
                pass
        result['error'] = str(e)
        print(f"[DB ERROR] 未知错误 [{result['name']}]: {e}", file=sys.stderr)
    finally:
        if cursor:
            try:
                cursor.close()
            except Exception:
                pass
        release_connection(connection)
    
    return result


def save_business_data_to_db(business_data):
    """
    Save business data to SQLite database with name+website uniqueness
    
    Features:
    - 基于 name + website 的唯一性判断 (Requirements 1.1, 1.2, 1.3)
    - 使用事务批量处理 (Requirements 4.2)
    - 错误回滚和单条重试 (Requirements 4.3)
    - 自动生成 unique_id (Requirements 2.1)
    - 支持 city 字段 (Requirements 9.3)
    
    Returns:
        dict: 包含 success, inserted_count, skipped_count, errors 的结果
    """
    connection = None
    cursor = None
    result = {
        'success': True,
        'inserted_count': 0,
        'skipped_count': 0,
        'updated_count': 0,
        'errors': []
    }
    
    try:
        connection = get_db_connection()
        connection.execute("BEGIN TRANSACTION")
        cursor = connection.cursor()

        # 用于跟踪本批次中的 name+website 组合
        seen_combinations = set()
        
        for business in business_data:
            name = business.get('name', '') or ''
            website = business.get('website', '') or ''
            emails = business.get('emails', []) if business.get('emails') else []
            phones = ', '.join(business.get('phones', [])) if business.get('phones') else ''
            facebook = business.get('facebook', '')
            twitter = business.get('twitter', '')
            instagram = business.get('instagram', '')
            linkedin = business.get('linkedin', '')
            whatsapp = business.get('whatsapp', '')
            youtube = business.get('youtube', '')
            city = business.get('city', '')
            product = business.get('product', '')
            
            # 创建 name+website 组合键
            combination_key = (name, website)
            
            # 检查本批次内是否已有相同组合
            if combination_key in seen_combinations:
                result['skipped_count'] += 1
                continue
            seen_combinations.add(combination_key)
            
            # 检查数据库中是否存在重复
            existing = check_duplicate_exists(name, website)
            
            if existing:
                # 更新现有记录
                email_value = emails[0] if emails else None
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
                result['updated_count'] += 1
            else:
                # 插入新记录
                unique_id = generate_unique_id()
                email_value = emails[0] if emails else None
                
                cursor.execute("""
                    INSERT INTO business_records 
                    (unique_id, name, website, email, phones, facebook, twitter, 
                     instagram, linkedin, whatsapp, youtube, city, product, send_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                """, (unique_id, name, website, email_value, phones, facebook, 
                      twitter, instagram, linkedin, whatsapp, youtube, city, product))
                result['inserted_count'] += 1

        connection.commit()
        print(f"Successfully processed {len(business_data)} records: "
              f"{result['inserted_count']} inserted, {result['updated_count']} updated, "
              f"{result['skipped_count']} skipped", file=sys.stderr)

    except Error as e:
        if connection:
            connection.rollback()
        result['success'] = False
        result['errors'].append(str(e))
        print(f"Failed to save business data: {e}", file=sys.stderr)
    finally:
        if cursor:
            cursor.close()
        release_connection(connection)
    
    return result


def save_business_data_batch(business_data_list):
    """
    批量保存商家数据到数据库，基于 name+website 唯一性判断
    
    Features:
    - 基于 name + website 的唯一性判断 (Requirements 1.1, 1.2, 1.3)
    - 使用事务批量处理 (Requirements 4.2)
    - 自动生成 unique_id (Requirements 2.1)
    - 支持 city 字段 (Requirements 9.3)
    
    Returns:
        dict: 包含 success, inserted_count, skipped_count, errors 的结果
    """
    if not business_data_list:
        return {'success': True, 'inserted_count': 0, 'skipped_count': 0, 'updated_count': 0, 'errors': []}
    
    connection = None
    cursor = None
    result = {
        'success': True,
        'inserted_count': 0,
        'skipped_count': 0,
        'updated_count': 0,
        'errors': []
    }
    
    try:
        connection = get_db_connection()
        connection.execute("BEGIN TRANSACTION")
        cursor = connection.cursor()
        
        # 用于跟踪本批次中的 name+website 组合
        seen_combinations = set()
        
        for business_data in business_data_list:
            name = business_data.get('name', '') or ''
            website = business_data.get('website', '') or ''
            emails = business_data.get('emails', []) if business_data.get('emails') else []
            phones = ','.join(business_data.get('phones', [])) if business_data.get('phones') else ''
            facebook = business_data.get('facebook', '')
            twitter = business_data.get('twitter', '')
            instagram = business_data.get('instagram', '')
            linkedin = business_data.get('linkedin', '')
            whatsapp = business_data.get('whatsapp', '')
            youtube = business_data.get('youtube', '')
            city = business_data.get('city', '')
            product = business_data.get('product', '')
            
            # 创建 name+website 组合键
            combination_key = (name, website)
            
            # 检查本批次内是否已有相同组合
            if combination_key in seen_combinations:
                result['skipped_count'] += 1
                continue
            seen_combinations.add(combination_key)
            
            # 检查数据库中是否存在重复
            existing = check_duplicate_exists(name, website)
            
            if existing:
                # 更新现有记录
                email_value = emails[0] if emails else None
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
                result['updated_count'] += 1
            else:
                # 插入新记录
                unique_id = generate_unique_id()
                email_value = emails[0] if emails else None
                
                cursor.execute("""
                    INSERT INTO business_records 
                    (unique_id, name, website, email, phones, facebook, twitter, 
                     instagram, linkedin, whatsapp, youtube, city, product, send_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                """, (unique_id, name, website, email_value, phones, facebook, 
                      twitter, instagram, linkedin, whatsapp, youtube, city, product))
                result['inserted_count'] += 1
        
        connection.commit()
        print(f"Successfully processed {len(business_data_list)} records in batch: "
              f"{result['inserted_count']} inserted, {result['updated_count']} updated, "
              f"{result['skipped_count']} skipped", file=sys.stderr)
    except Error as e:
        if connection:
            connection.rollback()
        result['success'] = False
        result['errors'].append(str(e))
        print(f"Failed to save business data in batch: {e}", file=sys.stderr)
    finally:
        if cursor:
            cursor.close()
        release_connection(connection)
    
    return result


def get_history_records(page, size, query='', show_empty_email=False, city_filter=None):
    """
    Query history records with search, pagination, and optional filtering
    
    Features:
    - 支持 city 字段查询 (Requirements 9.3)
    - 分页查询优化
    """
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        offset = (page - 1) * size

        # Base SQL query with unique_id, city and product fields
        sql = """
            SELECT id, unique_id, name, website, email, phones, facebook, twitter, instagram, 
                   linkedin, whatsapp, youtube, city, product, send_count, updated_at, created_at
            FROM business_records
            WHERE 1=1
        """
        count_sql = """
            SELECT COUNT(*) as total
            FROM business_records
            WHERE 1=1
        """
        params = []
        count_params = []

        # Add email filter condition
        if not show_empty_email:
            sql += " AND (email IS NOT NULL AND email != '')"
            count_sql += " AND (email IS NOT NULL AND email != '')"

        # Add search condition
        if query:
            sql += " AND (name LIKE ? OR email LIKE ? OR city LIKE ? OR product LIKE ?)"
            count_sql += " AND (name LIKE ? OR email LIKE ? OR city LIKE ? OR product LIKE ?)"
            query_param = f"%{query}%"
            params.extend([query_param, query_param, query_param, query_param])
            count_params.extend([query_param, query_param, query_param, query_param])

        # Add city filter
        if city_filter:
            sql += " AND city = ?"
            count_sql += " AND city = ?"
            params.append(city_filter)
            count_params.append(city_filter)

        # Add sorting and pagination
        sql += " ORDER BY updated_at DESC LIMIT ? OFFSET ?"
        params.extend([size, offset])

        # Execute query
        cursor.execute(sql, params)
        columns = [desc[0] for desc in cursor.description]
        records = [dict(zip(columns, row)) for row in cursor.fetchall()]

        # Query total count
        cursor.execute(count_sql, count_params)
        total = cursor.fetchone()[0]

        return records, total

    except Exception as e:
        print(f"Failed to query history records: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return [], 0

    finally:
        if cursor:
            try:
                cursor.close()
            except Exception:
                pass
        release_connection(connection)


def update_send_count(emails):
    """Update send count for specified emails"""
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        for email in emails:
            cursor.execute("""
                UPDATE business_records 
                SET send_count = send_count + 1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE email = ?
            """, (email,))

        connection.commit()
        print(f"Successfully updated send count for {len(emails)} emails", file=sys.stderr)

    except Error as e:
        print(f"Failed to update send count: {e}", file=sys.stderr)
        raise
    finally:
        if cursor:
            cursor.close()
        release_connection(connection)


def get_last_position(url):
    """Get last extraction position for a given URL"""
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("SELECT last_position FROM last_extraction_positions WHERE url = ?", (url,))
        result = cursor.fetchone()
        return result[0] if result else None
    finally:
        if cursor:
            cursor.close()
        release_connection(connection)


def save_last_position(url, last_position):
    """Save last extraction position for a given URL"""
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO last_extraction_positions (url, last_position)
            VALUES (?, ?)
        """, (url, last_position))

        connection.commit()
    finally:
        if cursor:
            cursor.close()
        release_connection(connection)


def get_facebook_non_email():
    """Get records with Facebook but no email"""
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("SELECT id, facebook FROM business_records WHERE facebook IS NOT NULL AND email IS NULL")
        result = cursor.fetchall()
        return result
    finally:
        if cursor:
            cursor.close()
        release_connection(connection)


def update_business_email(business_id, email):
    """Update email for a specific business record by ID"""
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("UPDATE business_records SET email = ? WHERE id = ?", (email, business_id))
        connection.commit()
        return True
    except sqlite3.Error as err:
        print(f"Failed to update email in database: {err}")
        if "UNIQUE constraint failed" in str(err):
            print(f"Duplicate email detected for record {business_id}, keeping existing record")
        return False
    finally:
        if cursor:
            cursor.close()
        release_connection(connection)


def delete_business_email(business_id):
    """Delete a business record by ID"""
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("DELETE FROM business_records WHERE id = ?", (business_id,))
        connection.commit()
        return True
    except sqlite3.Error as err:
        print(f"Failed to delete database record: {err}")
        return False
    finally:
        if cursor:
            cursor.close()
        release_connection(connection)


# ============================================================================
# AI 配置相关函数 (Requirements 12.6)
# ============================================================================

def get_ai_config():
    """获取 AI 配置"""
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        cursor.execute("""
            SELECT id, provider, api_key_encrypted, model_name, temperature, 
                   max_tokens, is_active, updated_at, created_at
            FROM ai_configurations
            WHERE is_active = 1
            ORDER BY updated_at DESC
            LIMIT 1
        """)
        
        row = cursor.fetchone()
        if row:
            columns = ['id', 'provider', 'api_key_encrypted', 'model_name', 
                      'temperature', 'max_tokens', 'is_active', 'updated_at', 'created_at']
            return dict(zip(columns, row))
        return None
    finally:
        if cursor:
            cursor.close()
        release_connection(connection)


def save_ai_config(config):
    """保存 AI 配置"""
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO ai_configurations 
            (provider, api_key_encrypted, model_name, temperature, max_tokens, is_active)
            VALUES (?, ?, ?, ?, ?, 1)
        """, (
            config.get('provider', 'gemini'),
            config.get('api_key_encrypted'),
            config.get('model_name', 'gemini-1.5-flash'),
            config.get('temperature', 0.7),
            config.get('max_tokens', 1024)
        ))
        
        connection.commit()
        return True
    except Error as e:
        print(f"保存 AI 配置失败: {e}", file=sys.stderr)
        return False
    finally:
        if cursor:
            cursor.close()
        release_connection(connection)


# ============================================================================
# 国家城市映射相关函数 (Requirements 10.3)
# ============================================================================

def get_countries():
    """获取所有国家列表"""
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        cursor.execute("""
            SELECT DISTINCT country_code, country_name
            FROM country_city_mappings
            WHERE is_active = 1
            ORDER BY country_name
        """)
        
        return [{'code': row[0], 'name': row[1]} for row in cursor.fetchall()]
    finally:
        if cursor:
            cursor.close()
        release_connection(connection)


def get_cities_by_country(country_code):
    """根据国家代码获取城市列表"""
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        cursor.execute("""
            SELECT city_name
            FROM country_city_mappings
            WHERE country_code = ? AND is_active = 1
            ORDER BY city_name
        """, (country_code,))
        
        return [row[0] for row in cursor.fetchall()]
    finally:
        if cursor:
            cursor.close()
        release_connection(connection)


def add_country_city_mapping(country_code, country_name, city_name):
    """添加国家城市映射"""
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        cursor.execute("""
            INSERT OR IGNORE INTO country_city_mappings 
            (country_code, country_name, city_name)
            VALUES (?, ?, ?)
        """, (country_code, country_name, city_name))
        
        connection.commit()
        return True
    except Error as e:
        print(f"添加国家城市映射失败: {e}", file=sys.stderr)
        return False
    finally:
        if cursor:
            cursor.close()
        release_connection(connection)


if __name__ == "__main__":
    # 示例代码 - 请根据需要修改参数
    # records, total = get_history_records(1, 10, "example")
    # print(f"Records: {records}")
    # print(f"Total: {total}")
    pass