#!/bin/bash

# Create necessary directories
mkdir -p data/models
mkdir -p data/training
mkdir -p experiments/workloads
mkdir -p experiments/results
mkdir -p experiments/analysis
mkdir -p infrastructure/monitoring/grafana-provisioning/dashboards
mkdir -p infrastructure/monitoring/grafana-provisioning/datasources

# Create monitoring configuration files if they don't exist
if [ ! -f infrastructure/monitoring/prometheus.yml ]; then
  cat > infrastructure/monitoring/prometheus.yml << "CONFIG"
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  - job_name: 'jmx-exporter'
    static_configs:
      - targets: ['jmx-exporter:5556']

  - job_name: 'kafka'
    static_configs:
      - targets: ['kafka-1:9999', 'kafka-2:9999', 'kafka-3:9999']
    metrics_path: '/metrics'

  - job_name: 'arms-monitor'
    static_configs:
      - targets: ['arms-monitor:8080']
CONFIG
fi

if [ ! -f infrastructure/monitoring/jmx-exporter-config.yaml ]; then
  cat > infrastructure/monitoring/jmx-exporter-config.yaml << "CONFIG"
lowercaseOutputName: true
lowercaseOutputLabelNames: true
rules:
  - pattern: kafka.server<type=(.+), name=(.+), clientId=(.+)><>Value
    name: kafka_server_$1_$2
    labels:
      clientId: "$3"
  
  - pattern: kafka.server<type=(.+), name=(.+)><>Value
    name: kafka_server_$1_$2
CONFIG
fi

# Generate training data for the classifier
echo "Generating synthetic training data..."
python3 -m src.classifier.generate_training_data --output data/training/training_data.csv

# Train the classifier model
echo "Training classifier model..."
python3 -m src.classifier.train_model --data data/training/training_data.csv --model-output data/models/workload_classifier.joblib

echo "Setup completed successfully!"
