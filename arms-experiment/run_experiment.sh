#!/bin/bash

# Run Experiment Script for ARMS (Adaptive Recovery Management System)

set -e  # Exit immediately if a command exits with a non-zero status

# Colours for terminal output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Colour

echo -e "${GREEN}Starting ARMS Experiment${NC}"

### Step 1: Docker Environment ###
echo -e "${YELLOW}Step 1: Setting up Docker environment${NC}"
if ! command -v docker &> /dev/null || ! command -v docker-compose &> /dev/null; then
  echo -e "${RED}Docker and Docker Compose must be installed to run this script.${NC}"
  exit 1
fi

### Step 2: Launch Docker Containers ###
echo -e "${YELLOW}Step 2: Starting Docker containers${NC}"
docker-compose up -d

echo -e "${YELLOW}Waiting for Kafka to initialise (30s)...${NC}"
sleep 30

### Step 3: Kafka Topic Setup ###
docker exec -it kafka1 kafka-topics --create --topic ai_workloads \
  --bootstrap-server kafka1:9092 \
  --replication-factor 3 \
  --partitions 6 \
  --config min.insync.replicas=2

### Step 4: Workload Generator ###
echo -e "${YELLOW}Step 4: Starting workload generator${NC}"

# Build the workload generator Docker image


# Run the workload generator
# docker exec kafka1 kafka-topics --create \
#   --bootstrap-server kafka1:29092 \
#   --replication-factor 1 \
#   --partitions 6 \
#   --topic ai_workloads || echo "Topic might already exist"


### Finish ###
echo -e "${GREEN}ARMS Experiment Execution Started Successfully${NC}"


echo -e "${YELLOW}Starting metrics collector...${NC}"
python3 metric_collector.py --output all_metrics.csv --interval 15 --prometheus-url http://localhost:9090 &
METRICS_PID=$!

echo -e "${GREEN}Experiment setup complete!${NC}"
echo -e "${GREEN}Grafana UI: http://localhost:3000 (admin/admin)${NC}"
echo -e "${GREEN}Prometheus UI: http://localhost:9090${NC}"
echo -e "${GREEN}Metrics are being collected to all_metrics.csv${NC}"
echo -e ""
echo -e "${YELLOW}Press Ctrl+C to stop the experiment${NC}"

# Wait for user to stop the experiment
function cleanup {
  echo -e "${YELLOW}Stopping metrics collector...${NC}"
  kill $METRICS_PID || true
  echo -e "${GREEN}Experiment complete! Metrics have been saved to all_metrics.csv${NC}"
}

trap cleanup EXIT

# Wait for user to stop
wait $METRICS_PID

# echo -e "${YELLOW}Step 5: Collecting metrics for statistical analysis${NC}"
# echo -e "${YELLOW}Running workload for data collection...${NC}"
# echo -e "${YELLOW}This will take approximately 3 hours to collect sufficient data${NC}"
# echo -e "${YELLOW}You can monitor progress in Grafana at http://localhost:3000${NC}"

# # Here we'd normally wait for the workload generator to finish,
# # but for testing purposes, let's assume we have data after a shorter period
# sleep 300  # Wait for some data to be collected (5 minutes for testing)

# echo -e "${YELLOW}Step a6: Performing statistical analysis on metrics${NC}"
# python3 metric_analysis.py --metrics-file workload_metrics.csv --output-dir analysis_output

# echo -e "${YELLOW}Step 7: Displaying selected metrics and their rationale${NC}"
# echo "Selected metrics for workload classification:"
# cat analysis_output/selected_metrics.json

# echo -e "${YELLOW}Step 8: Training the Random Forest classifier${NC}"
# python3 train_model.py --training-data analysis_output/training_dataset.csv --output-dir model_output

# echo -e "${YELLOW}Step 9: Starting ARMS classifier service${NC}"
# python3 arms_classifier.py --model-dir model_output --prometheus-url http://localhost:9090 \
#   --kafka-bootstrap-servers localhost:9092 &
# ARMS_PID=$!

# echo -e "${YELLOW}Step 10: Preparing for failure simulation experiment${NC}"
# echo -e "${YELLOW}Will simulate broker failure in 60 seconds...${NC}"
# sleep 60

# echo -e "${YELLOW}Step 11: Simulating broker failure${NC}"
# echo -e "${RED}Stopping Kafka broker 1 to simulate failure${NC}"
# docker stop kafka-broker-1

# echo -e "${YELLOW}Monitoring recovery process...${NC}"
# echo -e "${YELLOW}You can monitor recovery in Grafana at http://localhost:3000${NC}"
# sleep 120  # Wait for recovery process (2 minutes)

# echo -e "${YELLOW}Step 12: Collecting experimental results${NC}"
# echo -e "${YELLOW}Saving classification logs and metrics${NC}"
# cp classification_log.csv experiment_results/
# cp workload_metrics.csv experiment_results/

# echo -e "${YELLOW}Step 13: Starting broker again to measure complete recovery${NC}"
# docker start kafka-broker-1
# sleep 60  # Wait for broker to rejoin

# echo -e "${YELLOW}Step 14: Analyzing recovery performance${NC}"
# # Create analysis directory
# mkdir -p recovery_analysis

# # Run analysis script (this would be implemented separately)
# python3 analyze_recovery.py --log-dir experiment_results --output-dir recovery_analysis

# echo -e "${YELLOW}Step 15: Generating visualization of recovery metrics${NC}"
# python3 visualize_recovery.py --analysis-dir recovery_analysis --output-dir recovery_analysis

# echo -e "${YELLOW}Step 16: Cleaning up${NC}"
# # Kill ARMS classifier service
# kill $ARMS_PID

# # Stop Docker containers
# echo -e "${YELLOW}Stopping Docker containers${NC}"
# docker-compose down

# echo -e "${GREEN}Experiment completed!${NC}"
# echo -e "${GREEN}Results are available in the following directories:${NC}"
# echo -e "  - analysis_output/ (metric selection analysis)"
# echo -e "  - model_output/ (trained model artifacts)"
# echo -e "  - experiment_results/ (raw experiment data)"
# echo -e "  - recovery_analysis/ (recovery performance analysis)"

# # Generate a simple report
# cat > experiment_report.md << EOF
# # ARMS Experiment Report

# ## Experiment Summary
# - Date: $(date)
# - Duration: Approximately 3 hours
# - Environment: Docker with Kafka 3.6.0, Prometheus, Grafana

# ## Selected Metrics
# $(cat analysis_output/selected_metrics.json)

# ## Model Performance
# $(cat model_output/evaluation_metrics.json)

# ## Top Feature Importance
# $(head -n 5 model_output/feature_importance.csv)

# ## Recovery Performance
# - See detailed analysis in recovery_analysis/
# EOF

# echo -e "${GREEN}Report generated: experiment_report.md${NC}"