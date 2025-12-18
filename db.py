import sqlite3
from sqlite3 import Error
import sys

# SQLite database file path (replace with your desired path or use ':memory:' for in-memory database)
DB_FILE = "business.db"


def get_db_connection():
    """Create and return SQLite database connection"""
    try:
        connection = sqlite3.connect(DB_FILE)
        return connection
    except Error as e:
        print(f"Error connecting to database: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return None


def save_business_data_to_db(business_data):
    """Save business data to SQLite database, splitting multiple emails into multiple rows, updating on duplicate email"""
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        # 优化：使用事务批量处理
        connection.execute("BEGIN TRANSACTION")
        cursor = connection.cursor()

        # Ensure table exists with unique constraint on email
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS business_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                website TEXT,
                email TEXT UNIQUE,
                phones TEXT,
                facebook TEXT,
                twitter TEXT,
                instagram TEXT,
                linkedin TEXT,
                whatsapp TEXT,
                youtube TEXT,
                send_count INTEGER DEFAULT 0,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 优化：预处理所有数据，减少循环内的操作
        insert_data = []
        update_data = []
        email_set = set()
        
        for business in business_data:
            name = business.get('name', '')
            website = business.get('website', '')
            emails = business.get('emails', []) if business.get('emails') else []
            phones = ', '.join(business.get('phones', [])) if business.get('phones') else ''
            facebook = business.get('facebook', '')
            twitter = business.get('twitter', '')
            instagram = business.get('instagram', '')
            linkedin = business.get('linkedin', '')
            whatsapp = business.get('whatsapp', '')
            youtube = business.get('youtube', '')

            if not emails:
                # No email, insert directly
                insert_data.append((name, website, None, phones, facebook, twitter, instagram, linkedin, whatsapp, youtube, 0))
            else:
                for email in emails:
                    if email in email_set:
                        continue  # 跳过重复的email
                    email_set.add(email)
                    insert_data.append((name, website, email, phones, facebook, twitter, instagram, linkedin, whatsapp, youtube, 0))

        if insert_data:
            # 优化：使用批量插入，减少数据库操作次数
            cursor.executemany("""
                INSERT OR REPLACE INTO business_records 
                (name, website, email, phones, facebook, twitter, instagram, linkedin, whatsapp, youtube, send_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, insert_data)

        connection.commit()
        print(f"Successfully saved {len(business_data)} business records to database", file=sys.stderr)

    except Error as e:
        connection.rollback()
        print(f"Failed to save business data to database: {e}", file=sys.stderr)
        raise
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def save_business_data_batch(business_data_list):
    """批量保存商家数据到数据库，优化性能"""
    if not business_data_list:
        return
    
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        connection.execute("BEGIN TRANSACTION")
        cursor = connection.cursor()
        
        # 优化：使用单个批量插入语句
        insert_values = []
        email_set = set()
        
        for business_data in business_data_list:
            name = business_data.get('name', '')
            website = business_data.get('website', '')
            emails = business_data.get('emails', []) if business_data.get('emails') else []
            phones = ','.join(business_data.get('phones', [])) if business_data.get('phones') else ''
            facebook = business_data.get('facebook', '')
            twitter = business_data.get('twitter', '')
            instagram = business_data.get('instagram', '')
            linkedin = business_data.get('linkedin', '')
            whatsapp = business_data.get('whatsapp', '')
            youtube = business_data.get('youtube', '')
            
            if emails:
                for email in emails:
                    if email in email_set:
                        continue
                    email_set.add(email)
                    insert_values.append((name, website, email, phones, facebook, twitter, instagram, linkedin, whatsapp, youtube, 0))
            else:
                # 没有邮箱的情况，使用None占位
                insert_values.append((name, website, None, phones, facebook, twitter, instagram, linkedin, whatsapp, youtube, 0))
        
        if insert_values:
            cursor.executemany("""
                INSERT OR REPLACE INTO business_records 
                (name, website, email, phones, facebook, twitter, instagram, linkedin, whatsapp, youtube, send_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, insert_values)
        
        connection.commit()
        print(f"Successfully saved {len(business_data_list)} business records in batch", file=sys.stderr)
    except Error as e:
        connection.rollback()
        print(f"Failed to save business data in batch: {e}", file=sys.stderr)
        raise
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def get_history_records(page, size, query='', show_empty_email=False):
    """Query history records with search, pagination, and optional email filtering"""
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        # SQLite does not support dictionary cursor directly, so we fetch as list and convert
        offset = (page - 1) * size

        # Base SQL query
        sql = """
            SELECT id, name, website, email, phones, facebook, twitter, instagram, linkedin, whatsapp, youtube, send_count, updated_at, created_at
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
            sql += " AND (name LIKE ? OR email LIKE ?)"
            count_sql += " AND (name LIKE ? OR email LIKE ?)"
            query_param = f"%{query}%"
            params.extend([query_param, query_param])
            count_params.extend([query_param, query_param])

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
            except Exception as e:
                print(f"Failed to close cursor: {e}", file=sys.stderr)
                import traceback
                traceback.print_exc(file=sys.stderr)
        if connection:
            try:
                connection.close()
            except Exception as e:
                print(f"Failed to close connection: {e}", file=sys.stderr)
                import traceback
                traceback.print_exc(file=sys.stderr)


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
        if connection:
            connection.close()


def get_last_position(url):
    """Get last extraction position for a given URL"""
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        # Ensure table exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS last_extraction_positions (
                url TEXT PRIMARY KEY,
                last_position INTEGER,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("SELECT last_position FROM last_extraction_positions WHERE url = ?", (url,))
        result = cursor.fetchone()
        return result[0] if result else None
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


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
        if connection:
            connection.close()


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
        if connection:
            connection.close()


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
            delete_business_email(business_id)
            print(f"Duplicate email, deleted record: {business_id}")
        return False
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


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
        if connection:
            connection.close()


if __name__ == "__main__":
    # Test code
    records, total = get_history_records(1, 10, "example")
    print(f"Records: {records}")
    print(f"Total: {total}")