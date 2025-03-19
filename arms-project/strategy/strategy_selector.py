import os
import time
import json
import logging
import glob
import requests
from datetime import datetime
from flask import Flask, jsonify, request
from taxonomy import WorkloadTaxonomy, RecoveryStrategies

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('StrategySelector')

app = Flask(__name__)

class StrategySelector:
    def __init__(self):
        self.taxonomy = WorkloadTaxonomy()
        self.strategies = RecoveryStrategies()
        logger.info("StrategySelector initialized")
    
    def select_strategy(self, workload_type, current_metrics=None):
        """Select recovery strategy based on workload type and current metrics"""
        # Default to workload type's preferred strategy
        if workload_type in self.taxonomy.recovery_requirements:
            strategy = self.taxonomy.recovery_requirements[workload_type]['preferred_strategy']
        else:
            # If unknown workload type, use controlled gradual as a safe default
            strategy = self.strategies.CONTROLLED_GRADUAL
        
        # If metrics are provided, refine strategy selection
        if current_metrics:
            # For real-time event-driven workloads
            if workload_type == self.taxonomy.REAL_TIME_EVENT_DRIVEN:
                # If system is under high load, use high redundancy for safety
                if current_metrics.get('cpu_usage_mean', 0) > 0.8:
                    strategy = self.strategies.HIGH_REDUNDANCY
                # If latency is already high, use quick rebalance to recover faster
                elif current_metrics.get('latency_p99_mean', 0) > 100:
                    strategy = self.strategies.QUICK_REBALANCE
            
            # For batch data-intensive workloads
            elif workload_type == self.taxonomy.BATCH_DATA_INTENSIVE:
                # If system is under high load, use resource optimized
                if current_metrics.get('cpu_usage_mean', 0) > 0.7:
                    strategy = self.strategies.RESOURCE_OPTIMIZED
                # If currently in a peak, use controlled gradual
                elif current_metrics.get('message_rate_mean', 0) > self.taxonomy.classification_thresholds['message_rate_per_sec']['high']:
                    strategy = self.strategies.CONTROLLED_GRADUAL
        
        # Get strategy configuration
        config = self.strategies.strategy_configs.get(strategy, {})
        
        return {
            'strategy': strategy,
            'config': config,
            'description': self._get_strategy_description(strategy),
            'workload_type': workload_type
        }
    
    def _get_strategy_description(self, strategy):
        """Get human-readable description of the strategy"""
        descriptions = {
            self.strategies.QUICK_REBALANCE: "Quick rebalance prioritizes recovery speed over resource usage. Appropriate for real-time workloads where downtime must be minimized.",
            self.strategies.CONTROLLED_GRADUAL: "Controlled gradual recovery balances recovery time and resource usage. Suitable for mixed workloads.",
            self.strategies.RESOURCE_OPTIMIZED: "Resource optimized recovery prioritizes stability and minimal resource usage over recovery speed. Suitable for batch workloads.",
            self.strategies.HIGH_REDUNDANCY: "High redundancy recovery prioritizes data safety and availability at the cost of higher resource usage."
        }
        
        return descriptions.get(strategy, "Custom recovery strategy")

# Create the selector
selector = StrategySelector()

@app.route('/api/strategy', methods=['GET'])
def get_strategy():
    # Get workload type from query parameters or latest classification
    workload_type = request.args.get('workload_type')
    
    if not workload_type:
        # Get the latest classification
        classification_files = sorted(glob.glob("/app/data/classification_*.json"))
        if not classification_files:
            return jsonify({"error": "No classification data available"}), 404
        
        with open(classification_files[-1], "r") as f:
            classification = json.load(f)
        
        workload_type = classification.get('workload_type')
    
    # Get latest metrics
    current_metrics = None
    feature_files = sorted(glob.glob("/app/data/features_*.json"))
    if feature_files:
        with open(feature_files[-1], "r") as f:
            current_metrics = json.load(f)
    
    # Select strategy
    strategy = selector.select_strategy(workload_type, current_metrics)
    
    # Add timestamp
    strategy['timestamp'] = datetime.now().isoformat()
    
    # Add classification confidence if available
    if classification_files:
        with open(classification_files[-1], "r") as f:
            classification = json.load(f)
        strategy['classification'] = {
            'confidence': classification.get('confidence', 0),
            'timestamp': classification.get('timestamp')
        }
    
    # Save recommendation
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    with open(f"/app/data/recommendation_{timestamp}.json", "w") as f:
        json.dump(strategy, f)
    
    return jsonify(strategy)

@app.route('/api/strategy/manual', methods=['POST'])
def manual_strategy():
    data = request.json
    
    if not data or 'workload_type' not in data:
        return jsonify({"error": "workload_type is required"}), 400
    
    workload_type = data['workload_type']
    current_metrics = data.get('metrics')
    
    strategy = selector.select_strategy(workload_type, current_metrics)
    strategy['timestamp'] = datetime.now().isoformat()
    
    return jsonify(strategy)

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy"})

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5005)
