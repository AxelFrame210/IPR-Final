import cv2
import math
import pickle
import base64
import json
import os
import face_recognition
import numpy as np
from sklearn import neighbors
from DatabaseHooking import connect_db
from datetime import datetime, date
import mysql.connector

# Get the directory path of the current file
current_dir = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(current_dir, "config.json")

with open(config_path, "r", encoding="utf-8") as f:
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
        print("Database connection successful")
        return conn
    except mysql.connector.Error as err:
        print(f"Database connection error: {err}")
        return None

def train_from_db():
    # Get student data from database
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT HoVaTen, ImagePath FROM students')
    students = cursor.fetchall()
    cursor.close()
    conn.close()

    print(f"Found {len(students)} students in database")
    
    # Prepare training data
    X = []  # face encodings
    y = []  # names

    for student in students:
        name = student[0]
        image_path = student[1]
        
        print(f"Processing student: {name} with image: {image_path}")
        
        if not os.path.exists(image_path):
            print(f"Warning: Image not found for {name}: {image_path}")
            continue
            
        # Load image and find face encodings
        image = face_recognition.load_image_file(image_path)
        face_locations = face_recognition.face_locations(image, model="hog")
        
        if not face_locations:
            print(f"Warning: No face found in image for {name}")
            continue
            
        face_encoding = face_recognition.face_encodings(image, face_locations)[0]
        
        X.append(face_encoding)
        y.append(name)
        print(f"Successfully added {name} to training data")

    if not X:
        print("No valid training data found")
        return False

    print(f"Training model with {len(X)} faces")
    
    # Train the KNN classifier
    knn_clf = neighbors.KNeighborsClassifier(n_neighbors=1, algorithm='ball_tree', weights='distance')
    knn_clf.fit(X, y)

    # Save the trained model
    model_path = "trained_knn_model.clf"
    if os.path.exists(model_path):
        os.remove(model_path)
        print("Removed old model file")
        
    with open(model_path, 'wb') as f:
        pickle.dump(knn_clf, f)
        print(f"Saved new model with {len(X)} faces")

    return True

def reset_attendance_status(cursor, cnx):
    """Reset trạng thái điểm danh vào đầu mỗi ngày mới"""
    try:
        # Lấy ngày hiện tại
        today = date.today()
        
        # Kiểm tra xem đã reset cho ngày hôm nay chưa
        cursor.execute("SELECT MAX(ThoiGianDiemDanh) FROM students")
        last_reset = cursor.fetchone()[0]
        
        if last_reset is None or last_reset.date() < today:
            print(f"Đang reset trạng thái điểm danh cho ngày mới {today}...")
            
            # Update the column type if needed
            cursor.execute("""
                ALTER TABLE students 
                MODIFY COLUMN DiemDanhStatus ENUM('Absent', 'Present', 'Late') DEFAULT 'Absent'
            """)
            
            cursor.execute("""
                UPDATE students 
                SET DiemDanhStatus = 'Absent',
                    ThoiGianDiemDanh = NULL
            """)
            cnx.commit()
            print("Đã reset trạng thái điểm danh thành công!")
    except Exception as e:
        print(f"Lỗi khi reset trạng thái điểm danh: {str(e)}")

