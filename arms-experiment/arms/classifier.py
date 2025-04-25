# kafka_classifier_service.py

import joblib
import numpy as np
import time
import logging
import threading
import requests
import os
import pandas as pd
import json
from flask import Flask, jsonify
from prometheus_client import start_http_server, Gauge, Counter
from urllib.parse import urljoin
from strategy_selector import StrategySelector, QUICK_REBALANCE, RESOURCE_OPTIMIZED, CONTROLLED_GRADUAL

# Get Prometheus URL from environment variable or use default
PROMETHEUS_URL = os.environ.get('PROMETHEUS_URL', 'http://localhost:9090')

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("kafka_classifier.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("kafka_classifier")

# Define metrics for Prometheus
WORKLOAD_TYPE = Gauge('kafka_workload_type', 'Predicted Kafka workload type (0=REAL_TIME_EVENT_DRIVEN, 1=BATCH_DATA_INTENSIVE)')
PREDICTION_CONFIDENCE = Gauge('kafka_prediction_confidence', 'Confidence score for workload prediction (percentage)')
PREDICTION_COUNT = Counter('kafka_prediction_count_total', 'Total number of predictions made')
PREDICTION_SUCCESS = Counter('kafka_prediction_success_total', 'Total number of successful predictions')
PREDICTION_ERROR = Counter('kafka_prediction_error_total', 'Total number of prediction errors')

# Feature value metrics
FEATURE_VALUES = {
    'request_rate_variance': Gauge('kafka_feature_request_rate_variance', 'Value of request_rate_variance feature'),
    'node_disk_write_bytes_total': Gauge('kafka_feature_node_disk_write_bytes_total', 'Value of node_disk_write_bytes_total feature'),
    'message_rate_variance': Gauge('kafka_feature_message_rate_variance', 'Value of message_rate_variance feature'),
    'node_memory_MemAvailable_bytes': Gauge('kafka_feature_node_memory_MemAvailable_bytes', 'Value of node_memory_MemAvailable_bytes feature')
}

# Strategy metrics
CURRENT_STRATEGY = Gauge('kafka_recovery_strategy', 'Current Kafka recovery strategy', ['strategy_name'])
for strategy in [QUICK_REBALANCE, RESOURCE_OPTIMIZED, CONTROLLED_GRADUAL]:
    CURRENT_STRATEGY.labels(strategy_name=strategy).set(0)

class KafkaWorkloadClassifier:
    def __init__(self, model_path="kafka_logistic_regression_model.pkl", 
                 scaler_path="kafka_feature_scaler.pkl",
                 prometheus_url="http://localhost:9090",
                 check_interval=30,
                 strategy_buffer_path="/app/data/strategy_buffer.json"):
        """
        Initialize the Kafka workload classifier service.
        
        Args:
            model_path: Path to the trained logistic regression model
            scaler_path: Path to the feature scaler
            prometheus_url: URL of the Prometheus server
            check_interval: Time between classifications in seconds
            strategy_buffer_path: Path to the strategy buffer file
        """
        self.model_path = model_path
        self.scaler_path = scaler_path
        self.prometheus_url = prometheus_url
        self.check_interval = check_interval
        self.running = False
        
        # Load model and scaler
        try:
            self.model = joblib.load(model_path)
            self.scaler = joblib.load(scaler_path)
            logger.info("Successfully loaded model and scaler")
        except Exception as e:
            logger.error(f"Error loading model or scaler: {e}")
            raise
        
        # Define required features
        self.required_features = [
            'request_rate_variance',
            'node_disk_write_bytes_total',
            'message_rate_variance',
            'node_memory_MemAvailable_bytes'
        ]
        
        # Define Prometheus queries for the required features
        self.prometheus_queries = {
            'request_rate_variance': 'stddev_over_time(sum(rate(kafka_server_brokertopicmetrics_totalproducerequests_total[1m]))[15m:1m])',
            'node_disk_write_bytes_total': 'sum(rate(node_disk_written_bytes_total[1m]))',
            'message_rate_variance': 'stddev(rate(kafka_server_brokertopicmetrics_messagesin_total[1m]))',
            'node_memory_MemAvailable_bytes': 'avg(node_memory_MemAvailable_bytes)'
        }
        
        # Map workload types to descriptions
        self.workload_types = {
            0: "REAL_TIME_EVENT_DRIVEN",
            1: "BATCH_DATA_INTENSIVE"
        }
        
        # Store the latest prediction results
        self.latest_prediction = {
            "value": None,
            "type": "UNKNOWN",
            "confidence": 0,
            "timestamp": None,
            "features": {}
        }
        
        # Initialize strategy selector
        self.strategy_selector = StrategySelector(buffer_path=strategy_buffer_path)
        self.strategy_selector.start()
        logger.info("Strategy selector initialized and started")
        
    def _get_metric_value(self, response):
        """Extract metric value from Prometheus response."""
        try:
            if response and response.get("status") == "success":
                result = response.get("data", {}).get("result", [])
                if result and len(result) > 0:
                    return float(result[0]["value"][1])
            return None
        except (KeyError, IndexError, ValueError) as e:
            logger.error(f"Error extracting metric value: {e}")
            return None
    
    def collect_metrics(self):
        """Collect required metrics from Prometheus."""
        metrics = {}
        
        for feature, query in self.prometheus_queries.items():
            try:
                url = urljoin(self.prometheus_url, "/api/v1/query")
                response = requests.get(url, params={"query": query})
                
                if response.status_code == 200:
                    metric_value = self._get_metric_value(response.json())
                    metrics[feature] = metric_value
                    
                    # Update Prometheus gauge for this feature
                    if feature in FEATURE_VALUES and metric_value is not None:
                        FEATURE_VALUES[feature].set(metric_value)
                        logger.debug(f"Feature {feature}: {metric_value}")
                else:
                    logger.warning(f"Failed to fetch {feature}: {response.status_code}")
                    metrics[feature] = None
            except Exception as e:
                logger.error(f"Error fetching {feature}: {e}")
                metrics[feature] = None
        
        return metrics
    
    def predict_workload_type(self, metrics):
        """
        Predict the workload type based on the collected metrics.
        
        Args:
            metrics: Dictionary containing the required metrics
            
        Returns:
            Dictionary with prediction results and confidence
        """
        PREDICTION_COUNT.inc()
        
        # Check if all required features are available
        for feature in self.required_features:
            if feature not in metrics or metrics[feature] is None:
                logger.warning(f"Missing required feature: {feature}")
                PREDICTION_ERROR.inc()
                return {
                    "value": None,
                    "type": "UNKNOWN",
                    "confidence": 0,
                    "error": f"Missing required feature: {feature}",
                    "features": metrics
                }
        
        try:
            # Create a DataFrame with feature names instead of a NumPy array
            features_df = pd.DataFrame([[
                metrics['request_rate_variance'],
                metrics['node_disk_write_bytes_total'],
                metrics['message_rate_variance'],
                metrics['node_memory_MemAvailable_bytes']
            ]], columns=self.required_features)
            
            # Scale features
            scaled_features = self.scaler.transform(features_df)
            
            # Make prediction
            prediction = self.model.predict(scaled_features)[0]
            
            # Get probability
            probabilities = self.model.predict_proba(scaled_features)[0]
            confidence = float(probabilities[prediction]) * 100
            
            # Update Prometheus metrics
            WORKLOAD_TYPE.set(prediction)
            PREDICTION_CONFIDENCE.set(confidence)
            PREDICTION_SUCCESS.inc()
            
            # Select recovery strategy based on workload type and confidence
            selected_strategy = self.strategy_selector.select_strategy(prediction, confidence)
            logger.info(f"Selected recovery strategy: {selected_strategy} based on {self.workload_types[prediction]} workload")
            
            # Update Prometheus metrics for the strategy
            for strategy in [QUICK_REBALANCE, RESOURCE_OPTIMIZED, CONTROLLED_GRADUAL]:
                if strategy == selected_strategy:
                    CURRENT_STRATEGY.labels(strategy_name=strategy).set(1)
                else:
                    CURRENT_STRATEGY.labels(strategy_name=strategy).set(0)
            
            prediction_result = {
                "value": int(prediction),
                "type": self.workload_types[prediction],
                "confidence": confidence,
                "timestamp": time.time(),
                "features": metrics,
                "probabilities": {
                    self.workload_types[0]: float(probabilities[0]) * 100,
                    self.workload_types[1]: float(probabilities[1]) * 100
                },
                "recovery_strategy": selected_strategy
            }
            
            # Update latest prediction
            self.latest_prediction = prediction_result
            
            return prediction_result
        except Exception as e:
            logger.error(f"Error predicting workload type: {e}")
            PREDICTION_ERROR.inc()
            return {
                "value": None,
                "type": "ERROR",
                "confidence": 0,
                "error": str(e),
                "features": metrics
            }
    
    def classification_loop(self):
        """Main classification loop."""
        while self.running:
            try:
                # Collect metrics
                metrics = self.collect_metrics()
                
                # Make prediction
                prediction = self.predict_workload_type(metrics)
                
                # Log prediction
                logger.info(f"Predicted workload type: {prediction['type']} with {prediction.get('confidence', 0):.2f}% confidence")
                
                # Sleep for the check interval
                time.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"Error in classification loop: {e}")
                time.sleep(5)  # Wait a bit before retrying
    
    def start(self):
        """Start the classification service."""
        self.running = True
        
        # Start classification thread
        self.classification_thread = threading.Thread(target=self.classification_loop)
        self.classification_thread.daemon = True
        self.classification_thread.start()
        
        logger.info(f"Started Kafka workload classification service with interval {self.check_interval}s")
    
    def stop(self):
        """Stop the classification service."""
        self.running = False
        if hasattr(self, 'classification_thread'):
            self.classification_thread.join(timeout=30)
        
        # Stop strategy selector
        if hasattr(self, 'strategy_selector'):
            self.strategy_selector.stop()
        
        logger.info("Stopped Kafka workload classification service")

