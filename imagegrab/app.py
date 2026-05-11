import os
import uuid
import json
import io
from flask import Flask, request, jsonify
from minio import Minio
import redis

app = Flask(__name__)

# Environment variables with defaults for local development
MINIO_ENDPOINT = os.getenv('MINIO_ENDPOINT', 'localhost:30002')
MINIO_ACCESS_KEY = os.getenv('MINIO_ACCESS_KEY', 'minioadmin')
MINIO_SECRET_KEY = os.getenv('MINIO_SECRET_KEY', 'minioadmin')
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
BUCKET_NAME = 'images'

# Initialization of MinIO and Redis clients
minio_client = Minio(
    MINIO_ENDPOINT,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=False
)

redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)

# Creating the bucket if it doesn't exist
try:
    if not minio_client.bucket_exists(BUCKET_NAME):
        minio_client.make_bucket(BUCKET_NAME)
except Exception as e:
    print(f"[ERROR] MinIO error: {e}")

@app.route('/upload', methods=['POST'])
def upload_image():
    if 'image' not in request.files:
        return jsonify({"error": "No image part in the request"}), 400

    file = request.files['image']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    if file:
        # 1. Generating a unique task ID and object name for the uploaded file
        task_id = str(uuid.uuid4())
        file_extension = file.filename.rsplit('.', 1)[-1]
        object_name = f"{task_id}.{file_extension}"

        try:
            # Reading the file data into memory
            file_data = file.read()
            file_size = len(file_data)
            file_stream = io.BytesIO(file_data)

            # 2. Uploading the file to MinIO
            minio_client.put_object(
                BUCKET_NAME,
                object_name,
                data=file_stream,
                length=file_size
            )
            print(f"[INFO] Image successfully uploaded to MinIO: {object_name}")

            # 3. Sending a message to the Redis queue (JSON format) [cite: 11, 39]
            message = {
                "task_id": task_id,
                "image_path": object_name
            }
            redis_client.publish('resize_queue', json.dumps(message))
            print(f"[INFO] Message sent to resize_queue: {message}")

            return jsonify({
                "message": "Image grabbed successfully",
                "task_id": task_id,
                "image_path": object_name
            }), 202

        except Exception as e:
            print(f"[ERROR] Error occurred during processing: {e}")
            return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # port 5000 is used for local development, in Kubernetes it will be overridden by the service configuration
    app.run(host='0.0.0.0', port=5000)