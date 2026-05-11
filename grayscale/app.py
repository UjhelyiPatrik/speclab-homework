import os
import json
import cv2
import numpy as np
import redis
from minio import Minio
import io

# reading environment variables with default values
MINIO_ENDPOINT = os.getenv('MINIO_ENDPOINT', 'localhost:30002')
MINIO_ACCESS_KEY = os.getenv('MINIO_ACCESS_KEY', 'minioadmin')
MINIO_SECRET_KEY = os.getenv('MINIO_SECRET_KEY', 'minioadmin')
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
BUCKET_NAME = 'images'

# initializing MinIO and Redis clients
minio_client = Minio(
    MINIO_ENDPOINT,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=False
)
redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)

def process_image(task_id, image_path, origin_h, origin_w):
    try:
        print(f"[INFO] Starting grayscale processing: {task_id}")
        
        # 1. Download the image from MinIO
        response = minio_client.get_object(BUCKET_NAME, image_path)
        file_data = response.read()
        response.close()
        response.release_conn()

        # 2. Convert bytes to OpenCV format
        nparr = np.frombuffer(file_data, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if image is None:
            raise ValueError("Failed to decode the image.")

        # 3. Convert image to grayscale
        gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # 4. Encode the new image to bytes
        _, buffer = cv2.imencode('.jpg', gray_image)
        gray_bytes = buffer.tobytes()
        gray_stream = io.BytesIO(gray_bytes)
        
        # 5. Upload the new image to MinIO
        gray_image_path = f"gray_{task_id}.jpg"
        minio_client.put_object(
            BUCKET_NAME,
            gray_image_path,
            data=gray_stream,
            length=len(gray_bytes)
        )
        print(f"[INFO] Grayscale image uploaded: {gray_image_path}")

        # 6. Send message to ObjectDetect Service
        message = {
            "task_id": task_id,
            "image_path": gray_image_path,
            "origin_h": origin_h,
            "origin_w": origin_w
        }
        redis_client.publish('object_detect_queue', json.dumps(message))
        print(f"[INFO] Message sent to object_detect_queue: {message}")

    except Exception as e:
        print(f"[ERROR] Error during processing ({task_id}): {e}")

def listen_to_queue():
    pubsub = redis_client.pubsub()
    pubsub.subscribe('grayscale_queue') # Listen to the grayscale_queue channel
    print("[INFO] Grayscale Service started, waiting for messages on grayscale_queue...")

    for message in pubsub.listen():
        if message['type'] == 'message':
            try:
                data = json.loads(message['data'])
                task_id = data.get('task_id')
                image_path = data.get('image_path')
                origin_h = data.get('origin_h')
                origin_w = data.get('origin_w')
                
                if task_id and image_path and origin_h and origin_w:
                    process_image(task_id, image_path, origin_h, origin_w)
                else:
                    print(f"[WARN] Invalid message format: {data}")
            except json.JSONDecodeError:
                print(f"[ERROR] Failed to decode JSON message: {message['data']}")

if __name__ == '__main__':
    listen_to_queue()