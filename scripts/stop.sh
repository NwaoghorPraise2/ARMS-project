#!/bin/bash

# Stop all services
echo "Stopping all ARMS components and Kafka cluster..."
docker-compose down

echo "All components stopped!"