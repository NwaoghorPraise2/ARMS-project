#!/bin/bash

# Run a single experiment with specified parameters
WORKLOAD_TYPE=$1
WORKLOAD_SIZE=$2
FAILURE_SCENARIO=$3
RECOVERY_APPROACH=$4

if [ -z "$WORKLOAD_TYPE" ] || [ -z "$WORKLOAD_SIZE" ] || [ -z "$FAILURE_SCENARIO" ] || [ -z "$RECOVERY_APPROACH" ]; then
    echo "Usage: $0 <workload_type> <workload_size> <failure_scenario> <recovery_approach>"
    echo "Example: $0 batch_data_intensive medium single_broker arms_adaptive"
    exit 1
fi

echo "Running experiment with:"
echo "  Workload Type: $WORKLOAD_TYPE"
echo "  Workload Size: $WORKLOAD_SIZE"
echo "  Failure Scenario: $FAILURE_SCENARIO"
echo "  Recovery Approach: $RECOVERY_APPROACH"

# Create experiment config
CONFIG="{\"workload_type\": \"$WORKLOAD_TYPE\", \"workload_size\": \"$WORKLOAD_SIZE\", \"failure_scenario\": \"$FAILURE_SCENARIO\", \"recovery_approach\": \"$RECOVERY_APPROACH\", \"repetitions\": 1, \"duration_minutes\": 5}"

# Save config to temp file
echo $CONFIG > /tmp/experiment_config.json

# Run single experiment
docker-compose run --rm experiment-coordinator python3 -m src.evaluator.experiment_coordinator --experiment-plan /tmp/experiment_config.json

echo "Experiment completed!"