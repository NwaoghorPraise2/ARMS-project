#!/bin/bash

# Simple setup script for ARMS Kafka Experiment
set -e

# Colors for better readability
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Setting up ARMS Kafka Experiment Project Structure${NC}"

# Create the main project directory
mkdir -p arms-experiment
cd arms-experiment

echo -e "${YELLOW}Creating directory structure...${NC}"

# Create required directories
mkdir -p grafana/provisioning/datasources
mkdir -p grafana/provisioning/dashboards
mkdir -p grafana/dashboards
mkdir -p analysis_output
mkdir -p model_output
mkdir -p experiment_results
mkdir -p recovery_analysis

# Create empty files
echo -e "${YELLOW}Creating empty files...${NC}"

# Configuration files
touch docker-compose.yml
touch Dockerfile.workload-generator
touch requirements.txt
touch jmx_exporter_config.yml
touch prometheus.yml

# Grafana configuration
touch grafana/provisioning/datasources/datasource.yml
touch grafana/provisioning/dashboards/dashboards.yml
touch grafana/dashboards/kafka_metrics_dashboard.json

# Python scripts
touch workload_generator.py
touch metric_analysis.py
touch train_model.py
touch arms_classifier.py
touch analyze_recovery.py
touch visualize_recovery.py

# Experiment runner
touch run_experiment.sh
chmod +x run_experiment.sh

echo -e "${GREEN}Project structure created successfully!${NC}"
echo -e "${GREEN}Directory: $(pwd)${NC}"
echo -e "${YELLOW}Next step: Add content to each file${NC}"

# Print the directory structure
echo -e "\nProject structure:"
find . -type f | sort