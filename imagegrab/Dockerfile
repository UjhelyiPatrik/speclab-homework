# imagegrab/Dockerfile
FROM python:3.12-slim

# Set the working directory in the container
WORKDIR /app

# Copy dependencies and install them
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code into the container
COPY app.py .

# Expose the port used by Flask
EXPOSE 5000

# Start the service
CMD ["python", "app.py"]