import os
import time
import json
import random
import logging
import argparse
from datetime import datetime
from kafka import KafkaProducer

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('WorkloadGenerator')

class WorkloadGenerator:
    def __init__(self, bootstrap_servers, workload_type):
        self.producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        self.workload_type = workload_type
        logger.info(f"WorkloadGenerator initialized for type: {workload_type}")
        
    def generate_real_time_event_driven(self, duration_seconds, topic):
        """Generate real-time event-driven workload pattern"""
        logger.info(f"Generating real-time event-driven workload for {duration_seconds} seconds")
        end_time = time.time() + duration_seconds
        message_count = 0
        
        while time.time() < end_time:
            # Real-time workload has consistent high-rate small messages
            message = {
                "id": f"msg_{message_count}",
                "timestamp": time.time(),
                "data": "x" * random.randint(100, 200),  # Small payload
                "priority": random.choice(["high", "critical"])
            }
            
            self.producer.send(topic, message)
            message_count += 1
            
            # High frequency, low jitter
            time.sleep(random.uniform(0.001, 0.005))  # 1-5ms between messages
            
            # Every 100 messages, create a burst
            if message_count % 100 == 0:
                for i in range(20):
                    burst_message = {
                        "id": f"msg_{message_count}_burst_{i}",
                        "timestamp": time.time(),
                        "data": "x" * random.randint(100, 200),
                        "priority": "critical"
                    }
                    self.producer.send(topic, burst_message)
                
                logger.info(f"Generated burst of 20 messages at count {message_count}")
        
        logger.info(f"Finished generating real-time workload, sent {message_count} messages")
                
    def generate_batch_data_intensive(self, duration_seconds, topic):
        """Generate batch data-intensive workload pattern"""
        logger.info(f"Generating batch data-intensive workload for {duration_seconds} seconds")
        end_time = time.time() + duration_seconds
        batch_count = 0
        
        while time.time() < end_time:
            # Batch workload has irregular large messages in batches
            batch_size = random.randint(50, 100)
            logger.info(f"Generating batch {batch_count} with {batch_size} messages")
            
            # Send a batch
            for i in range(batch_size):
                message = {
                    "batch_id": batch_count,
                    "message_id": i,
                    "timestamp": time.time(),
                    "data": "x" * random.randint(10000, 50000),  # Large payload
                    "priority": "normal"
                }
                self.producer.send(topic, message)
            
            batch_count += 1
            
            # Wait between batches (simulating irregular batch processing)
            sleep_time = random.uniform(5.0, 15.0)
            logger.info(f"Sleeping for {sleep_time:.2f} seconds between batches")
            time.sleep(sleep_time)  # 5-15s between batches
        
        logger.info(f"Finished generating batch workload, sent {batch_count} batches")
    
    def generate_workload(self, duration_seconds, topic):
        """Generate workload based on the specified type"""
        if self.workload_type == "real_time_event_driven":
            self.generate_real_time_event_driven(duration_seconds, topic)
        elif self.workload_type == "batch_data_intensive":
            self.generate_batch_data_intensive(duration_seconds, topic)
        else:
            logger.error(f"Unknown workload type: {self.workload_type}")
            raise ValueError(f"Unknown workload type: {self.workload_type}")
        
        self.producer.flush()

def parse_args():
    parser = argparse.ArgumentParser(description='Generate Kafka workloads for ARMS testing')
    parser.add_argument('--workload-type', default='real_time_event_driven',
                        choices=['real_time_event_driven', 'batch_data_intensive'],
                        help='Type of workload to generate')
    parser.add_argument('--duration', type=int, default=300,
                        help='Duration in seconds to generate workload')
    parser.add_argument('--topic', default='arms-test',
                        help='Kafka topic to publish messages to')
    parser.add_argument('--bootstrap-servers', default=None,
                        help='Kafka bootstrap servers')
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    
    # Get bootstrap servers from environment if not provided
    bootstrap_servers = args.bootstrap_servers
    if bootstrap_servers is None:
        bootstrap_servers = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    
    generator = WorkloadGenerator(bootstrap_servers, args.workload_type)
    
    logger.info(f"Starting workload generation: {args.workload_type} for {args.duration}s on topic {args.topic}")
    generator.generate_workload(args.duration, args.topic)
    logger.info("Workload generation complete")
