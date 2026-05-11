# Image Processing Microservices Pipeline

This project demonstrates how to decompose a monolithic image processing application into a distributed, event-driven microservices architecture, deployed on Kubernetes (K3s).

---

## System Overview

The system processes images through a sequential pipeline, where each stage is handled by a dedicated microservice. To optimize performance, large binary data (images) are stored in **MinIO** (object storage), while only metadata and file paths are exchanged via **Redis** (message broker) using a Publish/Subscribe pattern.

### Microservices

1. **ImageGrab**: Provides a REST API to accept image uploads and initiates the pipeline.
2. **Resize**: Scales images down to 25% of their original size for faster processing.
3. **Grayscale**: Converts processed images to a single color channel (black and white).
4. **ObjectDetect**: Uses a MobileNet SSD model to identify objects within the grayscale images.
5. **Tag**: Draws bounding boxes and labels on the original high-resolution image based on detection coordinates.

---

## Setup & Deployment

Follow these steps to deploy the entire stack on a fresh machine (Ubuntu/Debian recommended).

### 1. Prerequisites

Ensure you have the following installed:
- **Docker**: For building container images.
- **K3s / Kubernetes Cluster**: A running K8s environment.
- **kubectl**: Kubernetes command-line tool.
- **Kustomize**: (Included in modern `kubectl`) for managing configurations.

### 2. Clone the Repository

```bash
git clone https://github.com/UjhelyiPatrik/speclab-homework.git
cd speclab-homework
```

### 3. Configure Secrets

Create a `secrets.env` file in the root directory. This file is excluded from version control to protect sensitive credentials. Example:

```bash
cat <<EOF > secrets.env
MINIO_ACCESS_KEY=your_access_key
MINIO_SECRET_KEY=your_secret_key
MINIO_ROOT_USER=your_admin_user
MINIO_ROOT_PASSWORD=your_admin_password
EOF
```

### 4. Build and Import Images

Since the cluster uses a local registry, you must build the images and manually import them into the K3s image store. The build.sh shell script handles this task, but you have to add execute right to the file:

```bash
chmod chmod +x build_images.sh
./build.sh
```

### 5. Deploy to Kubernetes

Use Kustomize to deploy all resources (deployments, services, and secret generators) in one command:

```bash
kubectl apply -k .
```

---

## Usage

### Accessing the API

The ImageGrab service is exposed via NodePort **30005**. You can trigger the pipeline by uploading an image:

```bash
curl -X POST -F "image=@test-1.jpg" http://<EC2_PUBLIC_IP>:30005/upload
```

### Monitoring Logs

To see the processing in real-time, monitor the logs of the services:

```bash
kubectl logs -f -l project=image-processor-v2 --max-log-requests=10
```

### Viewing Results

The final processed image (`result.jpg`) will be available in the MinIO storage:

- MinIO Console: http://<EC2_PUBLIC_IP>:30003
- Credentials: Use the values defined in your `secrets.env`.

---

## Management

To stop and remove all resources from the cluster:

```bash
kubectl delete -k .
```

---

## Additional Information

### MinIO

[MinIO](https://min.io/) is an open-source object storage server compatible with Amazon S3's API. It provides a simple HTTP API for storing and retrieving objects (like files, images, or any binary data). In this project, MinIO serves as the central storage for images at various stages of processing, allowing each microservice to retrieve and store images efficiently. The MinIO console is exposed on NodePort **30003**.

You can find the [`minio.yaml`](./minio.yaml) file in this repository to deploy your MinIO instance to the cluster. MinIO has a Python client for easy integration.

### Redis

[Redis](https://redis.io/) is a key-value store that can act as a message queue. This project uses Redis for inter-service communication via publish/subscribe channels. The [`redis.yaml`](./redis.yaml) config is provided for easy deployment. Redis also has a Python client for integration.

---

## Notes

- Do not hard-code configuration values (service host names, usernames, passwords); use configmaps or environment variables in deployments.
- Each service is containerized and deployed independently for scalability and maintainability.
- Logging is included in each service for easier debugging and monitoring.

For more details, see the source code and deployment manifests in this repository.