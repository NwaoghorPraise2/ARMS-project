#!/bin/bash

# Start all services in the correct order
echo "Starting ARMS system..."

# Step 1: Start ZooKeeper ensemble
echo "Starting ZooKeeper ensemble..."
docker-compose up -d zookeeper-1 zookeeper-2 zookeeper-3
echo "Waiting for ZooKeeper to initialize (10 seconds)..."
sleep 10

# Step 2: Start Kafka brokers
echo "Starting Kafka brokers..."
docker-compose up -d kafka-1 kafka-2 kafka-3
echo "Waiting for Kafka to initialize (20 seconds)..."
sleep 20

# Step 3: Start monitoring tools
echo "Starting monitoring infrastructure..."
docker-compose up -d prometheus grafana jmx-exporter
echo "Waiting for monitoring tools to initialize (10 seconds)..."
sleep 10

# Step 4: Create Kafka topics
echo "Creating Kafka topics..."
./scripts/create_topics.sh

# Step 5: Start ARMS core components
echo "Starting ARMS core components..."
docker-compose up -d arms-monitor
sleep 5
docker-compose up -d arms-classifier
sleep 5
docker-compose up -d arms-selector
sleep 5
docker-compose up -d arms-orchestrator
sleep 5

# Step 6: Start experiment components
echo "Starting experiment components..."
docker-compose up -d workload-generator
docker-compose up -d fault-injector

# Step 7: Verify all components are running
echo "Verifying deployment..."
docker-compose ps

echo "ARMS system startup complete!"
echo "Access Grafana at: http://localhost:3000 (admin/admin)"
echo "Access Prometheus at: http://localhost:9090"
echo "Run experiments with: ./scripts/run_experiment.sh"