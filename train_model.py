import os
import sys
import face_recognition
import numpy as np
import pickle
from sklearn import neighbors
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
        print("Database connection successful")
        return conn
    except mysql.connector.Error as err:
        print(f"Database connection error: {err}")
        return None

def train_from_db():
    # Get student data from database
    conn = get_db_connection()
    if conn is None:
        print("Failed to connect to database")
        return False
        
    cursor = conn.cursor()
    cursor.execute('SELECT HoVaTen, ImagePath FROM Students')
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

if __name__ == "__main__":
    print("Starting model training...")
    success = train_from_db()
    if success:
        print("Model training completed successfully")
    else:
        print("Model training failed") 