def face_loop(cnx, cursor, camera_source=0):
    cap = None
    try:
        # Reset trạng thái điểm danh trước khi bắt đầu
        reset_attendance_status(cursor, cnx)
        
        # Get cutoff time from config
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS config (
                config_key VARCHAR(50) PRIMARY KEY,
                config_value VARCHAR(255) NOT NULL
            )
        """)
        
        cursor.execute("SELECT config_value FROM config WHERE config_key = 'cutoff_time'")
        cutoff_result = cursor.fetchone()
        
        # Default cutoff time if not set
        cutoff_time = "08:30"
        gmt = "GMT+7"
        
        if cutoff_result:
            cutoff_value = cutoff_result[0]
            parts = cutoff_value.split(' ')
            if len(parts) == 2:
                gmt = parts[0]
                cutoff_time = parts[1]
        
        print(f"Đang thử mở camera với source {camera_source}...")
        
        # Try different camera backends
        backends = [cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY]
        cap = None
        
        for backend in backends:
            try:
                cap = cv2.VideoCapture(camera_source + backend)
                if cap.isOpened():
                    ret, frame = cap.read()
                    if ret and frame is not None:
                        print(f"Đã kết nối camera thành công với backend {backend}")
                        break
                    else:
                        cap.release()
            except Exception as e:
                print(f"Lỗi khi thử backend {backend}: {str(e)}")
                if cap is not None:
                    cap.release()
        
        if cap is None or not cap.isOpened():
            print("Lỗi: Không thể mở camera. Vui lòng kiểm tra:")
            print("1. Camera có được kết nối không?")
            print("2. Camera có đang được sử dụng bởi ứng dụng khác không?")
            print("3. Bạn có quyền truy cập camera không?")
            raise Exception("Không thể mở camera")
            
        # Set camera properties for better performance
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)  # Reduce resolution
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Minimize buffer size
        cap.set(cv2.CAP_PROP_FPS, 30)  # Set FPS
        cap.set(cv2.CAP_PROP_AUTOFOCUS, 1)  # Enable autofocus
        cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.75)  # Enable auto exposure
            
        print("Camera đã được khởi tạo thành công!")
        
        # Đặt tên cửa sổ và vị trí
        window_name = "Camera Điểm Danh (Nhấn ESC hoặc Q để thoát)"
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.moveWindow(window_name, 100, 100)  # Đặt vị trí cửa sổ
        cv2.setWindowProperty(window_name, cv2.WND_PROP_TOPMOST, 1)  # Giữ cửa sổ luôn trên cùng
        
        # Khởi tạo model
        knn_model_path = "trained_knn_model.clf"
        if not os.path.exists(knn_model_path):
            print("Huấn luyện model mới...")
            train_from_db()
        else:
            with open(knn_model_path, 'rb') as f:
                knn_clf = pickle.load(f)
        
        print("Đã khởi động camera. Nhấn ESC hoặc Q để thoát.")
        
        # Dictionary để theo dõi điểm danh
        attendance_buffer = {}
        attendance_threshold = 3  # Reduced from 5 to 3 for faster detection
        
        # Frame counter for processing every Nth frame
        frame_counter = 0
        process_every_n_frames = 2  # Process every 2nd frame
        
        # Keep track of last successful predictions
        last_predictions = []
        
        # Face detection confidence threshold
        face_detection_threshold = 0.5  # Reduced from 0.65 to 0.5 for better sensitivity
        
        while True:
            ret, frame = cap.read()
            if not ret:
                print("Không thể đọc frame từ camera")
                break
                
            # Process every Nth frame
            frame_counter += 1
            if frame_counter % process_every_n_frames != 0:
                continue
                
            # Create a copy of the frame for display
            display_frame = frame.copy()
            
            # Nhận diện khuôn mặt
            try:
                # Convert to RGB for face_recognition library
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                
                # Find face locations in the frame
                face_locations = face_recognition.face_locations(rgb_frame, model="hog")
                
                if not face_locations:
                    # Use last successful predictions for display
                    if last_predictions:
                        display_frame = show_labels(display_frame, last_predictions)
                    cv2.imshow(window_name, display_frame)
                    continue
                
                # Get face encodings
                face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)
                
                # Predict names for faces
                predictions = []
                for face_encoding in face_encodings:
                    # Find closest match
                    closest_distances = knn_clf.kneighbors([face_encoding], n_neighbors=1)
                    distance = closest_distances[0][0][0]
                    is_match = distance <= face_detection_threshold
                    
                    if is_match:
                        name = knn_clf.predict([face_encoding])[0]
                        # Convert numpy string to Python string
                        name_str = str(name)
                        predictions.append((name_str, face_locations[len(predictions)]))
                        print(f"Face detected: {name_str} with confidence: {1 - distance:.2%}")
                    else:
                        # Only show unknown if confidence is very low
                        if distance > face_detection_threshold * 1.2:
                            predictions.append(("unknown", face_locations[len(predictions)]))
                
                # Update last successful predictions
                if predictions:
                    last_predictions = predictions
                
                # Xử lý điểm danh
                current_names = set()
                for name, _ in predictions:
                    if name != "unknown":
                        current_names.add(name)
                        if name not in attendance_buffer:
                            attendance_buffer[name] = 1
                            print(f"Starting detection for {name} (count: 1)")
                        else:
                            attendance_buffer[name] += 1
                            print(f"Incrementing detection for {name} (count: {attendance_buffer[name]})")
                            
                        if attendance_buffer[name] >= attendance_threshold:
                            cursor.execute("SELECT DiemDanhStatus FROM students WHERE HoVaTen = %s", (name,))
                            current_status = cursor.fetchone()
                            
                            if current_status and current_status[0] == 'Absent':
                                # Get current time in Vietnam timezone
                                cursor.execute("""
                                    SELECT TIME(CONVERT_TZ(NOW(), '+00:00', 'Asia/Ho_Chi_Minh')) AS local_time
                                """)
                                local_time = cursor.fetchone()[0]
                                
                                # Check if attendance is late
                                status = 'Present'
                                if local_time and local_time > cutoff_time:
                                    status = 'Late'
                                    print(f"Student {name} is marked as LATE (arrived at {local_time}, cutoff is {cutoff_time})")
                                
                                try:
                                    cursor.execute("""
                                        UPDATE students 
                                        SET DiemDanhStatus = %s, 
                                            ThoiGianDiemDanh = NOW() 
                                        WHERE HoVaTen = %s
                                    """, (status, name))
                                    cnx.commit()
                                    cursor.execute("SELECT ThoiGianDiemDanh FROM students WHERE HoVaTen = %s", (name,))
                                    time = cursor.fetchone()[0]
                                    print(f"Đã điểm danh thành công: {name} vào lúc {time} với trạng thái {status}")
                                except Exception as e:
                                    print(f"Lỗi khi cập nhật điểm danh: {str(e)}")
                                    print(f"SQL Query: UPDATE students SET DiemDanhStatus = '{status}', ThoiGianDiemDanh = NOW() WHERE HoVaTen = '{name}'")
                
                # Giảm giá trị đếm cho những người không xuất hiện
                for name in list(attendance_buffer.keys()):
                    if name not in current_names:
                        attendance_buffer[name] = max(0, attendance_buffer[name] - 1)
                        if attendance_buffer[name] == 0:
                            del attendance_buffer[name]
                            print(f"Reset detection count for {name}")
                
                # Draw results on frame
                display_frame = show_labels(display_frame, predictions)
                cv2.imshow(window_name, display_frame)
                
                # Check for ESC key or 'q' key
                key = cv2.waitKey(1) & 0xFF
                if key == 27 or key == ord('q'):  # ESC or 'q'
                    print("Đã nhấn phím thoát. Thoát khỏi chương trình.")
                    break
                
            except Exception as e:
                print(f"Lỗi nhận diện: {str(e)}")
                # Use last successful predictions for display
                if last_predictions:
                    display_frame = show_labels(display_frame, last_predictions)
                cv2.imshow(window_name, display_frame)
                
    except Exception as e:
        print(f"Lỗi: {str(e)}")
        
    finally:
        if cap is not None:
            cap.release()
        cv2.destroyAllWindows()
        print("Đã đóng camera và kết thúc chương trình.")

def predict(frame, knn_clf=None, model_path=None, distance_threshold=0.5):
    """Nhận diện tất cả khuôn mặt trong frame"""
    if knn_clf is None and model_path is None:
        raise Exception("Phải cung cấp knn classifier.")
        
    if knn_clf is None:
        with open(model_path, 'rb') as f:
            knn_clf = pickle.load(f)
            
    # Phát hiện vị trí các khuôn mặt
    face_locations = face_recognition.face_locations(frame)
    if len(face_locations) == 0:
        return []
        
    # Tính toán encoding cho tất cả khuôn mặt
    face_encodings = face_recognition.face_encodings(frame, face_locations)
    
    # Dự đoán và tính khoảng cách cho mỗi khuôn mặt
    closest_distances = knn_clf.kneighbors(face_encodings, n_neighbors=1)
    are_matches = [closest_distances[0][i][0] <= distance_threshold for i in range(len(face_locations))]
    
    # Dự đoán tên cho mỗi khuôn mặt
    predictions = []
    for i, (pred, loc, is_match) in enumerate(zip(knn_clf.predict(face_encodings), face_locations, are_matches)):
        if is_match:
            predictions.append((pred, loc))
        else:
            predictions.append(("unknown", loc))
            
    return predictions

def show_labels(frame, predictions):
    """Hiển thị khung và tên cho mỗi khuôn mặt được nhận diện"""
    for name, (top, right, bottom, left) in predictions:
        # Vẽ khung xanh quanh khuôn mặt
        cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
        
        # Hiển thị tên phía dưới khung
        cv2.rectangle(frame, (left, bottom - 35), (right, bottom), (0, 255, 0), cv2.FILLED)
        font = cv2.FONT_HERSHEY_DUPLEX
        cv2.putText(frame, name, (left + 6, bottom - 6), font, 0.6, (255, 255, 255), 1)
        
        # Hiển thị thông tin điểm danh nếu đã nhận diện được
        if name != "unknown":
            cv2.putText(frame, "✓", (right - 30, top - 10), font, 0.6, (0, 255, 0), 2)
    
    return frame

def main(cnx=None, cursor=None, camera_source=0):
    """Hàm chính để chạy nhận diện khuôn mặt"""
    try:
        if cnx is None or cursor is None:
            cnx, cursor = connect_db(db_username, db_password, db_host)
            if cnx is None or cursor is None:
                raise Exception("Lỗi kết nối CSDL MySQL!")

        knn_model_path = "trained_knn_model.clf"
        if os.path.exists(knn_model_path):
            os.remove(knn_model_path)
            print("Đã xóa model cũ.")
        
        print("Đang train model mới từ CSDL...")
        train_from_db()
        
        face_loop(cnx, cursor, camera_source)
        return True
        
    except Exception as e:
        print(f"Lỗi trong quá trình chạy: {str(e)}")
        return False

if __name__ == "__main__":
    main()