import os
import json
import cv2
import numpy as np
import redis
from minio import Minio
import io

# Read environment variables with defaults for local testing
MINIO_ENDPOINT = os.getenv('MINIO_ENDPOINT', 'localhost:30002')
MINIO_ACCESS_KEY = os.getenv('MINIO_ACCESS_KEY', 'minioadmin')
MINIO_SECRET_KEY = os.getenv('MINIO_SECRET_KEY', 'minioadmin')
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
BUCKET_NAME = 'images'
SCALE_PERCENT = 25

# Initialize MinIO and Redis clients
minio_client = Minio(
    MINIO_ENDPOINT,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=False
)
redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)

def process_image(task_id, original_image_path):
    try:
        print(f"[INFO] Starting processing: {task_id}")
        
        # 1. Download the original image from MinIO
        response = minio_client.get_object(BUCKET_NAME, original_image_path)
        file_data = response.read()
        response.close()
        response.release_conn()

        # 2. Convert bytes to OpenCV (numpy) format
        nparr = np.frombuffer(file_data, np.uint8)
        origin_image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if origin_image is None:
            raise ValueError("Image could not be decoded.")

        # 3. Resize the image (based on the monolithic logic)
        (origin_h, origin_w) = origin_image.shape[:2]
        width = int(origin_w * SCALE_PERCENT / 100)
        height = int(origin_h * SCALE_PERCENT / 100)
        resized_image = cv2.resize(origin_image, (width, height), interpolation=cv2.INTER_AREA)

        # 4. Encode the new image to bytes
        _, buffer = cv2.imencode('.jpg', resized_image)
        resized_bytes = buffer.tobytes()
        resized_stream = io.BytesIO(resized_bytes)
        
        # 5. Upload the new image to MinIO (with a new name based on the task_id)
        resized_image_path = f"resized_{task_id}.jpg"
        minio_client.put_object(
            BUCKET_NAME,
            resized_image_path,
            data=resized_stream,
            length=len(resized_bytes)
        )
        print(f"[INFO] Resized image uploaded: {resized_image_path}")

        # 6. Send message to Grayscale Service with the new image path and original dimensions
        message = {
            "task_id": task_id,
            "image_path": resized_image_path,
            "origin_h": origin_h,  # The original height and width are needed for the Tag service later
            "origin_w": origin_w
        }
        redis_client.publish('grayscale_queue', json.dumps(message))
        print(f"[INFO] Message sent to grayscale_queue: {message}")

    except Exception as e:
        print(f"[ERROR] Error occurred while processing ({task_id}): {e}")

def listen_to_queue():
    pubsub = redis_client.pubsub()
    pubsub.subscribe('resize_queue')
    print("[INFO] Resize Service started, waiting for messages on resize_queue...")

    for message in pubsub.listen():
        if message['type'] == 'message':
            try:
                data = json.loads(message['data'])
                task_id = data.get('task_id')
                image_path = data.get('image_path')
                
                if task_id and image_path:
                    process_image(task_id, image_path)
                else:
                    print(f"[WARN] Invalid message format: {data}")
            except json.JSONDecodeError:
                print(f"[ERROR] Failed to decode JSON message: {message['data']}")

if __name__ == '__main__':
    listen_to_queue()