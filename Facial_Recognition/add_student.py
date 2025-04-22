import cv2
import os
import base64
import json
from DatabaseHooking import connect_db, add_student
from datetime import datetime

def capture_student_image(student_name):
    # Create student_images directory if it doesn't exist
    if not os.path.exists('student_images'):
        os.makedirs('student_images')
    
    # Initialize camera
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Không thể mở camera!")
        return None
    
    print("Nhấn SPACE để chụp ảnh, ESC để hủy")
    
    while True:
        ret, frame = cap.read()
        if not ret:
            print("Không thể đọc frame từ camera")
            break
            
        cv2.imshow('Chụp ảnh sinh viên', frame)
        
        key = cv2.waitKey(1) & 0xFF
        if key == 27:  # ESC
            print("Đã hủy chụp ảnh")
            break
        elif key == 32:  # SPACE
            # Save image
            image_path = f'student_images/{student_name}.jpg'
            cv2.imwrite(image_path, frame)
            print(f"Đã lưu ảnh tại: {image_path}")
            break
    
    cap.release()
    cv2.destroyAllWindows()
    return image_path if os.path.exists(f'student_images/{student_name}.jpg') else None

def add_new_student():
    # Load database configuration
    with open("config.json", "r", encoding="utf-8") as f:
        config = json.load(f)
    
    db_username = base64.b64decode(config.get("db_username", "")).decode("utf-8")
    db_password = base64.b64decode(config.get("db_password", "")).decode("utf-8")
    db_host = config.get("db_host", "localhost")
    
    # Connect to database
    cnx, cursor = connect_db(db_username, db_password, db_host)
    if not cnx or not cursor:
        print("Không thể kết nối đến cơ sở dữ liệu!")
        return
    
    try:
        # Get student information
        print("\n=== Thêm sinh viên mới ===")
        student_name = input("Nhập họ tên sinh viên: ")
        student_id = input("Nhập mã sinh viên: ")
        birth_date = input("Nhập ngày sinh (YYYY-MM-DD): ")
        class_name = input("Nhập lớp: ")
        gender = input("Nhập giới tính (Nam/Nữ): ")
        
        # Capture student image
        print("\nChuẩn bị chụp ảnh sinh viên...")
        image_path = capture_student_image(student_name)
        
        if not image_path:
            print("Không thể chụp ảnh sinh viên!")
            return
        
        # Add student to database
        add_student(cursor, cnx, 
                   UID=student_id,
                   HoVaTen=student_name,
                   NgaySinh=birth_date,
                   Lop=class_name,
                   Gender=gender,
                   ImagePath=image_path)
        
        print(f"\nĐã thêm sinh viên {student_name} thành công!")
        
    except Exception as e:
        print(f"Lỗi: {str(e)}")
    finally:
        cursor.close()
        cnx.close()

if __name__ == "__main__":
    add_new_student() 