"""
用户数据访问层
"""
import sys
from typing import Optional
from sqlite3 import Error

from db import get_db_connection, release_connection
from models.user import User


class UserRepository:
    """用户数据访问层"""
    
    USER_COLUMNS = ['id', 'username', 'password_hash', 'created_at', 'updated_at']
    
    def create_user(self, username: str, password_hash: str) -> Optional[int]:
        """
        创建新用户
        
        Args:
            username: 用户名
            password_hash: 加密后的密码
            
        Returns:
            int: 新创建用户的 ID，失败返回 None
        """
        connection = None
        cursor = None
        try:
            connection = get_db_connection()
            if not connection:
                return None
            
            cursor = connection.cursor()
            cursor.execute("""
                INSERT INTO users (username, password_hash)
                VALUES (?, ?)
            """, (username, password_hash))
            
            connection.commit()
            user_id = cursor.lastrowid
            print(f"[DB] 创建用户成功: {username}, ID={user_id}", file=sys.stderr)
            return user_id
            
        except Error as e:
            print(f"[DB ERROR] 创建用户失败: {e}", file=sys.stderr)
            if connection:
                connection.rollback()
            return None
        finally:
            if cursor:
                cursor.close()
            release_connection(connection)
    
    def get_user_by_username(self, username: str) -> Optional[User]:
        """
        根据用户名查询用户
        
        Args:
            username: 用户名
            
        Returns:
            User: 用户对象，不存在返回 None
        """
        connection = None
        cursor = None
        try:
            connection = get_db_connection()
            if not connection:
                return None
            
            cursor = connection.cursor()
            cursor.execute("""
                SELECT id, username, password_hash, created_at, updated_at
                FROM users
                WHERE username = ?
            """, (username,))
            
            row = cursor.fetchone()
            if row:
                return User.from_db_row(row, self.USER_COLUMNS)
            return None
            
        except Error as e:
            print(f"[DB ERROR] 查询用户失败: {e}", file=sys.stderr)
            return None
        finally:
            if cursor:
                cursor.close()
            release_connection(connection)
    
    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """
        根据 ID 查询用户
        
        Args:
            user_id: 用户 ID
            
        Returns:
            User: 用户对象，不存在返回 None
        """
        connection = None
        cursor = None
        try:
            connection = get_db_connection()
            if not connection:
                return None
            
            cursor = connection.cursor()
            cursor.execute("""
                SELECT id, username, password_hash, created_at, updated_at
                FROM users
                WHERE id = ?
            """, (user_id,))
            
            row = cursor.fetchone()
            if row:
                return User.from_db_row(row, self.USER_COLUMNS)
            return None
            
        except Error as e:
            print(f"[DB ERROR] 查询用户失败: {e}", file=sys.stderr)
            return None
        finally:
            if cursor:
                cursor.close()
            release_connection(connection)
    
    def username_exists(self, username: str) -> bool:
        """
        检查用户名是否已存在
        
        Args:
            username: 用户名
            
        Returns:
            bool: 用户名是否存在
        """
        connection = None
        cursor = None
        try:
            connection = get_db_connection()
            if not connection:
                return False
            
            cursor = connection.cursor()
            cursor.execute("""
                SELECT 1 FROM users WHERE username = ? LIMIT 1
            """, (username,))
            
            return cursor.fetchone() is not None
            
        except Error as e:
            print(f"[DB ERROR] 检查用户名失败: {e}", file=sys.stderr)
            return False
        finally:
            if cursor:
                cursor.close()
            release_connection(connection)
