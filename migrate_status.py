import mysql.connector
import json
import base64

# Load database configuration
with open('config.json', 'r', encoding='utf-8') as f:
    config = json.load(f)

db_username = base64.b64decode(config.get("db_username", "")).decode("utf-8")
db_password = base64.b64decode(config.get("db_password", "")).decode("utf-8")
db_host = config.get("db_host", "localhost")

def migrate_status():
    try:
        print("Connecting to database...")
        conn = mysql.connector.connect(
            host=db_host,
            user=db_username,
            password=db_password,
            database="attendance_db"
        )
        cursor = conn.cursor()
        
        print("Updating status values...")
        # Update ❌ to Absent
        cursor.execute("""
            UPDATE students 
            SET DiemDanhStatus = 'Absent' 
            WHERE DiemDanhStatus = '❌'
        """)
        print(f"Updated {cursor.rowcount} records from ❌ to Absent")
        
        # Update ✓ to Present
        cursor.execute("""
            UPDATE students 
            SET DiemDanhStatus = 'Present' 
            WHERE DiemDanhStatus = '✓'
        """)
        print(f"Updated {cursor.rowcount} records from ✓ to Present")
        
        conn.commit()
        print("Migration completed successfully")
        
    except Exception as e:
        print(f"Error during migration: {str(e)}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

if __name__ == "__main__":
    migrate_status() 