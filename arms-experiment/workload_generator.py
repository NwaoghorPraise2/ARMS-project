#!/usr/bin/env python3

import json
import time
import random
import uuid
import logging
import argparse
import threading
import datetime
from confluent_kafka import Producer
import numpy as np
import csv
import os
from prometheus_client import start_http_server, Gauge

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("workload_generator.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("workload_generator")

# Setup Prometheus metrics for monitoring the workload generator
WORKLOAD_TYPE = Gauge('workload_type', 'Current workload type (0=real-time, 1=batch)')
MESSAGE_RATE = Gauge('message_rate', 'Current message production rate')
PAYLOAD_SIZE = Gauge('payload_size', 'Average message payload size in bytes')
BATCH_SIZE = Gauge('batch_size', 'Current batch size for batch workload')

class WorkloadGenerator:
    def __init__(self, bootstrap_servers, topic_name="ai_workloads", metrics_port=8000):
        """Initialize the workload generator with Kafka connection and parameters."""
        self.bootstrap_servers = bootstrap_servers
        self.topic_name = topic_name
        self.producer = None
        self.running = False
        self.current_workload = None
        self.metrics_port = metrics_port
        
        # Stats for monitoring and logging
        self.messages_sent = 0
        self.bytes_sent = 0
        self.start_time = None
        
        # CSV logging for metrics
        self.csv_file = "workload_metrics.csv"
        self.csv_headers = [
            "timestamp", "workload_type", "message_rate", "payload_size_bytes", 
            "batch_size", "cpu_usage", "memory_usage"
        ]
        
        # Create CSV file and write headers if it doesn't exist
        if not os.path.exists(self.csv_file):
            with open(self.csv_file, 'w', newline='') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=self.csv_headers)
                writer.writeheader()
    
    def connect(self):
        """Connect to Kafka broker."""
        logger.info(f"Connecting to Kafka at {self.bootstrap_servers}")
        
        # Configure Kafka producer with settings optimized for multi-broker setup
        conf = {
            'bootstrap.servers': self.bootstrap_servers,
            'client.id': 'workload-generator',
            'acks': 'all',              # 'all' is appropriate for multi-broker setup
            'retries': 5,               
            'retry.backoff.ms': 500,    
            'linger.ms': 50,            # Batch messages for 50ms
            'compression.type': 'lz4',
            'message.timeout.ms': 30000,  # 30 seconds timeout
            'socket.keepalive.enable': True,
            'reconnect.backoff.ms': 1000,
            'reconnect.backoff.max.ms': 10000,
            'queue.buffering.max.messages': 100000,
            'batch.size': 16384,
            'max.in.flight.requests.per.connection': 5,
            'request.required.acks': -1, # Wait for all in-sync replicas

            'delivery.timeout.ms': 120000  # 2 minutes timeout for delivery
        }
        
        try:
            self.producer = Producer(conf)
            logger.info("Connected to Kafka")
            
            # Start Prometheus metrics server
            start_http_server(self.metrics_port)
            logger.info(f"Started Prometheus metrics server on port {self.metrics_port}")
        except Exception as e:
            logger.error(f"Failed to connect to Kafka: {e}")
            raise
    
    def log_metrics(self, workload_type, message_rate, payload_size, batch_size=0):
        """Log metrics to CSV file."""
        # Get basic system metrics
        cpu_usage = 0.0  # Would require psutil in a real implementation
        memory_usage = 0.0  # Would require psutil in a real implementation
        
        # Log to CSV
        with open(self.csv_file, 'a', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=self.csv_headers)
            writer.writerow({
                "timestamp": datetime.datetime.now().isoformat(),
                "workload_type": workload_type,
                "message_rate": message_rate,
                "payload_size_bytes": payload_size,
                "batch_size": batch_size,
                "cpu_usage": cpu_usage,
                "memory_usage": memory_usage
            })
        
        # Update Prometheus metrics
        WORKLOAD_TYPE.set(1 if workload_type == "batch" else 0)
        MESSAGE_RATE.set(message_rate)
        PAYLOAD_SIZE.set(payload_size)
        BATCH_SIZE.set(batch_size)
    
    def delivery_report(self, err, msg):
        """Callback for message delivery reports."""
        if err is not None:
            logger.error(f"Message delivery failed: {err}")
        else:
            self.messages_sent += 1
            self.bytes_sent += len(msg.value())
            
            # Log throughput every 1000 messages
            if self.messages_sent % 1000 == 0:
                elapsed = time.time() - self.start_time
                msg_rate = self.messages_sent / elapsed if elapsed > 0 else 0
                byte_rate = self.bytes_sent / elapsed if elapsed > 0 else 0
                
                logger.info(f"Throughput: {msg_rate:.2f} msgs/sec, {byte_rate/1024/1024:.2f} MB/sec")
    
    def generate_real_time_speech_data(self):
        """Generate simulated real-time speech recognition data."""
        # Generate a realistic speech recognition message
        speech_duration = random.uniform(0.5, 5.0)  # 0.5 to 5 seconds of speech
        sample_rate = 16000  # 16kHz sample rate
        num_channels = 1  # Mono audio
        
        # Generate realistic speech recognition confidence scores
        word_count = random.randint(5, 15)
        words = []
        for i in range(word_count):
            words.append({
                "word": f"word_{i}",
                "confidence": random.uniform(0.60, 0.99),
                "start_time": i * 0.3,
                "end_time": (i + 1) * 0.3
            })
        
        # Create message payload
        message = {
            # Taxonomy fields for classification
            "taxonomy": {
                "latency_sensitivity": "real_time",
                "data_criticality": "mission_critical",
                "processing_pattern": "event_driven",
                "resource_intensity": "compute_intensive"
            },
            
            # Speech recognition data
            "metadata": {
                "source_id": str(uuid.uuid4()),
                "timestamp": datetime.datetime.now().isoformat(),
                "sample_rate": sample_rate,
                "num_channels": num_channels,
                "duration_seconds": speech_duration,
                "format": "PCM16"
            },
            
            # Recognition results
            "results": {
                "transcript": " ".join([w["word"] for w in words]),
                "confidence": random.uniform(0.75, 0.98),
                "words": words,
                "language": "en-US"
            },
            
            # Add some variable size data to simulate actual audio features
            "features": {
                "mfcc": [random.random() for _ in range(random.randint(10, 30))],
                "audio_embeddings": [random.random() for _ in range(random.randint(50, 100))]
            }
        }
        
        return message
    
    def generate_batch_speech_data(self, batch_id):
        """Generate simulated batch speech recognition data."""
        # Simulate batch processing of audio files (e.g., for model training)
        
        # Create a larger payload with more comprehensive data
        sample_rate = 16000  # 16kHz sample rate
        num_channels = 1  # Mono audio
        
        # Generate a longer transcript (to increase payload size)
        paragraph_length = random.randint(100, 300)
        words = []
        transcript = ""
        
        for i in range(paragraph_length):
            word = f"word_{i}"
            confidence = random.uniform(0.70, 0.99)
            start_time = i * 0.3
            end_time = (i + 1) * 0.3
            
            words.append({
                "word": word,
                "confidence": confidence,
                "start_time": start_time,
                "end_time": end_time
            })
            
            transcript += word + " "
        
        # Create a larger message payload
        message = {
            # Taxonomy fields for classification
            "taxonomy": {
                "latency_sensitivity": "batch",
                "data_criticality": "business_critical",
                "processing_pattern": "batch",
                "resource_intensity": "io_intensive"
            },
            
            # Batch processing metadata
            "batch_metadata": {
                "batch_id": batch_id,
                "timestamp": datetime.datetime.now().isoformat(),
                "processing_pipeline": "speech_recognition_training",
                "total_files": random.randint(500, 1500),
                "compression_type": "gzip",
                "format_version": "2.0",
                "priority": random.choice(["low", "medium", "high"])
            },
            
            # Audio metadata
            "audio_metadata": {
                "file_id": str(uuid.uuid4()),
                "sample_rate": sample_rate,
                "num_channels": num_channels,
                "duration_seconds": paragraph_length * 0.3,
                "format": "FLAC"
            },
            
            # Recognition results
            "results": {
                "transcript": transcript,
                "confidence": random.uniform(0.80, 0.95),
                "words": words,
                "language": "en-US"
            },
            
            # Add large arrays to simulate feature extraction results
            "features": {
                "mfcc": [random.random() for _ in range(random.randint(200, 500))],
                "audio_embeddings": [random.random() for _ in range(random.randint(500, 1000))],
                "spectrogram": [
                    [random.random() for _ in range(random.randint(50, 100))] 
                    for _ in range(random.randint(20, 40))
                ]
            }
        }
        
        return message
    
    def run_real_time_workload(self, duration_seconds=7200):
        """Run real-time event-driven workload for specified duration (default 2 hours)."""
        logger.info(f"Starting real-time event-driven workload for {duration_seconds} seconds")
        self.current_workload = "real_time"
        self.start_time = time.time()
        self.messages_sent = 0
        self.bytes_sent = 0
        
        end_time = time.time() + duration_seconds
        # With 3 brokers, we can handle more messages
        message_rate = 1200  # Increased for multi-broker setup
        inter_message_delay = 1.0 / message_rate
        
        batch_counter = 0  # For logging purposes
        total_payload_size = 0
        
        while time.time() < end_time and self.running:
            batch_start = time.time()
            batch_size = min(50, int(message_rate / 20))
            
            batch_payload_size = 0
            for _ in range(batch_size):
                message = self.generate_real_time_speech_data()
                message_json = json.dumps(message)
                batch_payload_size += len(message_json)
                
                try:
                    self.producer.produce(
                        self.topic_name,
                        key=str(uuid.uuid4()),
                        value=message_json.encode('utf-8'),
                        callback=self.delivery_report
                    )
                except BufferError:
                    # If the local buffer is full, wait a bit and retry
                    logger.warning("Local buffer full, waiting...")
                    self.producer.poll(1)
                    # Retry producing the message
                    self.producer.produce(
                        self.topic_name,
                        key=str(uuid.uuid4()),
                        value=message_json.encode('utf-8'),
                        callback=self.delivery_report
                    )
            
            # Poll to handle callbacks
            self.producer.poll(0)
            
            # Flush every batch to ensure delivery
            remaining = self.producer.flush(timeout=5.0)
            if remaining > 0:
                logger.warning(f"{remaining} messages still in queue after flush")
            
            batch_counter += 1
            total_payload_size += batch_payload_size
            avg_payload_size = batch_payload_size / batch_size
            
            # Log metrics every 10 batches
            if batch_counter % 10 == 0:
                self.log_metrics(
                    workload_type="real_time",
                    message_rate=message_rate,
                    payload_size=avg_payload_size,
                    batch_size=0  # Not a batch workload
                )
                logger.info(f"Real-time workload: Sent {batch_size} messages, avg payload size: {avg_payload_size:.0f} bytes")
            
            # Calculate how long to sleep to maintain the target message rate
            batch_duration = time.time() - batch_start
            sleep_time = max(0, (batch_size * inter_message_delay) - batch_duration)
            if sleep_time > 0:
                time.sleep(sleep_time)
        
        logger.info(f"Completed real-time workload. Sent {self.messages_sent} messages")
    
    def run_batch_workload(self, duration_seconds=3600):
        """Run batch data-intensive workload for specified duration (default 1 hour)."""
        logger.info(f"Starting batch data-intensive workload for {duration_seconds} seconds")
        self.current_workload = "batch"
        self.start_time = time.time()
        self.messages_sent = 0
        self.bytes_sent = 0
        
        end_time = time.time() + duration_seconds
        batch_interval = 90  # Interval between batches
        
        batch_id = 0
        
        while time.time() < end_time and self.running:
            batch_start = time.time()
            
            # With 3 brokers, can handle larger batches
            batch_size = random.randint(8000, 20000)
            logger.info(f"Sending batch #{batch_id} with {batch_size} messages")
            
            batch_payload_size = 0
            for i in range(batch_size):
                message = self.generate_batch_speech_data(batch_id)
                message_json = json.dumps(message)
                batch_payload_size += len(message_json)
                
                try:
                    self.producer.produce(
                        self.topic_name,
                        key=f"batch-{batch_id}-{i}",
                        value=message_json.encode('utf-8'),
                        callback=self.delivery_report
                    )
                except BufferError:
                    # Handle buffer errors
                    logger.warning("Local buffer full, flushing and retrying...")
                    self.producer.poll(1)
                    self.producer.produce(
                        self.topic_name,
                        key=f"batch-{batch_id}-{i}",
                        value=message_json.encode('utf-8'),
                        callback=self.delivery_report
                    )
                
                # Poll to handle callbacks
                if i % 100 == 0:
                    self.producer.poll(0)
                
                # Flush every 1000 messages
                if i % 1000 == 0 and i > 0:
                    remaining = self.producer.flush(timeout=5.0)
                    if remaining > 0:
                        logger.warning(f"{remaining} messages still in queue after flush")
            
            # Final flush to ensure all messages are sent
            remaining = self.producer.flush(timeout=10.0)
            if remaining > 0:
                logger.warning(f"{remaining} messages still in queue after final flush")
            
            batch_id += 1
            avg_payload_size = batch_payload_size / batch_size
            
            # Log metrics for this batch
            self.log_metrics(
                workload_type="batch",
                message_rate=batch_size / batch_interval,
                payload_size=avg_payload_size,
                batch_size=batch_size
            )
            
            logger.info(f"Batch workload: Completed batch #{batch_id-1}, sent {batch_size} messages, avg payload size: {avg_payload_size:.0f} bytes")
            
            # Sleep until the next batch interval
            batch_duration = time.time() - batch_start
            sleep_time = max(0, batch_interval - batch_duration)
            if sleep_time > 0:
                logger.info(f"Sleeping for {sleep_time:.2f} seconds until next batch")
                time.sleep(sleep_time)
    
    # Mixed workload implementation removed as requested
    
    def run_workload_rotation(self, cycles=1):
        """Run complete workload rotation for specified number of cycles."""
        logger.info(f"Starting workload rotation for {cycles} cycles")
        self.running = True
        
        try:
            for cycle in range(cycles):
                logger.info(f"Starting cycle {cycle+1}/{cycles}")
                
                # Run real-time workload for 2 hours
                self.run_real_time_workload(duration_seconds=7200)
                if not self.running:
                    break
                
                # Run batch workload for 1 hour
                self.run_batch_workload(duration_seconds=3600)
                if not self.running:
                    break
                
                # Mixed workload removed as requested
            
            logger.info(f"Completed {cycles} workload rotation cycles")
        
        except KeyboardInterrupt:
            logger.info("Workload rotation interrupted by user")
            self.running = False
        
        except Exception as e:
            logger.error(f"Error in workload rotation: {e}", exc_info=True)
            self.running = False
    
    def stop(self):
        """Stop the workload generator."""
        logger.info("Stopping workload generator")
        self.running = False
        
        if self.producer:
            self.producer.flush(timeout=10.0)
            logger.info("Final flush completed")


