import json
import time
import argparse
import threading
from typing import Dict, Any

from confluent_kafka import Consumer, Producer

from src.common.utils import setup_logging, get_timestamp, json_serialize, receive_message, send_message
from src.classifier.classifier import WorkloadClassifier

# Set up logging
logger = setup_logging(__name__)

# Topics for communication
FEATURES_TOPIC = "arms-features"
CLASSIFICATION_TOPIC = "arms-classifications"

class ClassifierService:
    """Service for classifying workloads based on features"""
    
    def __init__(self, bootstrap_servers: str, model_path: str = "models/workload_classifier.joblib"):
        """
        Initialize the classifier service
        
        Args:
            bootstrap_servers: Kafka bootstrap servers string
            model_path: Path to the trained classifier model
        """
        self.bootstrap_servers = bootstrap_servers
        
        # Initialize classifier
        self.classifier = WorkloadClassifier(model_path)
        
        # Create Kafka consumer for features
        self.consumer = Consumer({
            'bootstrap.servers': bootstrap_servers,
            'group.id': 'arms-classifier-service',
            'auto.offset.reset': 'latest',
            'enable.auto.commit': True,
        })
        
        # Create Kafka producer for classifications
        self.producer = Producer({
            'bootstrap.servers': bootstrap_servers,
            'client.id': 'arms-classifier-producer'
        })
        
        # Subscribe to features topic
        self.consumer.subscribe([FEATURES_TOPIC])
        
        # Service state
        self.running = False
        
    def process_features(self, features_message: Dict[str, Any]) -> None:
        """
        Process features message and publish classification
        
        Args:
            features_message: Features message from Kafka
        """
        try:
            # Extract features
            features = features_message.get('features', {})
            workload_id = features_message.get('workload_id', 'unknown')
            
            # Classify workload
            classification = self.classifier.classify(features)
            
            # Prepare classification message
            classification_message = {
                'workload_id': workload_id,
                'classification': classification,
                'timestamp': get_timestamp()
            }
            
            # Send classification to Kafka
            send_message(CLASSIFICATION_TOPIC, classification_message, self.producer)
            
            logger.info(f"Published classification for workload {workload_id}: "
                        f"{classification.workload_type.value} with {classification.confidence:.2f} confidence")
                        
        except Exception as e:
            logger.error(f"Error processing features: {e}")
    
    def run(self) -> None:
        """Run the classifier service main loop"""
        self.running = True
        logger.info("Starting classifier service")
        
        try:
            while self.running:
                # Poll for features messages
                message = receive_message(self.consumer, timeout_ms=1000)
                
                if message:
                    self.process_features(message)
                    
                # Sleep briefly to avoid tight polling
                time.sleep(0.1)
                
        except KeyboardInterrupt:
            logger.info("Classifier service interrupted")
        finally:
            # Clean up resources
            self.running = False
            self.consumer.close()
            logger.info("Classifier service stopped")
            
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='ARMS Classifier Service')
    parser.add_argument('--bootstrap-servers', default='kafka-1:9092,kafka-2:9092,kafka-3:9092',
                      help='Kafka bootstrap servers')
    parser.add_argument('--model-path', default='models/workload_classifier.joblib',
                      help='Path to trained model')
    
    args = parser.parse_args()
    
    # Start the service
    service = ClassifierService(args.bootstrap_servers, args.model_path)
    service.run()