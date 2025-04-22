import mysql.connector
import json
import base64

# Load database configuration
with open('config.json', 'r', encoding='utf-8') as f:
    config = json.load(f)

db_username = base64.b64decode(config.get("db_username", "")).decode("utf-8")
db_password = base64.b64decode(config.get("db_password", "")).decode("utf-8")
db_host = config.get("db_host", "localhost")

def get_db_connection():
    try:
        conn = mysql.connector.connect(
            host=db_host,
            user=db_username,
            password=db_password,
            database="attendance_db"
        )
        return conn
    except mysql.connector.Error as err:
        print(f"Database connection error: {err}")
        return None

def check_attendance():
    conn = get_db_connection()
    if not conn:
        print("Failed to connect to database")
        return

    cursor = conn.cursor(dictionary=True)
    
    try:
        # Query 1: Basic attendance status
        print("\n=== Basic Attendance Status ===")
        cursor.execute("""
            SELECT 
                HoVaTen, 
                DiemDanhStatus, 
                DATE_FORMAT(CONVERT_TZ(ThoiGianDiemDanh, '+00:00', '+07:00'), '%Y-%m-%d %H:%i:%s') as attendance_time
            FROM students 
            ORDER BY ThoiGianDiemDanh DESC
        """)
        for row in cursor.fetchall():
            print(f"Name: {row['HoVaTen']}")
            print(f"Status: {row['DiemDanhStatus']}")
            print(f"Time: {row['attendance_time']}")
            print("-" * 50)

        # Query 2: Attendance count by status
        print("\n=== Attendance Count by Status ===")
        cursor.execute("""
            SELECT 
                DiemDanhStatus,
                COUNT(*) as student_count
            FROM students
            GROUP BY DiemDanhStatus
        """)
        for row in cursor.fetchall():
            print(f"Status: {row['DiemDanhStatus']} - Count: {row['student_count']}")

        # Query 3: Absent students
        print("\n=== Absent Students ===")
        cursor.execute("""
            SELECT HoVaTen, Lop 
            FROM students 
            WHERE DiemDanhStatus = 'Absent'
        """)
        absent_students = cursor.fetchall()
        if absent_students:
            for student in absent_students:
                print(f"Name: {student['HoVaTen']} - Class: {student['Lop']}")
        else:
            print("No absent students")

    except mysql.connector.Error as err:
        print(f"Error executing query: {err}")
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    check_attendance() 