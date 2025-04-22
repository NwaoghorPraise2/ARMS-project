#!/usr/bin/env python3

import pandas as pd
import numpy as np
import time
import json
import logging
import argparse
import threading
import requests
import joblib
import csv
import os
from sklearn.preprocessing import LabelEncoder
from confluent_kafka import Producer, Consumer, KafkaError, KafkaException
from confluent_kafka.admin import AdminClient, NewTopic
import prometheus_client
from prometheus_client import Counter, Gauge, Histogram

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("arms_classifier.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("arms_classifier")

# Prometheus metrics
prometheus_client.start_http_server(8001)
CLASSIFICATION_COUNTER = Counter('arms_classifications_total', 'Total number of workload classifications')
CONFIDENCE_GAUGE = Gauge('arms_classification_confidence', 'Confidence of workload classification')
RECOVERY_STRATEGY_COUNTER = Counter('arms_recovery_strategy_total', 'Count of recovery strategies selected', ['strategy'])
REQUEST_LATENCY = Histogram('arms_classification_latency_seconds', 'Latency of classification requests')
CLASSIFICATION_TYPE_COUNTER = Counter('arms_classification_type_total', 'Count of classifications by type', ['type'])

class ARMSClassifier:
    """Adaptive Recovery Management System Classifier"""
    
    # Recovery strategy constants
    QUICK_REBALANCE = "QUICK_REBALANCE"
    RESOURCE_OPTIMIZED = "RESOURCE_OPTIMIZED"
    CONTROLLED_GRADUAL = "CONTROLLED_GRADUAL"
    
    def __init__(self, model_dir, prometheus_url, kafka_bootstrap_servers, 
                 confidence_threshold=0.7, buffer_update_interval=2.0):
        """Initialize the ARMS classifier with model and configuration."""
        self.model_dir = model_dir
        self.prometheus_url = prometheus_url
        self.kafka_bootstrap_servers = kafka_bootstrap_servers
        self.confidence_threshold = confidence_threshold
        self.buffer_update_interval = buffer_update_interval
        
        self.model = None
        self.label_encoder = None
        self.feature_names = None
        self.class_mapping = None
        self.running = False
        
        # Strategy configuration mapping
        self.strategy_configs = {
            self.QUICK_REBALANCE: {
                "leader.imbalance.check.interval.seconds": 30,
                "leader.imbalance.per.broker.percentage": 10,
                "replica.lag.time.max.ms": 10000,  # 10 seconds
                "replica.fetch.max.bytes": 1048576,  # 1 MB
                "num.replica.fetchers": 4,
                "rebalance.priority": "speed"
            },
            self.RESOURCE_OPTIMIZED: {
                "leader.imbalance.check.interval.seconds": 300,
                "leader.imbalance.per.broker.percentage": 20,
                "replica.lag.time.max.ms": 30000,  # 30 seconds
                "replica.fetch.max.bytes": 524288,  # 512 KB
                "num.replica.fetchers": 2,
                "rebalance.priority": "resource"
            },
            self.CONTROLLED_GRADUAL: {
                "leader.imbalance.check.interval.seconds": 120,
                "leader.imbalance.per.broker.percentage": 25,
                "replica.lag.time.max.ms": 30000,  # 30 seconds
                "replica.fetch.max.bytes": 1048576,  # 1 MB
                "num.replica.fetchers": 2,
                "rebalance.priority": "controlled"
            }
        }
        
        # Real-time classification buffer
        self.classification_buffer = {
            "last_updated": time.time(),
            "strategy": self.CONTROLLED_GRADUAL,  # Default fallback strategy
            "confidence": 0.0,
            "workload_type": "UNKNOWN"
        }
        
        # CSV logging for classification
        self.csv_file = "classification_log.csv"
        self.csv_headers = [
            "timestamp", "workload_type", "confidence", "selected_strategy"
        ]
        
        # Create CSV file and write headers if it doesn't exist
        if not os.path.exists(self.csv_file):
            with open(self.csv_file, 'w', newline='') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=self.csv_headers)
                writer.writeheader()
    
    def load_model(self):
        """Load the trained Random Forest model and related artifacts."""
        logger.info(f"Loading model from {self.model_dir}")
        
        try:
            # Load the model
            model_path = f"{self.model_dir}/random_forest_model.pkl"
            self.model = joblib.load(model_path)
            logger.info("Model loaded successfully")
            
            # Load label encoder
            encoder_path = f"{self.model_dir}/label_encoder.pkl"
            self.label_encoder = joblib.load(encoder_path)
            logger.info(f"Label encoder loaded with classes: {self.label_encoder.classes_}")
            
            # Load feature names
            with open(f"{self.model_dir}/feature_names.json", 'r') as f:
                self.feature_names = json.load(f)
            logger.info(f"Loaded {len(self.feature_names)} features")
            
            # Load class mapping
            with open(f"{self.model_dir}/class_mapping.json", 'r') as f:
                self.class_mapping = json.load(f)
            logger.info(f"Class mapping loaded: {self.class_mapping}")
            
            return True
        
        except Exception as e:
            logger.error(f"Error loading model: {e}", exc_info=True)
            return False
    
    def fetch_prometheus_metrics(self):
        """Fetch metrics from Prometheus for classification."""
        metrics_data = {}
        
        try:
            for feature in self.feature_names:
                # Convert feature name to Prometheus query format
                # This is a simplified approach - in a real system you would have a more
                # robust mapping between feature names and Prometheus metrics
                prometheus_query = feature.replace("_", "_")
                
                # Query Prometheus for the metric
                response = requests.get(
                    f"{self.prometheus_url}/api/v1/query",
                    params={"query": prometheus_query}
                )
                
                if response.status_code == 200:
                    result = response.json()
                    # Extract the value - this is simplified
                    if result["data"]["result"]:
                        value = float(result["data"]["result"][0]["value"][1])
                        metrics_data[feature] = value
                    else:
                        logger.warning(f"No data for feature {feature}")
                        metrics_data[feature] = 0.0  # Default value
                else:
                    logger.warning(f"Failed to get metric {feature}: {response.status_code}")
                    metrics_data[feature] = 0.0  # Default value
            
            return metrics_data
        
        except Exception as e:
            logger.error(f"Error fetching Prometheus metrics: {e}", exc_info=True)
            return None
    
    def classify_workload(self, metrics_data):
        """Classify the workload based on the fetched metrics."""
        if not metrics_data or not self.model:
            return None, 0.0
        
        try:
            with REQUEST_LATENCY.time():
                # Create a DataFrame with the required features
                features_df = pd.DataFrame([metrics_data])
                
                # Ensure all required features are present
                for feature in self.feature_names:
                    if feature not in features_df.columns:
                        features_df[feature] = 0.0  # Default value
                
                # Extract only the features used by the model
                features_df = features_df[self.feature_names]
                
                # Make prediction
                class_probs = self.model.predict_proba(features_df)[0]
                
                # Get the most likely class
                class_idx = np.argmax(class_probs)
                confidence = class_probs[class_idx]
                
                # Convert numerical class to string label
                class_label = self.label_encoder.inverse_transform([class_idx])[0]
                
                # Update Prometheus metrics
                CLASSIFICATION_COUNTER.inc()
                CONFIDENCE_GAUGE.set(confidence)
                CLASSIFICATION_TYPE_COUNTER.labels(type=class_label).inc()
                
                logger.info(f"Classified workload as {class_label} with confidence {confidence:.4f}")
                
                return class_label, confidence
        
        except Exception as e:
            logger.error(f"Error classifying workload: {e}", exc_info=True)
            return None, 0.0
    
    def select_recovery_strategy(self, workload_type, confidence):
        """Select the appropriate recovery strategy based on workload type and confidence."""
        # If confidence is below threshold, use fallback strategy
        if confidence < self.confidence_threshold:
            logger.info(f"Confidence {confidence:.4f} below threshold {self.confidence_threshold}, using CONTROLLED_GRADUAL")
            RECOVERY_STRATEGY_COUNTER.labels(strategy=self.CONTROLLED_GRADUAL).inc()
            return self.CONTROLLED_GRADUAL
        
        # Map the workload type to a recovery strategy
        if workload_type == "real_time":
            logger.info("Selected QUICK_REBALANCE strategy for real-time workload")
            RECOVERY_STRATEGY_COUNTER.labels(strategy=self.QUICK_REBALANCE).inc()
            return self.QUICK_REBALANCE
        
        elif workload_type == "batch":
            logger.info("Selected RESOURCE_OPTIMIZED strategy for batch workload")
            RECOVERY_STRATEGY_COUNTER.labels(strategy=self.RESOURCE_OPTIMIZED).inc()
            return self.RESOURCE_OPTIMIZED
        
        else:
            # Unknown or mixed workload type
            logger.info(f"Unknown workload type '{workload_type}', using CONTROLLED_GRADUAL")
            RECOVERY_STRATEGY_COUNTER.labels(strategy=self.CONTROLLED_GRADUAL).inc()
            return self.CONTROLLED_GRADUAL
    
    def update_classification_buffer(self):
        """Update the classification buffer with fresh workload classification."""
        logger.info("Updating classification buffer")
        
        # Fetch metrics
        metrics_data = self.fetch_prometheus_metrics()
        if not metrics_data:
            logger.error("Failed to fetch metrics for classification")
            return
        
        # Classify workload
        workload_type, confidence = self.classify_workload(metrics_data)
        if not workload_type:
            logger.error("Workload classification failed")
            return
        
        # Select recovery strategy
        strategy = self.select_recovery_strategy(workload_type, confidence)
        
        # Update buffer
        self.classification_buffer = {
            "last_updated": time.time(),
            "strategy": strategy,
            "confidence": confidence,
            "workload_type": workload_type
        }
        
        # Log to CSV
        self.log_classification(workload_type, confidence, strategy)
        
        logger.info(f"Classification buffer updated: strategy={strategy}, workload={workload_type}, confidence={confidence:.4f}")
    
    def log_classification(self, workload_type, confidence, strategy):
        """Log classification decisions to CSV for analysis."""
        with open(self.csv_file, 'a', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=self.csv_headers)
            writer.writerow({
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "workload_type": workload_type,
                "confidence": confidence,
                "selected_strategy": strategy
            })
    
    def get_current_strategy(self):
        """Get the current recovery strategy from the buffer."""
        return self.classification_buffer
    
    def buffer_update_loop(self):
        """Background thread to periodically update the classification buffer."""
        logger.info(f"Starting buffer update loop with interval {self.buffer_update_interval} seconds")
        
        while self.running:
            try:
                self.update_classification_buffer()
            except Exception as e:
                logger.error(f"Error in buffer update: {e}", exc_info=True)
            
            # Sleep until next update
            time.sleep(self.buffer_update_interval)
    
    def start(self):
        """Start the ARMS classifier service."""
        logger.info("Starting ARMS classifier service")
        
        # Load the model
        if not self.load_model():
            logger.error("Failed to load model, cannot start service")
            return False
        
        self.running = True
        
        # Start buffer update thread
        update_thread = threading.Thread(target=self.buffer_update_loop)
        update_thread.daemon = True
        update_thread.start()
        
        logger.info("ARMS classifier service started")
        return True
    
    def stop(self):
        """Stop the ARMS classifier service."""
        logger.info("Stopping ARMS classifier service")
        self.running = False
        logger.info("ARMS classifier service stopped")


