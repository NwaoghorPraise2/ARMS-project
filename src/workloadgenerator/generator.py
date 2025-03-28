import json
import random
import time
import threading
import logging
import numpy as np
from typing import Dict, Any
from confluent_kafka import Producer
from confluent_kafka.admin import AdminClient, NewTopic

from src.common.models import WorkloadType
from src.common.utils import setup_logging, get_timestamp

# Set up logging
logger = setup_logging(__name__)


class WorkloadConfig:
    """Configuration for a synthetic workload"""
    
    def __init__(self, 
                 workload_type: WorkloadType,
                 workload_size: str,
                 message_rate: float,
                 message_size_mean: int,
                 message_size_stddev: int,
                 burst_factor: float = 1.0,
                 burst_frequency: int = 0,
                 duration_seconds: int = 600,
                 topic_name: str = None):
        """
        Initialize workload configuration
        
        Args:
            workload_type: Type of workload (batch or real-time)
            workload_size: Size category (small, medium, large for batch; low, medium, high for real-time)
            message_rate: Base messages per second
            message_size_mean: Average message size in bytes
            message_size_stddev: Standard deviation of message size
            burst_factor: Factor to increase message rate during bursts
            burst_frequency: How often bursts occur (0 for no bursts)
            duration_seconds: Duration of the workload in seconds
            topic_name: Kafka topic name (generated if None)
        """
        self.workload_type = workload_type
        self.workload_size = workload_size
        self.message_rate = message_rate
        self.message_size_mean = message_size_mean
        self.message_size_stddev = message_size_stddev
        self.burst_factor = burst_factor
        self.burst_frequency = burst_frequency
        self.duration_seconds = duration_seconds
        self.topic_name = topic_name or f"{workload_type.value}_{workload_size}_{int(time.time())}"
        # Create unique ID for this workload
        self.id = f"{self.topic_name}_{get_timestamp()}"


