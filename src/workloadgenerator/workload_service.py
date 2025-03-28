import json
import time
import argparse
import threading
from typing import Dict

from confluent_kafka import Consumer, Producer

from src.common.models import WorkloadType, ExperimentConfig
from src.common.utils import setup_logging, get_timestamp, json_serialize
from src.workloadgenerator.generator import WorkloadGenerator
from src.workloadgenerator.templates import create_workload

# Set up logging
logger = setup_logging(__name__)

# Topics for control and monitoring
CONTROL_TOPIC = "arms-experiment-control"
METRICS_TOPIC = "arms-workload-metrics"

class WorkloadService:
    """Service for managing workload generation based on control messages"""
    
    def __init__(self, bootstrap_servers: str):
        """
        Initialize the workload generation service
        
        Args:
            bootstrap_servers: Kafka bootstrap server string
        """
        self.bootstrap_servers = bootstrap_servers
        self.generator = WorkloadGenerator(bootstrap_servers)
        self.active_workloads = {}
        self.running = False
        
        # Create Kafka producer for metrics
        self.producer = Producer({
            'bootstrap.servers': bootstrap_servers,
            'client.id': 'arms-workload-metrics-producer'
        })
        
        # Create Kafka consumer for control messages
        self.consumer = Consumer({
            'bootstrap.servers': bootstrap_servers,
            'group.id': 'arms-workload-service',
            'auto.offset.reset': 'latest',
            'enable.auto.commit': True,
        })
        
        # Subscribe to control topic
        self.consumer.subscribe([CONTROL_TOPIC])
    
    def send_metrics(self, data: Dict):
        """Send metrics to the metrics topic"""
        try:
            # Add timestamp if not present
            if 'timestamp' not in data:
                data['timestamp'] = get_timestamp()
                
            # Send to Kafka
            self.producer.produce(
                METRICS_TOPIC,
                value=json.dumps(data, default=json_serialize).encode('utf-8')
            )
            self.producer.flush()
        except Exception as e:
            logger.error(f"Error sending metrics: {e}")
    
    def process_control_message(self, message: Dict):
        """
        Process a control message to start or stop workloads
        
        Args:
            message: The control message
        """
        try:
            command = message.get('command')
            
            if command == 'start_workload':
                # Extract experiment configuration
                config_dict = message.get('config', {})
                
                # Convert workload_type string to enum if needed
                if 'workload_type' in config_dict and isinstance(config_dict['workload_type'], str):
                    config_dict['workload_type'] = WorkloadType(config_dict['workload_type'])
                
                experiment_config = ExperimentConfig(**config_dict)
                
                # Create workload configuration
                workload_config = create_workload(
                    workload_type=experiment_config.workload_type,
                    workload_size=experiment_config.workload_size,
                    duration_seconds=experiment_config.duration_minutes * 60,
                    topic_name=f"workload-{experiment_config.experiment_id}"
                )
                
                # Start the workload
                workload_id = self.generator.start_workload_async(workload_config)
                self.active_workloads[workload_id] = workload_config
                
                # Report status
                self.send_metrics({
                    'event': 'workload_started',
                    'workload_id': workload_id,
                    'experiment_id': experiment_config.experiment_id,
                    'timestamp': get_timestamp()
                })
                
                logger.info(f"Started workload {workload_id} for experiment {experiment_config.experiment_id}")
                
            elif command == 'stop_workload':
                workload_id = message.get('workload_id')
                if workload_id in self.active_workloads:
                    # Individual workload stopping would require additional implementation
                    logger.info(f"Received request to stop workload {workload_id}, but individual stopping not implemented")
                
            elif command == 'stop_all_workloads':
                # Stop all workloads
                self.generator.stop_all_workloads()
                self.active_workloads.clear()
                
                # Report status
                self.send_metrics({
                    'event': 'all_workloads_stopped',
                    'timestamp': get_timestamp()
                })
                
                logger.info("Stopped all workloads")
                
            else:
                logger.warning(f"Unknown command: {command}")
                
        except Exception as e:
            logger.error(f"Error processing control message: {e}")
    
    def receive_control_message(self):
        """
        Poll for and process control messages
        
        Returns:
            True if a message was processed, False otherwise
        """
        try:
            # Poll for messages with timeout
            msg = self.consumer.poll(1.0)
            
            if msg is None:
                return False
                
            if msg.error():
                logger.error(f"Consumer error: {msg.error()}")
                return False
                
            # Parse message
            try:
                message = json.loads(msg.value().decode('utf-8'))
                self.process_control_message(message)
                return True
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON in control message: {msg.value()}")
                return False
                
        except Exception as e:
            logger.error(f"Error receiving control message: {e}")
            return False
    
    def run(self):
        """Run the workload service main loop"""
        self.running = True
        logger.info("Starting workload service")
        
        try:
            while self.running:
                # Poll for control messages
                self.receive_control_message()
                
                # Sleep briefly to avoid tight polling
                time.sleep(0.1)
                
        except KeyboardInterrupt:
            logger.info("Workload service interrupted")
        finally:
            # Clean up resources
            self.running = False
            self.generator.stop_all_workloads()
            self.consumer.close()
            logger.info("Workload service stopped")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='ARMS Workload Generation Service')
    parser.add_argument('--bootstrap-servers', default='kafka-1:9092,kafka-2:9092,kafka-3:9092',
                        help='Kafka bootstrap servers')
    args = parser.parse_args()
    
    # Start the service
    service = WorkloadService(args.bootstrap_servers)
    service.run()