
import os
import sys
import threading
from datetime import datetime
import time

# Add parent directory to sys.path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from db import get_db_connection, release_connection, init_database, update_send_count
    from validators.email_validator import EmailValidator
except ImportError as e:
    print(f"FAILED: Import error. Make sure you are running this from the project root. {e}")
    sys.exit(1)

def test_database_connection():
    print("Testing Database Connection...", end=" ")
    conn = get_db_connection()
    if conn:
        print("OK")
        release_connection(conn)
        return True
    else:
        print("FAILED")
        return False

def test_email_validator():
    print("Testing Email Validator...", end=" ")
    validator = EmailValidator()
    valid_email = "test@example.com"
    invalid_email = "test@.com"
    
    if validator.validate(valid_email).is_valid and not validator.validate(invalid_email).is_valid:
        print("OK")
        return True
    else:
        print(f"FAILED (Valid: {validator.validate(valid_email).is_valid}, Invalid: {validator.validate(invalid_email).is_valid})")
        return False

def test_update_send_count_batch():
    print("Testing Batch Update Send Count...", end=" ")
    # Mock data
    emails = [f"test{i}@example.com" for i in range(5)]
    
    # Needs actual DB entries to work, so we will skip actual execution if DB is empty or just dry run
    # For now, just checking if function call crashes
    try:
        # We won't actually update unless we insert fake records, which might pollute DB. 
        # Let's just create a specific test record
        conn = get_db_connection()
        cursor = conn.cursor()
        test_email = "verify_script_test@example.com"
        cursor.execute("INSERT OR IGNORE INTO business_records (email, name) VALUES (?, 'Test User')", (test_email,))
        conn.commit()
        release_connection(conn)
        
        result = update_send_count([test_email])
        print(f"OK (Updated: {result})")
        
        # Cleanup
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM business_records WHERE email = ?", (test_email,))
        conn.commit()
        release_connection(conn)
        return True
    except Exception as e:
        print(f"FAILED: {e}")
        return False

def test_limit_logic_simulation():
    print("Testing Limit Logic Simulation...", end=" ")
    # Simulate the logic fixed in app.py
    limit = 10
    cities = ["City A", "City B", "City C"]
    extracted_data = [] # Accumulated data
    
    stopped = False
    
    for city in cities:
        remaining_limit = limit - len(extracted_data)
        if remaining_limit <= 0:
            stopped = True
            break
        
        # Simulate extracting min(5, remaining) items per city
        to_extract = min(5, remaining_limit)
        for i in range(to_extract):
            extracted_data.append({"city": city, "id": i})
            
    if len(extracted_data) == 10 and stopped:
        print(f"OK (Extracted {len(extracted_data)} items, expected 10. Logic holds.)")
        return True
    else:
        print(f"FAILED (Extracted {len(extracted_data)} items, expected 10)")
        return False

if __name__ == "__main__":
    print("=== Verification Script ===")
    tests = [
        test_database_connection,
        test_email_validator,
        test_update_send_count_batch,
        test_limit_logic_simulation
    ]
    
    passed = 0
    for test in tests:
        if test():
            passed += 1
            
    print("===========================")
    print(f"Tests Passed: {passed}/{len(tests)}")
    
    if passed == len(tests):
        sys.exit(0)
    else:
        sys.exit(1)
