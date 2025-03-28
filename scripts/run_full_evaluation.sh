#!/bin/bash

# Run the full evaluation across all experimental conditions
echo "Starting full ARMS evaluation..."

# Generate default experiment plan
python3 -m src.evaluator.experiment_config --output experiments/default_plan.json

# Run evaluation
docker-compose run --rm experiment-coordinator python3 -m src.evaluator.experiment_coordinator --experiment-plan experiments/default_plan.json

echo "Full evaluation completed!"