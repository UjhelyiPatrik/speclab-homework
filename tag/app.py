import os
import json
import cv2
import numpy as np
import redis
from minio import Minio
import io

# environment variables with default values
MINIO_ENDPOINT = os.getenv('MINIO_ENDPOINT', 'localhost:30002')
MINIO_ACCESS_KEY = os.getenv('MINIO_ACCESS_KEY', 'minioadmin')
MINIO_SECRET_KEY = os.getenv('MINIO_SECRET_KEY', 'minioadmin')
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
BUCKET_NAME = 'images'

# Settings for OpenCV DNN model
CLASSES = ["background", "aeroplane", "bicycle", "bird", "boat",
           "bottle", "bus", "car", "cat", "chair", "cow", "diningtable",
           "dog", "horse", "motorbike", "person", "pottedplant", "sheep",
           "sofa", "train", "tvmonitor"]
COLORS = np.random.uniform(0, 255, size=(len(CLASSES), 3))

# Client initializations
minio_client = Minio(MINIO_ENDPOINT, access_key=MINIO_ACCESS_KEY, secret_key=MINIO_SECRET_KEY, secure=False)
redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)

def process_image(task_id, detections):
    try:
        print(f"[INFO] Starting image processing for task: {task_id}")
        
        # 1. Search for the original image in MinIO using the task_id
        objects = minio_client.list_objects(BUCKET_NAME, prefix=task_id)
        original_image_path = None
        for obj in objects:
            # Search for the original file only (e.g., "1234-5678.jpg")
            if obj.object_name.startswith(f"{task_id}."):
                original_image_path = obj.object_name
                break
                
        if not original_image_path:
            raise ValueError(f"Original image not found for task: {task_id}")

        # 2. Download and decode the original image from MinIO
        response = minio_client.get_object(BUCKET_NAME, original_image_path)
        file_data = response.read()
        response.close()
        response.release_conn()

        nparr = np.frombuffer(file_data, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if image is None:
            raise ValueError("Failed to decode the original image.")

        # 3. Draw bounding boxes and labels on the image based on detections
        for det in detections:
            label_name = det["label"]["name"]
            index = det["label"]["index"]
            startX, startY = det["startX"], det["startY"]
            endX, endY = det["endX"], det["endY"]

            # Bounding box drawing
            cv2.rectangle(image, (startX, startY), (endX, endY), COLORS[index], 2)
            # Szöveg elhelyezése
            cv2.putText(image, label_name, (startX, startY - 10), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, COLORS[index], 2)

        # 4. Encode the image and upload it back to MinIO
        _, buffer = cv2.imencode('.jpg', image)
        result_bytes = buffer.tobytes()
        result_stream = io.BytesIO(result_bytes)
        
        # Standard output file name
        out_file = f"result.jpg"
        
        minio_client.put_object(
            BUCKET_NAME,
            out_file,
            data=result_stream,
            length=len(result_bytes)
        )

        # Saving it also with task_id for easier retrieval
        # Placing the seek before upload to ensure the stream is read from the beginning
        result_stream.seek(0)
        minio_client.put_object(
            BUCKET_NAME,
            f"result_{task_id}.jpg",
            data=result_stream,
            length=len(result_bytes)
        )
        
        print(f"[INFO] Final image successfully generated and uploaded: {out_file} ")

    except Exception as e:
        print(f"[ERROR] Error during processing ({task_id}): {e}")

def listen_to_queue():
    pubsub = redis_client.pubsub()
    pubsub.subscribe('tag_queue')
    print("[INFO] Tag Service started, listening to tag_queue channel...")

    for message in pubsub.listen():
        if message['type'] == 'message':
            try:
                data = json.loads(message['data'])
                task_id = data.get('task_id')
                detections = data.get('detections', [])
                
                if task_id:
                    process_image(task_id, detections)
                else:
                    print(f"[WARN] Missing task_id in message: {data}")
            except json.JSONDecodeError:
                print(f"[ERROR] JSON decoding error: {message['data']}")

if __name__ == '__main__':
    listen_to_queue()