import json
import time
import argparse
import threading
from typing import Dict, Any

from confluent_kafka import Producer
from src.common.utils import setup_logging, get_timestamp, json_serialize
from src.monitor.collectors import MetricsCollectorManager
from src.monitor.features import FeatureExtractor

# Set up logging
logger = setup_logging(__name__)

# Topics for sending metrics and features
METRICS_TOPIC = "arms-metrics"
FEATURES_TOPIC = "arms-features"

class MonitorService:
    """Service for monitoring Kafka and extracting features"""
    
    def __init__(self, bootstrap_servers: str, collection_interval_seconds: int = 5):
        """
        Initialize the monitoring service
        
        Args:
            bootstrap_servers: Kafka bootstrap server string
            collection_interval_seconds: How often to collect metrics (in seconds)
        """
        self.bootstrap_servers = bootstrap_servers
        self.collection_interval = collection_interval_seconds
        self.running = False
        
        # Initialize metric collectors
        self.metrics_manager = MetricsCollectorManager(bootstrap_servers)
        
        # Initialize feature extractor with 60-second window (12 samples at 5-second intervals)
        self.feature_extractor = FeatureExtractor(window_size=12)
        
        # Initialize Kafka producer for sending metrics and features
        self.producer = Producer({
            'bootstrap.servers': bootstrap_servers,
            'client.id': 'arms-monitor-service'
        })
    
    def collect_and_process_metrics(self):
        """Collect metrics, extract features, and send to Kafka"""
        try:
            # Collect metrics from all sources
            metrics = self.metrics_manager.collect_all_metrics()
            
            # Send raw metrics to Kafka for storage
            self.send_to_kafka(METRICS_TOPIC, {
                'event_type': 'metrics',
                'timestamp': get_timestamp(),
                'data': metrics
            })
            
            # Add metrics to feature extractor
            self.feature_extractor.add_metrics(metrics)
            
            # Extract features if we have enough data
            features = self.feature_extractor.extract_features()
            if features:
                # Send features to Kafka for classification
                self.send_to_kafka(FEATURES_TOPIC, {
                    'event_type': 'features',
                    'timestamp': get_timestamp(),
                    'data': features
                })
                logger.debug(f"Extracted features: {features}")
            
        except Exception as e:
            logger.error(f"Error in metrics collection and processing: {e}")
    
    def send_to_kafka(self, topic: str, data: Dict[str, Any]):
        """
        Send data to a Kafka topic
        
        Args:
            topic: Topic to send to
            data: Data to send
        """
        try:
            # Convert data to JSON
            json_data = json.dumps(data, default=json_serialize)
            
            # Send to Kafka
            self.producer.produce(
                topic,
                value=json_data.encode('utf-8')
            )
            
            # Occasional flush
            self.producer.poll(0)
            
        except Exception as e:
            logger.error(f"Error sending to Kafka topic {topic}: {e}")
    
    def run_collection_loop(self):
        """Run the metric collection loop"""
        logger.info(f"Starting metric collection loop (interval: {self.collection_interval}s)")
        
        while self.running:
            start_time = time.time()
            
            # Collect and process metrics
            self.collect_and_process_metrics()
            
            # Calculate sleep time to maintain consistent interval
            elapsed = time.time() - start_time
            sleep_time = max(0.1, self.collection_interval - elapsed)
            
            # Sleep until next collection
            time.sleep(sleep_time)
            
        logger.info("Metric collection loop stopped")
    
    def start(self):
        """Start the monitoring service"""
        if self.running:
            logger.warning("Monitor service is already running")
            return
            
        self.running = True
        
        # Start collection loop in a separate thread
        self.collection_thread = threading.Thread(
            target=self.run_collection_loop,
            name="metric-collection-thread"
        )
        self.collection_thread.daemon = True
        self.collection_thread.start()
        
        logger.info("Monitor service started")
    
    def stop(self):
        """Stop the monitoring service"""
        if not self.running:
            logger.warning("Monitor service is not running")
            return
            
        self.running = False
        
        # Wait for collection thread to stop
        if hasattr(self, 'collection_thread') and self.collection_thread.is_alive():
            self.collection_thread.join(timeout=2 * self.collection_interval)
        
        # Final flush of producer
        self.producer.flush()
        
        logger.info("Monitor service stopped")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='ARMS Monitoring Service')
    parser.add_argument('--bootstrap-servers', default='kafka-1:9092,kafka-2:9092,kafka-3:9092',
                        help='Kafka bootstrap servers')
    parser.add_argument('--interval', type=int, default=5,
                        help='Metric collection interval in seconds')
    args = parser.parse_args()
    
    # Create and start the service
    service = MonitorService(args.bootstrap_servers, args.interval)
    
    try:
        service.start()
        
        # Keep main thread running
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Stopping due to keyboard interrupt")
    finally:
        service.stop()