def main():
    parser = argparse.ArgumentParser(description="Kafka AI Workload Generator")
    # Use comma-separated bootstrap servers for multi-broker environment
    parser.add_argument("--bootstrap-servers", default="kafka1:9092,kafka2:9093,kafka3:9094", 
                       help="Comma-separated Kafka bootstrap servers")
    parser.add_argument("--topic", default="ai_workloads", help="Kafka topic to produce to")
    parser.add_argument("--metrics-port", type=int, default=8000, help="Port for Prometheus metrics")
    parser.add_argument("--workload", choices=["real_time", "batch", "rotation"], 
                        default="rotation", help="Workload type to generate")
    parser.add_argument("--duration", type=int, default=3600, 
                        help="Duration in seconds (for non-rotation workloads)")
    parser.add_argument("--cycles", type=int, default=1, 
                        help="Number of full cycles for rotation workload")
    
    args = parser.parse_args()
    
    # Setup error handling
    try:
        generator = WorkloadGenerator(
            bootstrap_servers=args.bootstrap_servers,
            topic_name=args.topic,
            metrics_port=args.metrics_port
        )
        
        generator.connect()
        
        try:
            if args.workload == "real_time":
                generator.run_real_time_workload(duration_seconds=args.duration)
            elif args.workload == "batch":
                generator.run_batch_workload(duration_seconds=args.duration)
            # Mixed workload option removed
            elif args.workload == "rotation":
                generator.run_workload_rotation(cycles=args.cycles)
        
        except KeyboardInterrupt:
            logger.info("Workload generator interrupted by user")
        
        finally:
            generator.stop()
            logger.info("Workload generator shutdown complete")
    
    except Exception as e:
        logger.error(f"Fatal error in workload generator: {e}", exc_info=True)
        exit(1)


if __name__ == "__main__":
    main()