class WorkloadGenerator:
    """Generator for synthetic AI workloads"""
    
    def __init__(self, 
                 bootstrap_servers: str,
                 num_partitions: int = 6,
                 replication_factor: int = 3):
        """
        Initialize the workload generator
        
        Args:
            bootstrap_servers: Kafka bootstrap server string
            num_partitions: Number of partitions for created topics
            replication_factor: Replication factor for created topics
        """
        self.bootstrap_servers = bootstrap_servers
        self.num_partitions = num_partitions
        self.replication_factor = replication_factor
        
        # Initialize Kafka admin client for topic management
        self.admin_client = AdminClient({'bootstrap.servers': bootstrap_servers})
        
        # Initialize Kafka producer configuration
        self.producer_config = {
            'bootstrap.servers': bootstrap_servers,
            'client.id': 'arms-workload-generator',
            'batch.size': 131072,  # 128KB batches
            'linger.ms': 5,  # Small batching delay
            'compression.type': 'snappy',  # Use compression
            'acks': 'all'  # Wait for all replicas
        }
        
        self.running = False
        self.threads = []
    
    def create_topic(self, topic_name: str) -> bool:
        """
        Create a Kafka topic for the workload
        
        Args:
            topic_name: Name of the topic to create
            
        Returns:
            True if topic creation was successful or topic exists
        """
        try:
            # Check if topic already exists
            topics_metadata = self.admin_client.list_topics(timeout=10)
            if topic_name in topics_metadata.topics:
                logger.info(f"Topic {topic_name} already exists")
                return True
            
            # Create new topic with specified partitions and replication
            new_topics = [NewTopic(
                topic_name,
                num_partitions=self.num_partitions,
                replication_factor=self.replication_factor
            )]
            
            # Submit topic creation request
            result = self.admin_client.create_topics(new_topics)
            
            # Wait for operation to complete
            for topic, future in result.items():
                try:
                    future.result()
                    logger.info(f"Topic {topic} created successfully")
                except Exception as e:
                    if "TopicExistsError" in str(e):
                        logger.info(f"Topic {topic} already exists")
                        return True
                    logger.error(f"Failed to create topic {topic}: {e}")
                    return False
            
            return True
        except Exception as e:
            logger.error(f"Error creating topic: {e}")
            return False
    
    def generate_message(self, size_mean: int, size_stddev: int) -> bytes:
        """
        Generate a message with the specified size characteristics
        
        Args:
            size_mean: Target mean size in bytes
            size_stddev: Target standard deviation in bytes
            
        Returns:
            Generated message as bytes
        """
        # Generate random message size from log-normal distribution
        size = int(np.random.lognormal(np.log(size_mean), size_stddev / size_mean))
        size = max(10, min(size, 10 * size_mean))  # Clamp to reasonable range
        
        # Generate message with timestamp, ID, and payload
        message = {
            "timestamp": get_timestamp(),
            "message_id": f"{time.time()}_{random.randint(0, 1000000)}",
            # Create payload to match target size
            "payload": "X" * (size - 100)  # -100 to account for JSON overhead
        }
        
        return json.dumps(message).encode('utf-8')
    
    def generate_workload(self, config: WorkloadConfig) -> bool:
        """
        Generate and send a workload according to the provided configuration
        
        Args:
            config: WorkloadConfiguration with workload parameters
            
        Returns:
            True if workload generation was successful
        """
        # Create the topic first
        if not self.create_topic(config.topic_name):
            logger.error(f"Failed to create topic for workload {config.id}")
            return False
        
        # Create a new producer for this workload
        producer = Producer(self.producer_config)
        
        # Track start time and message count
        start_time = time.time()
        message_count = 0
        
        try:
            # Continue until the specified duration is reached
            while time.time() - start_time < config.duration_seconds and self.running:
                # Calculate current message rate (apply burst if needed)
                current_rate = config.message_rate
                if config.burst_frequency > 0:
                    # Apply burst factor periodically
                    if int((time.time() - start_time) / config.burst_frequency) % 2 == 0:
                        current_rate *= config.burst_factor
                
                # Calculate sleep time between messages
                sleep_time = 1.0 / current_rate if current_rate > 0 else 0.1
                
                # Generate and send message
                message = self.generate_message(
                    config.message_size_mean, 
                    config.message_size_stddev
                )
                
                # Add workload metadata to the message
                message_with_metadata = {
                    "workload_id": config.id,
                    "workload_type": config.workload_type.value,
                    "workload_size": config.workload_size,
                    "message_index": message_count,
                    "timestamp": get_timestamp(),
                    "data": message.decode('utf-8')
                }
                
                # Send to Kafka
                producer.produce(
                    config.topic_name,
                    key=str(message_count).encode('utf-8'),
                    value=json.dumps(message_with_metadata).encode('utf-8')
                )
                
                # Occasional flush to ensure messages are sent
                if message_count % 100 == 0:
                    producer.flush()
                
                message_count += 1
                
                # Sleep to maintain the desired message rate
                time.sleep(sleep_time)
            
            # Final flush to ensure all messages are sent
            producer.flush()
            logger.info(f"Workload {config.id} completed: {message_count} messages sent")
            return True
            
        except Exception as e:
            logger.error(f"Error generating workload {config.id}: {e}")
            return False
        finally:
            # Clean up
            producer.flush()
    
    def start_workload_async(self, config: WorkloadConfig) -> str:
        """
        Start a workload asynchronously in a separate thread
        
        Args:
            config: WorkloadConfiguration with workload parameters
            
        Returns:
            Workload ID if successfully started
        """
        self.running = True
        thread = threading.Thread(
            target=self.generate_workload, 
            args=(config,),
            name=f"workload-{config.id}"
        )
        thread.daemon = True
        thread.start()
        
        self.threads.append(thread)
        logger.info(f"Started workload {config.id} asynchronously")
        return config.id
    
    def stop_all_workloads(self):
        """Stop all running workloads"""
        logger.info("Stopping all workloads")
        self.running = False
        
        # Wait for all threads to complete
        for thread in self.threads:
            if thread.is_alive():
                thread.join(timeout=5)
        
        self.threads.clear()
        logger.info("All workloads stopped")