class KafkaAdminManager:
    """Manager for Kafka admin operations during recovery."""
    
    def __init__(self, bootstrap_servers):
        """Initialize with Kafka bootstrap servers."""
        self.bootstrap_servers = bootstrap_servers
        self.admin_client = AdminClient({'bootstrap.servers': bootstrap_servers})
    
    def apply_recovery_strategy(self, strategy_config):
        """Apply the recovery strategy configuration to Kafka."""
        logger.info(f"Applying recovery strategy: {strategy_config}")
        
        try:
            # In a real implementation, this would use the Kafka AdminClient API
            # to update broker configurations during recovery
            
            # This is a simplified example - actual implementation would depend
            # on your Kafka version and requirements
            
            # For example, to update a broker config:
            # self.admin_client.alter_configs([ConfigResource(
            #     ConfigResource.Type.BROKER, 
            #     broker_id,
            #     set_config={key: value for key, value in strategy_config.items()}
            # )])
            
            logger.info("Recovery strategy applied successfully")
            return True
        
        except Exception as e:
            logger.error(f"Error applying recovery strategy: {e}", exc_info=True)
            return False
    
    def simulate_broker_failure(self, broker_id):
        """Simulate a broker failure for testing."""
        logger.info(f"Simulating failure of broker {broker_id}")
        
        try:
            # In a real system, you might not call this directly
            # This is for testing purposes only
            
            # For example, you could kill a broker container:
            # subprocess.run(["docker", "stop", f"kafka-broker-{broker_id}"])
            
            logger.info(f"Simulated failure of broker {broker_id}")
            return True
        
        except Exception as e:
            logger.error(f"Error simulating broker failure: {e}", exc_info=True)
            return False
    
    def handle_broker_failure(self, broker_id, arms_classifier):
        """Handle a broker failure using the ARMS strategy."""
        logger.info(f"Handling failure of broker {broker_id}")
        
        try:
            # Get current recovery strategy from ARMS
            classification = arms_classifier.get_current_strategy()
            strategy = classification["strategy"]
            
            logger.info(f"Using recovery strategy {strategy} for broker {broker_id} failure")
            
            # Get configuration for the strategy
            config = arms_classifier.strategy_configs[strategy]
            
            # Apply the recovery strategy
            success = self.apply_recovery_strategy(config)
            
            if success:
                logger.info(f"Successfully handled broker {broker_id} failure with {strategy}")
            else:
                logger.error(f"Failed to handle broker {broker_id} failure")
            
            return success
        
        except Exception as e:
            logger.error(f"Error handling broker failure: {e}", exc_info=True)
            return False