# Create Flask app for API access
app = Flask(__name__)

@app.route('/api/prediction', methods=['GET'])
def get_prediction():
    """API endpoint to get the latest prediction."""
    if classifier.latest_prediction["value"] is None:
        return jsonify({
            "status": "waiting",
            "message": "No prediction available yet"
        }), 204
    
    return jsonify({
        "status": "success",
        "prediction": classifier.latest_prediction
    })

@app.route('/api/strategy', methods=['GET'])
def get_strategy():
    """API endpoint to get the current recovery strategy."""
    if not hasattr(classifier, 'strategy_selector') or not classifier.strategy_selector.current_strategy:
        return jsonify({
            "status": "waiting",
            "message": "No strategy selected yet"
        }), 204
    
    # Read directly from buffer for most up-to-date information
    try:
        with open(classifier.strategy_selector.buffer_path, 'r') as f:
            buffer_data = json.load(f)
        
        return jsonify({
            "status": "success",
            "strategy": buffer_data
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/health', methods=['GET'])
def health_check():
    """API endpoint for health checks."""
    return jsonify({"status": "healthy"})

if __name__ == "__main__":
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description='Kafka Workload Classification Service')
    parser.add_argument('--model', default='/app/models/kafka_logistic_regression_model.pkl', help='Path to the trained model')
    parser.add_argument('--scaler', default='/app/models/kafka_feature_scaler.pkl', help='Path to the feature scaler')
    parser.add_argument('--prometheus', default=PROMETHEUS_URL, help='Prometheus URL')
    parser.add_argument('--interval', type=int, default=30, help='Classification interval in seconds')
    parser.add_argument('--port', type=int, default=5001, help='Port for the API server')
    parser.add_argument('--metrics-port', type=int, default=8001, help='Port for Prometheus metrics')
    parser.add_argument('--strategy-buffer', default='/app/data/strategy_buffer.json', help='Path to the strategy buffer file')
    args = parser.parse_args()
    
    # Start Prometheus metrics server
    start_http_server(args.metrics_port)
    logger.info(f"Started Prometheus metrics server on port {args.metrics_port}")
    
    # Initialize and start the classifier
    classifier = KafkaWorkloadClassifier(
        model_path=args.model,
        scaler_path=args.scaler,
        prometheus_url=args.prometheus,
        check_interval=args.interval,
        strategy_buffer_path=args.strategy_buffer
    )
    classifier.start()
    
    # Start the API server
    app.run(host='0.0.0.0', port=args.port)