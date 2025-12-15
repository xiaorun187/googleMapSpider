import mysql.connector
from mysql.connector import Error
import logging
import time

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('db_connection.log'),
        logging.StreamHandler()
    ]
)


DB_CONFIG = {
    'host': '118.190.206.30',
    'user': 'google_maps',
    'password': 'yun@google_maps',
    'database': 'google_maps',
    'raise_on_warnings': True,
    'port': 40594,  
    'ssl_disabled': True,
    'connect_timeout': 120
}

def test_connection(max_retries=5, retry_delay=10):
    logging.debug(f"DB_CONFIG: { {k: v if k != 'password' else '****' for k, v in DB_CONFIG.items()} }")
    for attempt in range(max_retries):
        try:
            connection = mysql.connector.connect(**DB_CONFIG)
            if connection.is_connected():
                logging.info("Successfully connected to the database!")
                db_info = connection.get_server_info()
                logging.info(f"MySQL Server version: {db_info}")
                cursor = connection.cursor()
                cursor.execute("SELECT DATABASE();")
                record = cursor.fetchone()
                logging.info(f"Connected to database: {record}")
            return
        except Error as e:
            logging.error(f"Attempt {attempt + 1}/{max_retries} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
        finally:
            if 'connection' in locals() and connection.is_connected():
                cursor.close()
                connection.close()
                logging.info("MySQL connection is closed.")
    logging.error("All retries failed.")

if __name__ == "__main__":
    test_connection()
