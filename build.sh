#!/bin/bash

# Define services
SERVICES=("imagegrab" "resize" "grayscale" "objectdetect" "tag")

# Build and Import loop
for SERVICE in "${SERVICES[@]}"
do
    echo "Building $SERVICE..."
    sudo docker build -t $SERVICE:latest ./$SERVICE
    sudo docker save $SERVICE:latest | sudo k3s ctr images import -
done