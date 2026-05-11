import os
import json
import cv2
import numpy as np
import redis
from minio import Minio

# Environment variables with default values
MINIO_ENDPOINT = os.getenv('MINIO_ENDPOINT', 'localhost:30002')
MINIO_ACCESS_KEY = os.getenv('MINIO_ACCESS_KEY', 'minioadmin')
MINIO_SECRET_KEY = os.getenv('MINIO_SECRET_KEY', 'minioadmin')
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
BUCKET_NAME = 'images'

# Model classes and confidence threshold
CLASSES = ["background", "aeroplane", "bicycle", "bird", "boat",
           "bottle", "bus", "car", "cat", "chair", "cow", "diningtable",
           "dog", "horse", "motorbike", "person", "pottedplant", "sheep",
           "sofa", "train", "tvmonitor"]
CONFIDENCE_MIN = 0.4

# Client initialization
minio_client = Minio(MINIO_ENDPOINT, access_key=MINIO_ACCESS_KEY, secret_key=MINIO_SECRET_KEY, secure=False)
redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)

# Model loading into memory (on startup)
print("[INFO] Loading model...")
net = cv2.dnn.readNetFromCaffe("./MobileNetSSD_deploy.prototxt", "./MobileNetSSD_deploy.caffemodel")

def process_image(task_id, image_path, origin_h, origin_w):
    try:
        print(f"[INFO] ObjectDetect processing starting: {task_id}")
        
        # 1. Grayscale image download from MinIO
        response = minio_client.get_object(BUCKET_NAME, image_path)
        file_data = response.read()
        response.close()
        response.release_conn()

        # 2. Convert bytes to OpenCV format
        nparr = np.frombuffer(file_data, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)
        
        if image is None:
            raise ValueError("Failed to decode the image.")

        # The model expects a 3-channel image, so we need to convert the grayscale back to BGR
        image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        (height, width) = image.shape[:2]
        
        # Blob creation and network input
        blob = cv2.dnn.blobFromImage(image, 0.007843, (height, width), 127.5)
        net.setInput(blob)
        detections = net.forward()

        labels_and_coords = []
        # 3. Process results and filter them
        for i in np.arange(0, detections.shape[2]):
            confidence = detections[0, 0, i, 2]
            if confidence > CONFIDENCE_MIN:
                idx = int(detections[0, 0, i, 1])
                # Scale the bounding box coordinates back to the original image size
                box = detections[0, 0, i, 3:7] * np.array([origin_w, origin_h, origin_w, origin_h])
                (startX, startY, endX, endY) = box.astype("int")
                
                labels_and_coords.append({
                    "startX": int(startX),
                    "startY": int(startY),
                    "endX": int(endX),
                    "endY": int(endY),
                    "label": {"name": CLASSES[idx], "index": int(idx)},
                    "confidence": float(confidence)
                })

        print(f"[INFO] Number of detected objects: {len(labels_and_coords)}")

        # 4. Send message to Tag Service
        message = {
            "task_id": task_id,
            "detections": labels_and_coords
        }
        redis_client.publish('tag_queue', json.dumps(message))
        print(f"[INFO] Message sent to tag_queue: {task_id}")

    except Exception as e:
        print(f"[ERROR] Error occurred while processing ({task_id}): {e}")

def listen_to_queue():
    pubsub = redis_client.pubsub()
    pubsub.subscribe('object_detect_queue')
    print("[INFO] ObjectDetect Service started, waiting for messages...")

    for message in pubsub.listen():
        if message['type'] == 'message':
            try:
                data = json.loads(message['data'])
                task_id = data.get('task_id')
                image_path = data.get('image_path')
                origin_h = data.get('origin_h')
                origin_w = data.get('origin_w')
                
                if all([task_id, image_path, origin_h, origin_w]):
                    process_image(task_id, image_path, origin_h, origin_w)
                else:
                    print(f"[WARN] Invalid message format: {data}")
            except json.JSONDecodeError:

if __name__ == '__main__':
    listen_to_queue()