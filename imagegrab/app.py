import os
import uuid
import json
import io
from flask import Flask, request, jsonify
from minio import Minio
import redis

app = Flask(__name__)

# Környezeti változók (alapértelmezett értékekkel a lokális teszteléshez)
MINIO_ENDPOINT = os.getenv('MINIO_ENDPOINT', 'localhost:30002') # A minio.yaml alapján a NodePort API portja
MINIO_ACCESS_KEY = os.getenv('MINIO_ACCESS_KEY', 'minioadmin')
MINIO_SECRET_KEY = os.getenv('MINIO_SECRET_KEY', 'minioadmin')
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
BUCKET_NAME = 'images'

# Kliensek inicializálása
minio_client = Minio(
    MINIO_ENDPOINT,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=False
)

redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)

# Inicializáláskor ellenőrizzük, hogy létezik-e a bucket, ha nem, létrehozzuk
try:
    if not minio_client.bucket_exists(BUCKET_NAME):
        minio_client.make_bucket(BUCKET_NAME)
except Exception as e:
    print(f"[ERROR] MinIO hiba: {e}")

@app.route('/upload', methods=['POST'])
def upload_image():
    if 'image' not in request.files:
        return jsonify({"error": "No image part in the request"}), 400

    file = request.files['image']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    if file:
        # 1. Egyedi azonosító és fájlnév generálása [cite: 41]
        task_id = str(uuid.uuid4())
        file_extension = file.filename.rsplit('.', 1)[-1]
        object_name = f"{task_id}.{file_extension}"

        try:
            # Fájl tartalmának beolvasása memóriába
            file_data = file.read()
            file_size = len(file_data)
            file_stream = io.BytesIO(file_data)

            # 2. Fájl feltöltése a MinIO-ba [cite: 11]
            minio_client.put_object(
                BUCKET_NAME,
                object_name,
                data=file_stream,
                length=file_size
            )
            print(f"[INFO] Kép sikeresen feltöltve a MinIO-ba: {object_name}")

            # 3. Üzenet küldése a Redis queue-ba (JSON formátum) [cite: 11, 39]
            message = {
                "task_id": task_id,
                "image_path": object_name
            }
            redis_client.publish('resize_queue', json.dumps(message))
            print(f"[INFO] Üzenet kiküldve a resize_queue-ra: {message}")

            return jsonify({
                "message": "Image grabbed successfully",
                "task_id": task_id,
                "image_path": object_name
            }), 202

        except Exception as e:
            print(f"[ERROR] Hiba történt a feldolgozás során: {e}")
            return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # 5000-es porton indítjuk a Flask szervert
    app.run(host='0.0.0.0', port=5000)