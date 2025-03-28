#!/bin/bash

# Ensure Kafka is running before creating topics
echo "Creating Kafka topics..."

# Create ARMS topics
docker-compose exec kafka-1 kafka-topics --create --bootstrap-server kafka-1:9092 --topic arms-features --partitions 3 --replication-factor 3 --if-not-exists
docker-compose exec kafka-1 kafka-topics --create --bootstrap-server kafka-1:9092 --topic arms-classifications --partitions 3 --replication-factor 3 --if-not-exists
docker-compose exec kafka-1 kafka-topics --create --bootstrap-server kafka-1:9092 --topic arms-system-state --partitions 3 --replication-factor 3 --if-not-exists
docker-compose exec kafka-1 kafka-topics --create --bootstrap-server kafka-1:9092 --topic arms-strategies --partitions 3 --replication-factor 3 --if-not-exists
docker-compose exec kafka-1 kafka-topics --create --bootstrap-server kafka-1:9092 --topic arms-recovery-metrics --partitions 3 --replication-factor 3 --if-not-exists
docker-compose exec kafka-1 kafka-topics --create --bootstrap-server kafka-1:9092 --topic arms-failure-events --partitions 3 --replication-factor 3 --if-not-exists
docker-compose exec kafka-1 kafka-topics --create --bootstrap-server kafka-1:9092 --topic arms-experiment-control --partitions 3 --replication-factor 3 --if-not-exists
docker-compose exec kafka-1 kafka-topics --create --bootstrap-server kafka-1:9092 --topic arms-workload-metrics --partitions 3 --replication-factor 3 --if-not-exists

# Verify topics were created
docker-compose exec kafka-1 kafka-topics --list --bootstrap-server kafka-1:9092

echo "Kafka topics created successfully!"
