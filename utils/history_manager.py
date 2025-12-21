"""
HistoryManager - 历史数据管理模块
实现分页查询、记录创建、更新、删除和数据验证
"""
import os
import sys
import sqlite3
from typing import List, Tuple, Optional, Dict, Any

sys.path.insert(0, '.')
from validators.email_validator import EmailValidator
from validators.phone_validator import PhoneValidator
from validators.url_validator import URLValidator


class HistoryManager:
    """
    历史数据管理模块
    
    Features:
    - 分页查询
    - 记录创建
    - 记录更新
    - 记录删除
    - 数据验证
    """
    
    DB_FILE = os.path.join(os.environ.get('DATA_DIR', 'data'), "business.db")
    
    def __init__(self, db_file: str = None):
        """
        初始化历史管理器
        
        Args:
            db_file: 数据库文件路径
        """
        self.db_file = db_file or self.DB_FILE
        self._email_validator = EmailValidator()
        self._phone_validator = PhoneValidator()
        self._url_validator = URLValidator()
    
    def _get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        return sqlite3.connect(self.db_file)
    
    def get_records(
        self, 
        page: int = 1, 
        size: int = 10, 
        query: str = '', 
        filters: dict = None
    ) -> Tuple[List[dict], int]:
        """
        获取分页记录
        
        Args:
            page: 页码（从1开始）
            size: 每页大小
            query: 搜索关键词
            filters: 过滤条件
            
        Returns:
            Tuple[List[dict], int]: (记录列表, 总数)
        """
        connection = None
        cursor = None
        try:
            connection = self._get_connection()
            cursor = connection.cursor()
            
            offset = (page - 1) * size
            filters = filters or {}
            
            # 构建SQL - 包含 product 字段
            sql = """
                SELECT id, name, website, email, phones, facebook, twitter, 
                       instagram, linkedin, whatsapp, youtube, city, product, send_count, 
                       updated_at, created_at
                FROM business_records
                WHERE 1=1
            """
            count_sql = "SELECT COUNT(*) FROM business_records WHERE 1=1"
            params = []
            count_params = []
            
            # 邮箱过滤
            if not filters.get('show_empty_email', False):
                sql += " AND (email IS NOT NULL AND email != '')"
                count_sql += " AND (email IS NOT NULL AND email != '')"
            
            # 搜索条件 - 包含 product 字段
            if query:
                sql += " AND (name LIKE ? OR email LIKE ? OR city LIKE ? OR product LIKE ?)"
                count_sql += " AND (name LIKE ? OR email LIKE ? OR city LIKE ? OR product LIKE ?)"
                query_param = f"%{query}%"
                params.extend([query_param, query_param, query_param, query_param])
                count_params.extend([query_param, query_param, query_param, query_param])
            
            # 城市过滤
            if filters.get('city'):
                sql += " AND city = ?"
                count_sql += " AND city = ?"
                params.append(filters['city'])
                count_params.append(filters['city'])
            
            # 排序和分页
            sql += " ORDER BY updated_at DESC LIMIT ? OFFSET ?"
            params.extend([size, offset])
            
            # 执行查询
            cursor.execute(sql, params)
            columns = [desc[0] for desc in cursor.description]
            records = [dict(zip(columns, row)) for row in cursor.fetchall()]
            
            # 查询总数
            cursor.execute(count_sql, count_params)
            total = cursor.fetchone()[0]
            
            return records, total
            
        except Exception as e:
            print(f"查询记录失败: {e}", file=sys.stderr)
            return [], 0
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()
    
    def create_record(self, data: dict) -> int:
        """
        创建新记录
        
        Args:
            data: 记录数据
            
        Returns:
            int: 新记录ID，失败返回-1
        """
        # 验证数据
        is_valid, errors = self.validate_record(data)
        if not is_valid:
            print(f"数据验证失败: {errors}", file=sys.stderr)
            return -1
        
        connection = None
        cursor = None
        try:
            connection = self._get_connection()
            cursor = connection.cursor()
            
            # 处理phones字段
            phones = data.get('phones', [])
            if isinstance(phones, list):
                phones = ', '.join(phones)
            
            cursor.execute("""
                INSERT INTO business_records 
                (name, website, email, phones, facebook, twitter, instagram, 
                 linkedin, whatsapp, youtube, city, product, send_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data.get('name', ''),
                data.get('website'),
                data.get('email'),
                phones,
                data.get('facebook'),
                data.get('twitter'),
                data.get('instagram'),
                data.get('linkedin'),
                data.get('whatsapp'),
                data.get('youtube'),
                data.get('city'),
                data.get('product'),
                data.get('send_count', 0)
            ))
            
            connection.commit()
            return cursor.lastrowid
            
        except Exception as e:
            print(f"创建记录失败: {e}", file=sys.stderr)
            return -1
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()
    
    def update_record(self, record_id: int, data: dict) -> bool:
        """
        更新记录
        
        Args:
            record_id: 记录ID
            data: 更新数据
            
        Returns:
            bool: 是否成功
        """
        # 验证数据
        is_valid, errors = self.validate_record(data, is_update=True)
        if not is_valid:
            print(f"数据验证失败: {errors}", file=sys.stderr)
            return False
        
        connection = None
        cursor = None
        try:
            connection = self._get_connection()
            cursor = connection.cursor()
            
            # 处理phones字段
            phones = data.get('phones', [])
            if isinstance(phones, list):
                phones = ', '.join(phones)
            
            cursor.execute("""
                UPDATE business_records 
                SET name = ?, website = ?, email = ?, phones = ?, 
                    facebook = ?, twitter = ?, instagram = ?, linkedin = ?,
                    whatsapp = ?, youtube = ?, city = ?, product = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (
                data.get('name', ''),
                data.get('website'),
                data.get('email'),
                phones,
                data.get('facebook'),
                data.get('twitter'),
                data.get('instagram'),
                data.get('linkedin'),
                data.get('whatsapp'),
                data.get('youtube'),
                data.get('city'),
                data.get('product'),
                record_id
            ))
            
            connection.commit()
            return cursor.rowcount > 0
            
        except Exception as e:
            print(f"更新记录失败: {e}", file=sys.stderr)
            return False
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()
    
    def delete_record(self, record_id: int) -> bool:
        """
        删除记录
        
        Args:
            record_id: 记录ID
            
        Returns:
            bool: 是否成功
        """
        connection = None
        cursor = None
        try:
            connection = self._get_connection()
            cursor = connection.cursor()
            
            cursor.execute("DELETE FROM business_records WHERE id = ?", (record_id,))
            connection.commit()
            
            return cursor.rowcount > 0
            
        except Exception as e:
            print(f"删除记录失败: {e}", file=sys.stderr)
            return False
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()
    
    def get_record_by_id(self, record_id: int) -> Optional[dict]:
        """
        根据ID获取记录
        
        Args:
            record_id: 记录ID
            
        Returns:
            Optional[dict]: 记录数据
        """
        connection = None
        cursor = None
        try:
            connection = self._get_connection()
            cursor = connection.cursor()
            
            cursor.execute("""
                SELECT id, name, website, email, phones, facebook, twitter, 
                       instagram, linkedin, whatsapp, youtube, city, product, send_count, 
                       updated_at, created_at
                FROM business_records
                WHERE id = ?
            """, (record_id,))
            
            row = cursor.fetchone()
            if row:
                columns = [desc[0] for desc in cursor.description]
                return dict(zip(columns, row))
            return None
            
        except Exception as e:
            print(f"获取记录失败: {e}", file=sys.stderr)
            return None
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()
    
    def validate_record(
        self, 
        data: dict, 
        is_update: bool = False
    ) -> Tuple[bool, List[str]]:
        """
        验证记录数据
        
        Args:
            data: 记录数据
            is_update: 是否为更新操作
            
        Returns:
            Tuple[bool, List[str]]: (是否有效, 错误列表)
        """
        errors = []
        
        # 验证必填字段
        if not is_update and not data.get('name'):
            errors.append('商家名称不能为空')
        
        # 验证邮箱格式
        email = data.get('email')
        if email:
            result = self._email_validator.validate(email)
            if not result.is_valid:
                errors.append(f'邮箱格式无效: {result.reason}')
        
        # 验证网站格式
        website = data.get('website')
        if website and not self._url_validator.validate(website):
            errors.append('网站URL格式无效')
        
        # 验证电话号码
        phones = data.get('phones', [])
        if phones is None:
            phones = []
        if isinstance(phones, str):
            phones = [p.strip() for p in phones.split(',') if p.strip()]
        for phone in phones:
            if phone and not self._phone_validator.validate(phone):
                errors.append(f'电话号码格式无效: {phone}')
        
        return len(errors) == 0, errors
    
    def batch_delete(self, record_ids: List[int]) -> int:
        """
        批量删除记录
        
        Args:
            record_ids: 记录ID列表
            
        Returns:
            int: 删除的记录数
        """
        if not record_ids:
            return 0
        
        connection = None
        cursor = None
        try:
            connection = self._get_connection()
            cursor = connection.cursor()
            
            placeholders = ','.join(['?' for _ in record_ids])
            cursor.execute(
                f"DELETE FROM business_records WHERE id IN ({placeholders})",
                record_ids
            )
            connection.commit()
            
            return cursor.rowcount
            
        except Exception as e:
            print(f"批量删除失败: {e}", file=sys.stderr)
            return 0
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()