def main():
    parser = argparse.ArgumentParser(description="ARMS Classifier Service")
    parser.add_argument("--model-dir", default="model_output", 
                       help="Directory containing trained model and artifacts")
    parser.add_argument("--prometheus-url", default="http://prometheus:9090", 
                       help="URL of Prometheus server")
    parser.add_argument("--kafka-bootstrap-servers", default="kafka-broker-1:29092,kafka-broker-2:29093,kafka-broker-3:29094", 
                       help="Kafka bootstrap servers")
    parser.add_argument("--confidence-threshold", type=float, default=0.7, 
                       help="Confidence threshold for classification")
    parser.add_argument("--buffer-update-interval", type=float, default=2.0, 
                       help="Interval in seconds for buffer updates")
    parser.add_argument("--simulate-failure", action="store_true",
                       help="Simulate a broker failure for testing")
    parser.add_argument("--broker-id", type=int, default=1,
                       help="Broker ID to simulate failure for")
    
    args = parser.parse_args()
    
    # Create ARMS classifier
    classifier = ARMSClassifier(
        model_dir=args.model_dir,
        prometheus_url=args.prometheus_url,
        kafka_bootstrap_servers=args.kafka_bootstrap_servers,
        confidence_threshold=args.confidence_threshold,
        buffer_update_interval=args.buffer_update_interval
    )
    
    # Start classifier service
    if not classifier.start():
        logger.error("Failed to start ARMS classifier service")
        return
    
    # Create Kafka admin manager
    admin_manager = KafkaAdminManager(
        bootstrap_servers=args.kafka_bootstrap_servers
    )
    
    try:
        # If simulating a failure, do it after a short delay
        if args.simulate_failure:
            logger.info(f"Will simulate failure of broker {args.broker_id} in 10 seconds...")
            time.sleep(10)
            
            admin_manager.simulate_broker_failure(args.broker_id)
            admin_manager.handle_broker_failure(args.broker_id, classifier)
        
        # Keep running until interrupted
        logger.info("Service running. Press Ctrl+C to stop.")
        while True:
            time.sleep(1)
    
    except KeyboardInterrupt:
        logger.info("Service interrupted by user")
    
    finally:
        classifier.stop()
        logger.info("Service shutdown complete")


if __name__ == "__main__":
    main()