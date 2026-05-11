FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy model files and application code
COPY MobileNetSSD_deploy.prototxt .
COPY MobileNetSSD_deploy.caffemodel .
COPY app.py .

CMD ["python", "app.py"]