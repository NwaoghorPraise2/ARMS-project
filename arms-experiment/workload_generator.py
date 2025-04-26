#!/usr/bin/env python3

import os
import sys
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

# Flask and monitoring imports
from flask import Flask, jsonify, request
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

    def run_real_time_workload(self, duration_seconds=3600, target_messages=1000000):
        """
        Run real-time streaming workload for a specified duration.
        
        Args:
            duration_seconds: Total duration in seconds to run the workload
            target_messages: Target number of messages to send during the workload
        """
        logger.info(f"Starting real-time workload for {duration_seconds} seconds")
        logger.info(f"Target: {target_messages} total messages")
        
        self.running = True
        self.start_time = time.time()
        end_time = time.time() + duration_seconds
        self.current_workload = "real_time"
        
        # Calculate target message rate to achieve the target message count
        message_rate = target_messages / duration_seconds
        inter_message_delay = 1.0 / message_rate
        
        logger.info(f"Real-time workload: Target rate {message_rate:.2f} msgs/sec")
        
        messages_sent = 0
        total_payload_size = 0
        batch_count = 0
        
        while time.time() < end_time and self.running:
            batch_start = time.time()
            # Calculate optimal batch size based on rate
            batch_size = min(50, max(1, int(message_rate / 10)))
            
            batch_payload_size = 0
            batch_count += 1
            
            for _ in range(batch_size):
                if messages_sent >= target_messages:
                    logger.info(f"Reached target message count: {messages_sent}")
                    break
                    
                message = self.generate_real_time_speech_data()
                message_json = json.dumps(message)
                batch_payload_size += len(message_json)
                total_payload_size += len(message_json)
                
                try:
                    self.producer.produce(
                        self.topic_name,
                        key=str(uuid.uuid4()),
                        value=message_json.encode('utf-8'),
                        callback=self.delivery_report
                    )
                    messages_sent += 1
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
                    messages_sent += 1
            
            # Poll to handle callbacks
            self.producer.poll(0)
            
            # Log metrics periodically (every 20 batches)
            if batch_count % 20 == 0:
                elapsed = time.time() - self.start_time
                current_rate = messages_sent / elapsed if elapsed > 0 else 0
                avg_payload_size = total_payload_size / messages_sent if messages_sent > 0 else 0
                
                logger.info(f"Progress: {messages_sent}/{target_messages} messages sent " +
                          f"({current_rate:.2f} msgs/sec, avg size: {avg_payload_size:.2f} bytes)")
                
                # Log metrics to prometheus and CSV
                self.log_metrics(
                    workload_type="real_time",
                    message_rate=current_rate,
                    payload_size=avg_payload_size,
                    batch_size=batch_size
                )
            
            # Calculate how long to sleep to maintain the target rate
            batch_duration = time.time() - batch_start
            sleep_time = max(0, (batch_size * inter_message_delay) - batch_duration)
            if sleep_time > 0:
                time.sleep(sleep_time)
        
        # Final flush to ensure all messages are delivered
        self.producer.flush(timeout=10.0)
        
        total_elapsed = time.time() - self.start_time
        avg_payload_size = total_payload_size / messages_sent if messages_sent > 0 else 0
        actual_rate = messages_sent / total_elapsed if total_elapsed > 0 else 0
        
        logger.info(f"Real-time workload complete:")
        logger.info(f"- Total messages: {messages_sent}")
        logger.info(f"- Total time: {total_elapsed:.2f} seconds")
        logger.info(f"- Actual rate: {actual_rate:.2f} msgs/sec")
        logger.info(f"- Average payload size: {avg_payload_size:.2f} bytes")
        
        # Final metrics log
        self.log_metrics(
            workload_type="real_time",
            message_rate=actual_rate,
            payload_size=avg_payload_size,
            batch_size=0
        )

    def run_batch_workload(self, duration_seconds=3600, target_messages=1000000, batch_size=10000):
        """
        Run batch processing workload for a specified duration.
        
        Args:
            duration_seconds: Total duration in seconds to run the workload
            target_messages: Target number of messages to send during the workload
            batch_size: Number of messages to send in each batch
        """
        logger.info(f"Starting batch workload for {duration_seconds} seconds")
        logger.info(f"Target: {target_messages} total messages")
        
        self.running = True
        self.start_time = time.time()
        end_time = time.time() + duration_seconds
        self.current_workload = "batch"
        
        # Calculate how many batches to send to hit target
        num_batches = max(1, target_messages // batch_size)
        
        # Adjust batch size to hit target exactly
        adjusted_batch_size = target_messages // num_batches
        
        # Calculate timing to spread batches over the duration
        batch_interval = duration_seconds / num_batches
        
        logger.info(f"Batch workload: {num_batches} batches of {adjusted_batch_size} messages each")
        logger.info(f"Batch interval: {batch_interval:.2f} seconds")
        
        messages_sent = 0
        total_payload_size = 0
        batch_id = 0
        
        while time.time() < end_time and self.running and messages_sent < target_messages:
            batch_start = time.time()
            
            # Adjust last batch size to hit target exactly
            remaining_messages = target_messages - messages_sent
            current_batch_size = min(adjusted_batch_size, remaining_messages)
            
            logger.info(f"Sending batch #{batch_id+1}/{num_batches} with {current_batch_size} messages")
            
            batch_payload_size = 0
            for i in range(current_batch_size):
                message = self.generate_batch_speech_data(batch_id)
                message_json = json.dumps(message)
                batch_payload_size += len(message_json)
                total_payload_size += len(message_json)
                
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
            
            # Flush to ensure delivery
            self.producer.flush(timeout=5.0)
            
            # Calculate metrics for this batch
            avg_batch_payload_size = batch_payload_size / current_batch_size if current_batch_size > 0 else 0
            messages_sent += current_batch_size
            batch_id += 1
            
            # Log metrics after each batch
            elapsed = time.time() - self.start_time
            current_rate = messages_sent / elapsed if elapsed > 0 else 0
            logger.info(f"Progress: {messages_sent}/{target_messages} messages sent " +
                      f"({current_rate:.2f} msgs/sec, avg size: {avg_batch_payload_size:.2f} bytes)")
            
            # Log metrics to prometheus and CSV
            self.log_metrics(
                workload_type="batch",
                message_rate=current_rate,
                payload_size=avg_batch_payload_size,
                batch_size=current_batch_size
            )
            
            # If we've reached the target or end time, break
            if messages_sent >= target_messages or time.time() >= end_time:
                break
                
            # Calculate sleep time to maintain batch interval
            batch_duration = time.time() - batch_start
            sleep_time = max(0, batch_interval - batch_duration)
            
            # Only sleep if we haven't reached the end of the duration
            # and we haven't sent all messages yet
            if sleep_time > 0 and time.time() + sleep_time < end_time and messages_sent < target_messages:
                logger.info(f"Sleeping for {sleep_time:.2f} seconds until next batch")
                time.sleep(sleep_time)
        
        # Final flush to ensure all messages are delivered
        self.producer.flush(timeout=10.0)
        
        total_elapsed = time.time() - self.start_time
        avg_payload_size = total_payload_size / messages_sent if messages_sent > 0 else 0
        actual_rate = messages_sent / total_elapsed if total_elapsed > 0 else 0
        
        logger.info(f"Batch workload complete:")
        logger.info(f"- Total messages: {messages_sent}")
        logger.info(f"- Total batches: {batch_id}")
        logger.info(f"- Total time: {total_elapsed:.2f} seconds")
        logger.info(f"- Actual rate: {actual_rate:.2f} msgs/sec")
        logger.info(f"- Average payload size: {avg_payload_size:.2f} bytes")
        
        # Final metrics log
        self.log_metrics(
            workload_type="batch",
            message_rate=actual_rate,
            payload_size=avg_payload_size,
            batch_size=adjusted_batch_size
        )

    def run_balanced_workload(self, total_duration_seconds=3600, interval_seconds=300, total_messages=2160000):
        """
        Run alternating real-time and batch workloads for a total duration,
        ensuring both types send the same number of messages.
        
        Args:
            total_duration_seconds: Total runtime in seconds (default: 1 hour)
            interval_seconds: Time to spend on each workload before switching (default: 5 minutes)
            total_messages: Total target messages to send across all workloads (default: 2.16M)
        """
        logger.info(f"Starting balanced workload for {total_duration_seconds} seconds")
        logger.info(f"Target: {total_messages} total messages, equal split between workload types")
        
        self.running = True
        self.start_time = time.time()
        end_time = time.time() + total_duration_seconds
        
        # Calculate how many intervals we'll have
        total_intervals = total_duration_seconds // interval_seconds
        if total_intervals % 2 != 0:
            total_intervals -= 1  # Ensure even number of intervals for equal split
        
        # Calculate messages per workload type
        messages_per_type = total_messages // 2
        # Calculate messages per interval
        messages_per_interval = messages_per_type // (total_intervals // 2)
        
        logger.info(f"Will run {total_intervals} intervals of {interval_seconds} seconds each")
        logger.info(f"Target: {messages_per_interval} messages per interval")
        
        # Initialize counters
        real_time_messages = 0
        batch_messages = 0
        current_interval = 0
        
        while time.time() < end_time and self.running and current_interval < total_intervals:
            interval_start = time.time()
            interval_end = interval_start + interval_seconds
            
            # Determine current workload type
            is_real_time = (current_interval % 2 == 0)
            workload_type = "real_time" if is_real_time else "batch"
            self.current_workload = workload_type
            
            logger.info(f"Starting interval {current_interval+1}/{total_intervals}: {workload_type}")
            
            if is_real_time:
                # Run real-time workload for this interval
                message_rate = messages_per_interval / interval_seconds
                logger.info(f"Real-time workload: Target rate {message_rate:.2f} msgs/sec")
                
                inter_message_delay = 1.0 / message_rate
                interval_messages_sent = 0
                
                while time.time() < interval_end and self.running:
                    batch_start = time.time()
                    # Calculate optimal batch size based on rate
                    batch_size = min(50, max(1, int(message_rate / 10)))
                    
                    batch_payload_size = 0
                    for _ in range(batch_size):
                        if interval_messages_sent >= messages_per_interval:
                            break
                            
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
                            interval_messages_sent += 1
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
                            interval_messages_sent += 1
                    
                    # Poll to handle callbacks
                    self.producer.poll(0)
                    
                    if interval_messages_sent >= messages_per_interval:
                        logger.info(f"Reached target message count for interval: {interval_messages_sent}")
                        break
                    
                    # Calculate how long to sleep to maintain the target rate
                    batch_duration = time.time() - batch_start
                    sleep_time = max(0, (batch_size * inter_message_delay) - batch_duration)
                    if sleep_time > 0:
                        time.sleep(sleep_time)
                
                # Update counters
                real_time_messages += interval_messages_sent
                logger.info(f"Real-time interval complete: Sent {interval_messages_sent} messages")
                
                # Log metrics
                avg_payload_size = batch_payload_size / batch_size if batch_size > 0 else 0
                self.log_metrics(
                    workload_type="real_time",
                    message_rate=message_rate,
                    payload_size=avg_payload_size,
                    batch_size=0
                )
                
            else:
                # Run batch workload for this interval
                # Calculate how many batches to send in this interval
                batch_size = 10000  # Fixed batch size
                num_batches = max(1, messages_per_interval // batch_size)
                
                # If we can't fit exactly into batches, adjust the batch size
                if messages_per_interval % batch_size != 0:
                    batch_size = messages_per_interval // num_batches
                
                batch_interval = interval_seconds / num_batches
                logger.info(f"Batch workload: {num_batches} batches of {batch_size} messages each")
                logger.info(f"Batch interval: {batch_interval:.2f} seconds")
                
                interval_messages_sent = 0
                batch_id = 0
                
                while time.time() < interval_end and self.running and interval_messages_sent < messages_per_interval:
                    batch_start = time.time()
                    
                    # Adjust last batch size to hit target exactly
                    remaining_messages = messages_per_interval - interval_messages_sent
                    current_batch_size = min(batch_size, remaining_messages)
                    
                    logger.info(f"Sending batch #{batch_id+1}/{num_batches} with {current_batch_size} messages")
                    
                    batch_payload_size = 0
                    for i in range(current_batch_size):
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
                    
                    # Flush to ensure delivery
                    self.producer.flush(timeout=5.0)
                    
                    interval_messages_sent += current_batch_size
                    batch_id += 1
                    
                    # Calculate sleep time to maintain batch interval
                    batch_duration = time.time() - batch_start
                    sleep_time = max(0, batch_interval - batch_duration)
                    
                    # Only sleep if we haven't reached the end of the interval
                    # and we haven't sent all messages yet
                    if sleep_time > 0 and time.time() + sleep_time < interval_end and interval_messages_sent < messages_per_interval:
                        logger.info(f"Sleeping for {sleep_time:.2f} seconds until next batch")
                        time.sleep(sleep_time)
                
                # Update counters
                batch_messages += interval_messages_sent
                logger.info(f"Batch interval complete: Sent {interval_messages_sent} messages")
                
                # Log metrics
                avg_payload_size = batch_payload_size / current_batch_size if current_batch_size > 0 else 0
                self.log_metrics(
                    workload_type="batch",
                    message_rate=interval_messages_sent / interval_seconds,
                    payload_size=avg_payload_size,
                    batch_size=batch_size
                )
            
            # Move to next interval
            current_interval += 1
            
            # If we finished the interval early, sleep until the next one
            time_to_next = interval_end - time.time()
            if time_to_next > 0 and self.running and current_interval < total_intervals:
                logger.info(f"Finished interval early, sleeping for {time_to_next:.2f} seconds until next interval")
                time.sleep(time_to_next)
        
        # Final flush to ensure all messages are delivered
        self.producer.flush(timeout=10.0)
        
        # Log final stats
        total_elapsed = time.time() - self.start_time
        logger.info(f"Balanced workload complete:")
        logger.info(f"- Real-time messages: {real_time_messages}")
        logger.info(f"- Batch messages: {batch_messages}")
        logger.info(f"- Total messages: {real_time_messages + batch_messages}")
        logger.info(f"- Total time: {total_elapsed:.2f} seconds")

    def stop(self):
        """Stop the workload generator."""
        logger.info("Stopping workload generator")
        self.running = False
        
        if self.producer:
            self.producer.flush(timeout=10.0)
            logger.info("Final flush completed")

# Create Flask app for API
app = Flask(__name__)

# Global workload generator instance
generator = None
config = {}

@app.route('/health', methods=['GET'])
def health_check():
    """API endpoint for health checks."""
    if generator and generator.running:
        return jsonify({"status": "healthy"})
    else:
        return jsonify({"status": "unhealthy"}), 503



@app.route('/start', methods=['POST'])
def start_workload():
    """API endpoint to start a specific workload."""
    global generator, config
    
    if not generator:
        return jsonify({
            "status": "error",
            "message": "Workload generator not initialized"
        }), 503
    
    try:
        data = request.json
        workload_type = data.get("workload", "real_time")
        duration = data.get("duration", 3600)
        total_messages = data.get("total_messages", 1000000)
        batch_size = data.get("batch_size", 10000)
        
        # Stop any running workload
        if generator.running:
            generator.stop()
        
        # Start a new workload in a separate thread
        workload_thread = threading.Thread(
            target=start_workload_thread,
            args=(workload_type, duration, total_messages, batch_size),
            daemon=True
        )
        workload_thread.start()
        
        return jsonify({
            "status": "success",
            "message": f"Started {workload_type} workload",
            "config": {
                "workload_type": workload_type,
                "duration": duration,
                "total_messages": total_messages,
                "batch_size": batch_size
            }
        })
        
    except Exception as e:
        logger.error(f"Error starting workload: {e}")
        return jsonify({
            "status": "error",
            "message": f"Failed to start workload: {str(e)}"
        }), 500

def start_workload_thread(workload_type, duration, total_messages, batch_size):
    """Start a workload in a separate thread."""
    global generator
    
    try:
        if workload_type == "real_time":
            generator.run_real_time_workload(
                duration_seconds=duration,
                target_messages=total_messages
            )
        elif workload_type == "batch":
            generator.run_batch_workload(
                duration_seconds=duration,
                target_messages=total_messages,
                batch_size=batch_size
            )
        elif workload_type == "balanced":
            generator.run_balanced_workload(
                total_duration_seconds=duration,
                interval_seconds=300,
                total_messages=total_messages
            )
    except Exception as e:
        logger.error(f"Error in workload thread: {e}")
    finally:
        if generator:
            generator.stop()

@app.route('/state', methods=['GET'])
def get_state():
    """API endpoint to get the current workload generator state."""
    if not generator:
        return jsonify({
            "status": "error",
            "message": "Workload generator not initialized"
        }), 503
    
    # Convert workload type string to int for classifier compatibility
    workload_type = None
    if generator.current_workload == "real_time":
        workload_type = 0
    elif generator.current_workload == "batch":
        workload_type = 1
    
    state = {
        "status": "running" if generator.running else "stopped",
        "workload_type": workload_type,
        "current_workload": generator.current_workload,
        "messages_sent": generator.messages_sent,
        "bytes_sent": generator.bytes_sent,
        "start_time": generator.start_time
    }
    
    return jsonify(state)

@app.route('/config', methods=['GET'])
def get_config():
    """API endpoint to get the workload generator configuration."""
    if not generator:
        return jsonify({
            "status": "error",
            "message": "Workload generator not initialized"
        }), 503
    
    return jsonify(config)

@app.route('/metrics', methods=['GET'])
def get_metrics():
    """API endpoint to get the current metrics."""
    if not generator:
        return jsonify({
            "status": "error",
            "message": "Workload generator not initialized"
        }), 503
    
    # Calculate some derived metrics
    elapsed = time.time() - generator.start_time if generator.start_time else 0
    msg_rate = generator.messages_sent / elapsed if elapsed > 0 else 0
    byte_rate = generator.bytes_sent / elapsed if elapsed > 0 else 0
    
    metrics = {
        "messages_sent": generator.messages_sent,
        "bytes_sent": generator.bytes_sent,
        "messages_per_second": round(msg_rate, 2),
        "mb_per_second": round(byte_rate / (1024 * 1024), 2),
        "running_time_seconds": round(elapsed, 2)
    }
    
    return jsonify(metrics)

def run_generator(args):
    """Run the workload generator in a separate thread."""
    global generator, config
    
    try:
        # Update config
        config = vars(args)
        
        # Initialize generator
        generator = WorkloadGenerator(
            bootstrap_servers=args.bootstrap_servers,
            topic_name=args.topic,
            metrics_port=args.metrics_port
        )
        
        generator.connect()
        
        # Run the appropriate workload type
        if args.workload == "real_time":
            generator.run_real_time_workload(
                duration_seconds=args.duration,
                target_messages=args.total_messages
            )
        elif args.workload == "batch":
            generator.run_batch_workload(
                duration_seconds=args.duration,
                target_messages=args.total_messages,
                batch_size=args.batch_size
            )
        elif args.workload == "balanced":
            generator.run_balanced_workload(
                total_duration_seconds=args.duration,
                interval_seconds=args.interval,
                total_messages=args.total_messages
            )
        
    except Exception as e:
        logger.error(f"Error in workload generator: {e}", exc_info=True)
    finally:
        if generator:
            generator.stop()
            logger.info("Workload generator stopped")

def main():
    parser = argparse.ArgumentParser(description="Kafka AI Workload Generator with API")
    parser.add_argument("--bootstrap-servers", default="kafka:9092", 
                       help="Comma-separated Kafka bootstrap servers")
    parser.add_argument("--topic", default="ai_workloads", help="Kafka topic to produce to")
    parser.add_argument("--metrics-port", type=int, default=8000, help="Port for Prometheus metrics")
    parser.add_argument("--workload", choices=["real_time", "batch", "balanced"], 
                        default="balanced", help="Workload type to generate")
    parser.add_argument("--duration", type=int, default=3600, 
                        help="Duration in seconds (for all workloads)")
    parser.add_argument("--interval", type=int, default=300, 
                        help="Interval in seconds between workload switches in balanced mode")
    parser.add_argument("--total-messages", type=int, default=2160000, 
                        help="Target total message count for balanced workload")
    parser.add_argument("--batch-size", type=int, default=10000,
                        help="Batch size for batch workload")
    parser.add_argument("--api-port", type=int, default=5005, help="Port for the API server")
    
    args = parser.parse_args()
    
    # Start the workload generator in a separate thread
    generator_thread = threading.Thread(target=run_generator, args=(args,))
    generator_thread.daemon = True
    generator_thread.start()
    
    # Start the API server
    logger.info(f"Starting API server on port {args.api_port}")
    app.run(host='0.0.0.0', port=args.api_port)

if __name__ == "__main__":
    main()

























# import os
# import sys
# import json
# import time
# import random
# import uuid
# import logging
# import argparse
# import threading
# import datetime
# from confluent_kafka import Producer
# import numpy as np
# import csv

# # Flask and monitoring imports
# from flask import Flask, jsonify, request
# from prometheus_client import start_http_server, Gauge

# # Setup logging
# logging.basicConfig(
#     level=logging.INFO,
#     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
#     handlers=[
#         logging.FileHandler("workload_generator.log"),
#         logging.StreamHandler()
#     ]
# )
# logger = logging.getLogger("workload_generator")

# # Setup Prometheus metrics for monitoring the workload generator
# WORKLOAD_TYPE = Gauge('workload_type', 'Current workload type (0=real-time, 1=batch)')
# MESSAGE_RATE = Gauge('message_rate', 'Current message production rate')
# PAYLOAD_SIZE = Gauge('payload_size', 'Average message payload size in bytes')
# BATCH_SIZE = Gauge('batch_size', 'Current batch size for batch workload')

# class WorkloadGenerator:
#     def __init__(self, bootstrap_servers, topic_name="ai_workloads", metrics_port=8000):
#         """Initialize the workload generator with Kafka connection and parameters."""
#         self.bootstrap_servers = bootstrap_servers
#         self.topic_name = topic_name
#         self.producer = None
#         self.running = False
#         self.current_workload = None
#         self.metrics_port = metrics_port
        
#         # Stats for monitoring and logging
#         self.messages_sent = 0
#         self.bytes_sent = 0
#         self.start_time = None
        
#         # CSV logging for metrics
#         self.csv_file = "workload_metrics.csv"
#         self.csv_headers = [
#             "timestamp", "workload_type", "message_rate", "payload_size_bytes", 
#             "batch_size", "cpu_usage", "memory_usage"
#         ]
        
#         # Create CSV file and write headers if it doesn't exist
#         if not os.path.exists(self.csv_file):
#             with open(self.csv_file, 'w', newline='') as csvfile:
#                 writer = csv.DictWriter(csvfile, fieldnames=self.csv_headers)
#                 writer.writeheader()
    
#     def connect(self):
#         """Connect to Kafka broker."""
#         logger.info(f"Connecting to Kafka at {self.bootstrap_servers}")
        
#         # Configure Kafka producer with settings optimized for multi-broker setup
#         conf = {
#             'bootstrap.servers': self.bootstrap_servers,
#             'client.id': 'workload-generator',
#             'acks': 'all',              # 'all' is appropriate for multi-broker setup
#             'retries': 5,               
#             'retry.backoff.ms': 500,    
#             'linger.ms': 50,            # Batch messages for 50ms
#             'compression.type': 'lz4',
#             'message.timeout.ms': 30000,  # 30 seconds timeout
#             'socket.keepalive.enable': True,
#             'reconnect.backoff.ms': 1000,
#             'reconnect.backoff.max.ms': 10000,
#             'queue.buffering.max.messages': 100000,
#             'batch.size': 16384,
#             'max.in.flight.requests.per.connection': 5,
#             'request.required.acks': -1, # Wait for all in-sync replicas
#             'delivery.timeout.ms': 120000  # 2 minutes timeout for delivery
#         }
        
#         try:
#             self.producer = Producer(conf)
#             logger.info("Connected to Kafka")
            
#             # Start Prometheus metrics server
#             start_http_server(self.metrics_port)
#             logger.info(f"Started Prometheus metrics server on port {self.metrics_port}")
#         except Exception as e:
#             logger.error(f"Failed to connect to Kafka: {e}")
#             raise
    
#     def log_metrics(self, workload_type, message_rate, payload_size, batch_size=0):
#         """Log metrics to CSV file."""
#         # Get basic system metrics
#         cpu_usage = 0.0  # Would require psutil in a real implementation
#         memory_usage = 0.0  # Would require psutil in a real implementation
        
#         # Log to CSV
#         with open(self.csv_file, 'a', newline='') as csvfile:
#             writer = csv.DictWriter(csvfile, fieldnames=self.csv_headers)
#             writer.writerow({
#                 "timestamp": datetime.datetime.now().isoformat(),
#                 "workload_type": workload_type,
#                 "message_rate": message_rate,
#                 "payload_size_bytes": payload_size,
#                 "batch_size": batch_size,
#                 "cpu_usage": cpu_usage,
#                 "memory_usage": memory_usage
#             })
        
#         # Update Prometheus metrics
#         WORKLOAD_TYPE.set(1 if workload_type == "batch" else 0)
#         MESSAGE_RATE.set(message_rate)
#         PAYLOAD_SIZE.set(payload_size)
#         BATCH_SIZE.set(batch_size)
    
#     def delivery_report(self, err, msg):
#         """Callback for message delivery reports."""
#         if err is not None:
#             logger.error(f"Message delivery failed: {err}")
#         else:
#             self.messages_sent += 1
#             self.bytes_sent += len(msg.value())
            
#             # Log throughput every 1000 messages
#             if self.messages_sent % 1000 == 0:
#                 elapsed = time.time() - self.start_time
#                 msg_rate = self.messages_sent / elapsed if elapsed > 0 else 0
#                 byte_rate = self.bytes_sent / elapsed if elapsed > 0 else 0
                
#                 logger.info(f"Throughput: {msg_rate:.2f} msgs/sec, {byte_rate/1024/1024:.2f} MB/sec")
    
#     def generate_real_time_speech_data(self):
#         """Generate simulated real-time speech recognition data."""
#         # Generate a realistic speech recognition message
#         speech_duration = random.uniform(0.5, 5.0)  # 0.5 to 5 seconds of speech
#         sample_rate = 16000  # 16kHz sample rate
#         num_channels = 1  # Mono audio
        
#         # Generate realistic speech recognition confidence scores
#         word_count = random.randint(5, 15)
#         words = []
#         for i in range(word_count):
#             words.append({
#                 "word": f"word_{i}",
#                 "confidence": random.uniform(0.60, 0.99),
#                 "start_time": i * 0.3,
#                 "end_time": (i + 1) * 0.3
#             })
        
#         # Create message payload
#         message = {
#             # Taxonomy fields for classification
#             "taxonomy": {
#                 "latency_sensitivity": "real_time",
#                 "data_criticality": "mission_critical",
#                 "processing_pattern": "event_driven",
#                 "resource_intensity": "compute_intensive"
#             },
            
#             # Speech recognition data
#             "metadata": {
#                 "source_id": str(uuid.uuid4()),
#                 "timestamp": datetime.datetime.now().isoformat(),
#                 "sample_rate": sample_rate,
#                 "num_channels": num_channels,
#                 "duration_seconds": speech_duration,
#                 "format": "PCM16"
#             },
            
#             # Recognition results
#             "results": {
#                 "transcript": " ".join([w["word"] for w in words]),
#                 "confidence": random.uniform(0.75, 0.98),
#                 "words": words,
#                 "language": "en-US"
#             },
            
#             # Add some variable size data to simulate actual audio features
#             "features": {
#                 "mfcc": [random.random() for _ in range(random.randint(10, 30))],
#                 "audio_embeddings": [random.random() for _ in range(random.randint(50, 100))]
#             }
#         }
        
#         return message
    
#     def generate_batch_speech_data(self, batch_id):
#         """Generate simulated batch speech recognition data."""
#         # Simulate batch processing of audio files (e.g., for model training)
        
#         # Create a larger payload with more comprehensive data
#         sample_rate = 16000  # 16kHz sample rate
#         num_channels = 1  # Mono audio
        
#         # Generate a longer transcript (to increase payload size)
#         paragraph_length = random.randint(100, 300)
#         words = []
#         transcript = ""
        
#         for i in range(paragraph_length):
#             word = f"word_{i}"
#             confidence = random.uniform(0.70, 0.99)
#             start_time = i * 0.3
#             end_time = (i + 1) * 0.3
            
#             words.append({
#                 "word": word,
#                 "confidence": confidence,
#                 "start_time": start_time,
#                 "end_time": end_time
#             })
            
#             transcript += word + " "
        
#         # Create a larger message payload
#         message = {
#             # Taxonomy fields for classification
#             "taxonomy": {
#                 "latency_sensitivity": "batch",
#                 "data_criticality": "business_critical",
#                 "processing_pattern": "batch",
#                 "resource_intensity": "io_intensive"
#             },
            
#             # Batch processing metadata
#             "batch_metadata": {
#                 "batch_id": batch_id,
#                 "timestamp": datetime.datetime.now().isoformat(),
#                 "processing_pipeline": "speech_recognition_training",
#                 "total_files": random.randint(500, 1500),
#                 "compression_type": "gzip",
#                 "format_version": "2.0",
#                 "priority": random.choice(["low", "medium", "high"])
#             },
            
#             # Audio metadata
#             "audio_metadata": {
#                 "file_id": str(uuid.uuid4()),
#                 "sample_rate": sample_rate,
#                 "num_channels": num_channels,
#                 "duration_seconds": paragraph_length * 0.3,
#                 "format": "FLAC"
#             },
            
#             # Recognition results
#             "results": {
#                 "transcript": transcript,
#                 "confidence": random.uniform(0.80, 0.95),
#                 "words": words,
#                 "language": "en-US"
#             },
            
#             # Add large arrays to simulate feature extraction results
#             "features": {
#                 "mfcc": [random.random() for _ in range(random.randint(200, 500))],
#                 "audio_embeddings": [random.random() for _ in range(random.randint(500, 1000))],
#                 "spectrogram": [
#                     [random.random() for _ in range(random.randint(50, 100))] 
#                     for _ in range(random.randint(20, 40))
#                 ]
#             }
#         }
        
#         return message

#     def run_real_time_workload(self, duration_seconds=3600):
#         """Run real-time streaming workload."""
#         # This method is a placeholder - development of this method would be similar to the balanced workload real-time section
#         logger.warning("Real-time workload method not fully implemented")
#         pass

#     def run_batch_workload(self, duration_seconds=3600):
#         """Run batch processing workload."""
#         # This method is a placeholder - development of this method would be similar to the balanced workload batch section
#         logger.warning("Batch workload method not fully implemented")
#         pass

#     def run_balanced_workload(self, total_duration_seconds=3600, interval_seconds=300, total_messages=2160000):
#         """
#         Run alternating real-time and batch workloads for a total duration,
#         ensuring both types send the same number of messages.
        
#         Args:
#             total_duration_seconds: Total runtime in seconds (default: 1 hour)
#             interval_seconds: Time to spend on each workload before switching (default: 5 minutes)
#             total_messages: Total target messages to send across all workloads (default: 2.16M)
#         """
#         logger.info(f"Starting balanced workload for {total_duration_seconds} seconds")
#         logger.info(f"Target: {total_messages} total messages, equal split between workload types")
        
#         self.running = True
#         self.start_time = time.time()
#         end_time = time.time() + total_duration_seconds
        
#         # Calculate how many intervals we'll have
#         total_intervals = total_duration_seconds // interval_seconds
#         if total_intervals % 2 != 0:
#             total_intervals -= 1  # Ensure even number of intervals for equal split
        
#         # Calculate messages per workload type
#         messages_per_type = total_messages // 2
#         # Calculate messages per interval
#         messages_per_interval = messages_per_type // (total_intervals // 2)
        
#         logger.info(f"Will run {total_intervals} intervals of {interval_seconds} seconds each")
#         logger.info(f"Target: {messages_per_interval} messages per interval")
        
#         # Initialize counters
#         real_time_messages = 0
#         batch_messages = 0
#         current_interval = 0
        
#         while time.time() < end_time and self.running and current_interval < total_intervals:
#             interval_start = time.time()
#             interval_end = interval_start + interval_seconds
            
#             # Determine current workload type
#             is_real_time = (current_interval % 2 == 0)
#             workload_type = "real_time" if is_real_time else "batch"
#             self.current_workload = workload_type
            
#             logger.info(f"Starting interval {current_interval+1}/{total_intervals}: {workload_type}")
            
#             if is_real_time:
#                 # Run real-time workload for this interval
#                 message_rate = messages_per_interval / interval_seconds
#                 logger.info(f"Real-time workload: Target rate {message_rate:.2f} msgs/sec")
                
#                 inter_message_delay = 1.0 / message_rate
#                 interval_messages_sent = 0
                
#                 while time.time() < interval_end and self.running:
#                     batch_start = time.time()
#                     # Calculate optimal batch size based on rate
#                     batch_size = min(50, max(1, int(message_rate / 10)))
                    
#                     batch_payload_size = 0
#                     for _ in range(batch_size):
#                         if interval_messages_sent >= messages_per_interval:
#                             break
                            
#                         message = self.generate_real_time_speech_data()
#                         message_json = json.dumps(message)
#                         batch_payload_size += len(message_json)
                        
#                         try:
#                             self.producer.produce(
#                                 self.topic_name,
#                                 key=str(uuid.uuid4()),
#                                 value=message_json.encode('utf-8'),
#                                 callback=self.delivery_report
#                             )
#                             interval_messages_sent += 1
#                         except BufferError:
#                             # If the local buffer is full, wait a bit and retry
#                             logger.warning("Local buffer full, waiting...")
#                             self.producer.poll(1)
#                             # Retry producing the message
#                             self.producer.produce
#                             # self.topic_name,
#                             #     key=str(uuid.uuid4()),
#                             #     value=message_json.encode('utf-8'),
#                             #     callback=self.delivery_report
#                             # )
#                             # interval_messages_sent += 1
                    
#                     # Poll to handle callbacks
#                     self.producer.poll(0)
                    
#                     if interval_messages_sent >= messages_per_interval:
#                         logger.info(f"Reached target message count for interval: {interval_messages_sent}")
#                         break
                    
#                     # Calculate how long to sleep to maintain the target rate
#                     batch_duration = time.time() - batch_start
#                     sleep_time = max(0, (batch_size * inter_message_delay) - batch_duration)
#                     if sleep_time > 0:
#                         time.sleep(sleep_time)
                
#                 # Update counters
#                 real_time_messages += interval_messages_sent
#                 logger.info(f"Real-time interval complete: Sent {interval_messages_sent} messages")
                
#                 # Log metrics
#                 avg_payload_size = batch_payload_size / batch_size if batch_size > 0 else 0
#                 self.log_metrics(
#                     workload_type="real_time",
#                     message_rate=message_rate,
#                     payload_size=avg_payload_size,
#                     batch_size=0
#                 )
                
#             else:
#                 # Run batch workload for this interval
#                 # Calculate how many batches to send in this interval
#                 batch_size = 10000  # Fixed batch size
#                 num_batches = max(1, messages_per_interval // batch_size)
                
#                 # If we can't fit exactly into batches, adjust the batch size
#                 if messages_per_interval % batch_size != 0:
#                     batch_size = messages_per_interval // num_batches
                
#                 batch_interval = interval_seconds / num_batches
#                 logger.info(f"Batch workload: {num_batches} batches of {batch_size} messages each")
#                 logger.info(f"Batch interval: {batch_interval:.2f} seconds")
                
#                 interval_messages_sent = 0
#                 batch_id = 0
                
#                 while time.time() < interval_end and self.running and interval_messages_sent < messages_per_interval:
#                     batch_start = time.time()
                    
#                     # Adjust last batch size to hit target exactly
#                     remaining_messages = messages_per_interval - interval_messages_sent
#                     current_batch_size = min(batch_size, remaining_messages)
                    
#                     logger.info(f"Sending batch #{batch_id+1}/{num_batches} with {current_batch_size} messages")
                    
#                     batch_payload_size = 0
#                     for i in range(current_batch_size):
#                         message = self.generate_batch_speech_data(batch_id)
#                         message_json = json.dumps(message)
#                         batch_payload_size += len(message_json)
                        
#                         try:
#                             self.producer.produce(
#                                 self.topic_name,
#                                 key=f"batch-{batch_id}-{i}",
#                                 value=message_json.encode('utf-8'),
#                                 callback=self.delivery_report
#                             )
#                         except BufferError:
#                             # Handle buffer errors
#                             logger.warning("Local buffer full, flushing and retrying...")
#                             self.producer.poll(1)
#                             self.producer.produce(
#                                 self.topic_name,
#                                 key=f"batch-{batch_id}-{i}",
#                                 value=message_json.encode('utf-8'),
#                                 callback=self.delivery_report
#                             )
                        
#                         # Poll to handle callbacks
#                         if i % 100 == 0:
#                             self.producer.poll(0)
                    
#                     # Flush to ensure delivery
#                     self.producer.flush(timeout=5.0)
                    
#                     interval_messages_sent += current_batch_size
#                     batch_id += 1
                    
#                     # Calculate sleep time to maintain batch interval
#                     batch_duration = time.time() - batch_start
#                     sleep_time = max(0, batch_interval - batch_duration)
                    
#                     # Only sleep if we haven't reached the end of the interval
#                     # and we haven't sent all messages yet
#                     if sleep_time > 0 and time.time() + sleep_time < interval_end and interval_messages_sent < messages_per_interval:
#                         logger.info(f"Sleeping for {sleep_time:.2f} seconds until next batch")
#                         time.sleep(sleep_time)
                
#                 # Update counters
#                 batch_messages += interval_messages_sent
#                 logger.info(f"Batch interval complete: Sent {interval_messages_sent} messages")
                
#                 # Log metrics
#                 avg_payload_size = batch_payload_size / current_batch_size if current_batch_size > 0 else 0
#                 self.log_metrics(
#                     workload_type="batch",
#                     message_rate=interval_messages_sent / interval_seconds,
#                     payload_size=avg_payload_size,
#                     batch_size=batch_size
#                 )
            
#             # Move to next interval
#             current_interval += 1
            
#             # If we finished the interval early, sleep until the next one
#             time_to_next = interval_end - time.time()
#             if time_to_next > 0 and self.running and current_interval < total_intervals:
#                 logger.info(f"Finished interval early, sleeping for {time_to_next:.2f} seconds until next interval")
#                 time.sleep(time_to_next)
        
#         # Final flush to ensure all messages are delivered
#         self.producer.flush(timeout=10.0)
        
#         # Log final stats
#         total_elapsed = time.time() - self.start_time
#         logger.info(f"Balanced workload complete:")
#         logger.info(f"- Real-time messages: {real_time_messages}")
#         logger.info(f"- Batch messages: {batch_messages}")
#         logger.info(f"- Total messages: {real_time_messages + batch_messages}")
#         logger.info(f"- Total time: {total_elapsed:.2f} seconds")
    
#     def stop(self):
#         """Stop the workload generator."""
#         logger.info("Stopping workload generator")
#         self.running = False
        
#         if self.producer:
#             self.producer.flush(timeout=10.0)
#             logger.info("Final flush completed")

# # Create Flask app for API
# app = Flask(__name__)

# # Global workload generator instance
# generator = None
# config = {}

# @app.route('/health', methods=['GET'])
# def health_check():
#     """API endpoint for health checks."""
#     if generator and generator.running:
#         return jsonify({"status": "healthy"})
#     else:
#         return jsonify({"status": "unhealthy"}), 503

# @app.route('/state', methods=['GET'])
# def get_state():
#     """API endpoint to get the current workload generator state."""
#     if not generator:
#         return jsonify({
#             "status": "error",
#             "message": "Workload generator not initialized"
#         }), 503
    
#     # Convert workload type string to int for classifier compatibility
#     workload_type = None
#     if generator.current_workload == "real_time":
#         workload_type = 0
#     elif generator.current_workload == "batch":
#         workload_type = 1
    
#     state = {
#         "status": "running" if generator.running else "stopped",
#         "workload_type": workload_type,
#         "current_workload": generator.current_workload,
#         "messages_sent": generator.messages_sent,
#         "bytes_sent": generator.bytes_sent,
#         "start_time": generator.start_time
#     }
    
#     return jsonify(state)

# @app.route('/config', methods=['GET'])
# def get_config():
#     """API endpoint to get the workload generator configuration."""
#     if not generator:
#         return jsonify({
#             "status": "error",
#             "message": "Workload generator not initialized"
#         }), 503
    
#     return jsonify(config)

# @app.route('/metrics', methods=['GET'])
# def get_metrics():
#     """API endpoint to get the current metrics."""
#     if not generator:
#         return jsonify({
#             "status": "error",
#             "message": "Workload generator not initialized"
#         }), 503
    
#     # Calculate some derived metrics
#     elapsed = time.time() - generator.start_time if generator.start_time else 0
#     msg_rate = generator.messages_sent / elapsed if elapsed > 0 else 0
#     byte_rate = generator.bytes_sent / elapsed if elapsed > 0 else 0
    
#     metrics = {
#         "messages_sent": generator.messages_sent,
#         "bytes_sent": generator.bytes_sent,
#         "messages_per_second": round(msg_rate, 2),
#         "mb_per_second": round(byte_rate / (1024 * 1024), 2),
#         "running_time_seconds": round(elapsed, 2)
#     }
    
#     return jsonify(metrics)

# def run_generator(args):
#     """Run the workload generator in a separate thread."""
#     global generator, config
    
#     try:
#         # Update config
#         config = vars(args)
        
#         # Initialize generator
#         generator = WorkloadGenerator(
#             bootstrap_servers=args.bootstrap_servers,
#             topic_name=args.topic,
#             metrics_port=args.metrics_port
#         )
        
#         generator.connect()
        
#         # Run the appropriate workload type
#         if args.workload == "real_time":
#             generator.run_real_time_workload(duration_seconds=args.duration)
#         elif args.workload == "batch":
#             generator.run_batch_workload(duration_seconds=args.duration)
#         elif args.workload == "balanced":
#             generator.run_balanced_workload(
#                 total_duration_seconds=args.duration,
#                 interval_seconds=args.interval,
#                 total_messages=args.total_messages
#             )
        
#     except Exception as e:
#         logger.error(f"Error in workload generator: {e}", exc_info=True)
#     finally:
#         if generator:
#             generator.stop()
#             logger.info("Workload generator stopped")

# def main():
#     parser = argparse.ArgumentParser(description="Kafka AI Workload Generator with API")
#     parser.add_argument("--bootstrap-servers", default="kafka:9092", 
#                        help="Comma-separated Kafka bootstrap servers")
#     parser.add_argument("--topic", default="ai_workloads", help="Kafka topic to produce to")
#     parser.add_argument("--metrics-port", type=int, default=8000, help="Port for Prometheus metrics")
#     parser.add_argument("--workload", choices=["real_time", "batch", "balanced"], 
#                         default="balanced", help="Workload type to generate")
#     parser.add_argument("--duration", type=int, default=3600, 
#                         help="Duration in seconds (for all workloads)")
#     parser.add_argument("--interval", type=int, default=300, 
#                         help="Interval in seconds between workload switches in balanced mode")
#     parser.add_argument("--total-messages", type=int, default=2160000, 
#                         help="Target total message count for balanced workload")
#     parser.add_argument("--api-port", type=int, default=5005, help="Port for the API server")
    
#     args = parser.parse_args()
    
#     # Start the workload generator in a separate thread
#     generator_thread = threading.Thread(target=run_generator, args=(args,))
#     generator_thread.daemon = True
#     generator_thread.start()
    
#     # Start the API server
#     logger.info(f"Starting API server on port {args.api_port}")
#     app.run(host='0.0.0.0', port=args.api_port)

# if __name__ == "__main__":
#     main()

















































# OLD# -*- coding: utf-8 -*-
# OLD# @Author: Your Name



# import json
# import time
# import random
# import uuid
# import logging
# import argparse
# import threading
# import datetime
# from confluent_kafka import Producer
# import numpy as np
# import csv
# import os
# from prometheus_client import start_http_server, Gauge

# # Setup logging
# logging.basicConfig(
#     level=logging.INFO,
#     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
#     handlers=[
#         logging.FileHandler("workload_generator.log"),
#         logging.StreamHandler()
#     ]
# )
# logger = logging.getLogger("workload_generator")

# # Setup Prometheus metrics for monitoring the workload generator
# WORKLOAD_TYPE = Gauge('workload_type', 'Current workload type (0=real-time, 1=batch)')
# MESSAGE_RATE = Gauge('message_rate', 'Current message production rate')
# PAYLOAD_SIZE = Gauge('payload_size', 'Average message payload size in bytes')
# BATCH_SIZE = Gauge('batch_size', 'Current batch size for batch workload')

# class WorkloadGenerator:
#     def __init__(self, bootstrap_servers, topic_name="ai_workloads", metrics_port=8000):
#         """Initialize the workload generator with Kafka connection and parameters."""
#         self.bootstrap_servers = bootstrap_servers
#         self.topic_name = topic_name
#         self.producer = None
#         self.running = False
#         self.current_workload = None
#         self.metrics_port = metrics_port
        
#         # Stats for monitoring and logging
#         self.messages_sent = 0
#         self.bytes_sent = 0
#         self.start_time = None
        
#         # CSV logging for metrics
#         self.csv_file = "workload_metrics.csv"
#         self.csv_headers = [
#             "timestamp", "workload_type", "message_rate", "payload_size_bytes", 
#             "batch_size", "cpu_usage", "memory_usage"
#         ]
        
#         # Create CSV file and write headers if it doesn't exist
#         if not os.path.exists(self.csv_file):
#             with open(self.csv_file, 'w', newline='') as csvfile:
#                 writer = csv.DictWriter(csvfile, fieldnames=self.csv_headers)
#                 writer.writeheader()
    
#     def connect(self):
#         """Connect to Kafka broker."""
#         logger.info(f"Connecting to Kafka at {self.bootstrap_servers}")
        
#         # Configure Kafka producer with settings optimized for multi-broker setup
#         conf = {
#             'bootstrap.servers': self.bootstrap_servers,
#             'client.id': 'workload-generator',
#             'acks': 'all',              # 'all' is appropriate for multi-broker setup
#             'retries': 5,               
#             'retry.backoff.ms': 500,    
#             'linger.ms': 50,            # Batch messages for 50ms
#             'compression.type': 'lz4',
#             'message.timeout.ms': 30000,  # 30 seconds timeout
#             'socket.keepalive.enable': True,
#             'reconnect.backoff.ms': 1000,
#             'reconnect.backoff.max.ms': 10000,
#             'queue.buffering.max.messages': 100000,
#             'batch.size': 16384,
#             'max.in.flight.requests.per.connection': 5,
#             'request.required.acks': -1, # Wait for all in-sync replicas
#             'delivery.timeout.ms': 120000  # 2 minutes timeout for delivery
#         }
        
#         try:
#             self.producer = Producer(conf)
#             logger.info("Connected to Kafka")
            
#             # Start Prometheus metrics server
#             start_http_server(self.metrics_port)
#             logger.info(f"Started Prometheus metrics server on port {self.metrics_port}")
#         except Exception as e:
#             logger.error(f"Failed to connect to Kafka: {e}")
#             raise
    
#     def log_metrics(self, workload_type, message_rate, payload_size, batch_size=0):
#         """Log metrics to CSV file."""
#         # Get basic system metrics
#         cpu_usage = 0.0  # Would require psutil in a real implementation
#         memory_usage = 0.0  # Would require psutil in a real implementation
        
#         # Log to CSV
#         with open(self.csv_file, 'a', newline='') as csvfile:
#             writer = csv.DictWriter(csvfile, fieldnames=self.csv_headers)
#             writer.writerow({
#                 "timestamp": datetime.datetime.now().isoformat(),
#                 "workload_type": workload_type,
#                 "message_rate": message_rate,
#                 "payload_size_bytes": payload_size,
#                 "batch_size": batch_size,
#                 "cpu_usage": cpu_usage,
#                 "memory_usage": memory_usage
#             })
        
#         # Update Prometheus metrics
#         WORKLOAD_TYPE.set(1 if workload_type == "batch" else 0)
#         MESSAGE_RATE.set(message_rate)
#         PAYLOAD_SIZE.set(payload_size)
#         BATCH_SIZE.set(batch_size)
    
#     def delivery_report(self, err, msg):
#         """Callback for message delivery reports."""
#         if err is not None:
#             logger.error(f"Message delivery failed: {err}")
#         else:
#             self.messages_sent += 1
#             self.bytes_sent += len(msg.value())
            
#             # Log throughput every 1000 messages
#             if self.messages_sent % 1000 == 0:
#                 elapsed = time.time() - self.start_time
#                 msg_rate = self.messages_sent / elapsed if elapsed > 0 else 0
#                 byte_rate = self.bytes_sent / elapsed if elapsed > 0 else 0
                
#                 logger.info(f"Throughput: {msg_rate:.2f} msgs/sec, {byte_rate/1024/1024:.2f} MB/sec")
    
#     def generate_real_time_speech_data(self):
#         """Generate simulated real-time speech recognition data."""
#         # Generate a realistic speech recognition message
#         speech_duration = random.uniform(0.5, 5.0)  # 0.5 to 5 seconds of speech
#         sample_rate = 16000  # 16kHz sample rate
#         num_channels = 1  # Mono audio
        
#         # Generate realistic speech recognition confidence scores
#         word_count = random.randint(5, 15)
#         words = []
#         for i in range(word_count):
#             words.append({
#                 "word": f"word_{i}",
#                 "confidence": random.uniform(0.60, 0.99),
#                 "start_time": i * 0.3,
#                 "end_time": (i + 1) * 0.3
#             })
        
#         # Create message payload
#         message = {
#             # Taxonomy fields for classification
#             "taxonomy": {
#                 "latency_sensitivity": "real_time",
#                 "data_criticality": "mission_critical",
#                 "processing_pattern": "event_driven",
#                 "resource_intensity": "compute_intensive"
#             },
            
#             # Speech recognition data
#             "metadata": {
#                 "source_id": str(uuid.uuid4()),
#                 "timestamp": datetime.datetime.now().isoformat(),
#                 "sample_rate": sample_rate,
#                 "num_channels": num_channels,
#                 "duration_seconds": speech_duration,
#                 "format": "PCM16"
#             },
            
#             # Recognition results
#             "results": {
#                 "transcript": " ".join([w["word"] for w in words]),
#                 "confidence": random.uniform(0.75, 0.98),
#                 "words": words,
#                 "language": "en-US"
#             },
            
#             # Add some variable size data to simulate actual audio features
#             "features": {
#                 "mfcc": [random.random() for _ in range(random.randint(10, 30))],
#                 "audio_embeddings": [random.random() for _ in range(random.randint(50, 100))]
#             }
#         }
        
#         return message
    
#     def generate_batch_speech_data(self, batch_id):
#         """Generate simulated batch speech recognition data."""
#         # Simulate batch processing of audio files (e.g., for model training)
        
#         # Create a larger payload with more comprehensive data
#         sample_rate = 16000  # 16kHz sample rate
#         num_channels = 1  # Mono audio
        
#         # Generate a longer transcript (to increase payload size)
#         paragraph_length = random.randint(100, 300)
#         words = []
#         transcript = ""
        
#         for i in range(paragraph_length):
#             word = f"word_{i}"
#             confidence = random.uniform(0.70, 0.99)
#             start_time = i * 0.3
#             end_time = (i + 1) * 0.3
            
#             words.append({
#                 "word": word,
#                 "confidence": confidence,
#                 "start_time": start_time,
#                 "end_time": end_time
#             })
            
#             transcript += word + " "
        
#         # Create a larger message payload
#         message = {
#             # Taxonomy fields for classification
#             "taxonomy": {
#                 "latency_sensitivity": "batch",
#                 "data_criticality": "business_critical",
#                 "processing_pattern": "batch",
#                 "resource_intensity": "io_intensive"
#             },
            
#             # Batch processing metadata
#             "batch_metadata": {
#                 "batch_id": batch_id,
#                 "timestamp": datetime.datetime.now().isoformat(),
#                 "processing_pipeline": "speech_recognition_training",
#                 "total_files": random.randint(500, 1500),
#                 "compression_type": "gzip",
#                 "format_version": "2.0",
#                 "priority": random.choice(["low", "medium", "high"])
#             },
            
#             # Audio metadata
#             "audio_metadata": {
#                 "file_id": str(uuid.uuid4()),
#                 "sample_rate": sample_rate,
#                 "num_channels": num_channels,
#                 "duration_seconds": paragraph_length * 0.3,
#                 "format": "FLAC"
#             },
            
#             # Recognition results
#             "results": {
#                 "transcript": transcript,
#                 "confidence": random.uniform(0.80, 0.95),
#                 "words": words,
#                 "language": "en-US"
#             },
            
#             # Add large arrays to simulate feature extraction results
#             "features": {
#                 "mfcc": [random.random() for _ in range(random.randint(200, 500))],
#                 "audio_embeddings": [random.random() for _ in range(random.randint(500, 1000))],
#                 "spectrogram": [
#                     [random.random() for _ in range(random.randint(50, 100))] 
#                     for _ in range(random.randint(20, 40))
#                 ]
#             }
#         }
        
#         return message

#     def run_balanced_workload(self, total_duration_seconds=3600, interval_seconds=300, total_messages=2160000):
#         """
#         Run alternating real-time and batch workloads for a total duration,
#         ensuring both types send the same number of messages.
        
#         Args:
#             total_duration_seconds: Total runtime in seconds (default: 1 hour)
#             interval_seconds: Time to spend on each workload before switching (default: 5 minutes)
#             total_messages: Total target messages to send across all workloads (default: 2.16M)
#         """
#         logger.info(f"Starting balanced workload for {total_duration_seconds} seconds")
#         logger.info(f"Target: {total_messages} total messages, equal split between workload types")
        
#         self.running = True
#         self.start_time = time.time()
#         end_time = time.time() + total_duration_seconds
        
#         # Calculate how many intervals we'll have
#         total_intervals = total_duration_seconds // interval_seconds
#         if total_intervals % 2 != 0:
#             total_intervals -= 1  # Ensure even number of intervals for equal split
        
#         # Calculate messages per workload type
#         messages_per_type = total_messages // 2
#         # Calculate messages per interval
#         messages_per_interval = messages_per_type // (total_intervals // 2)
        
#         logger.info(f"Will run {total_intervals} intervals of {interval_seconds} seconds each")
#         logger.info(f"Target: {messages_per_interval} messages per interval")
        
#         # Initialize counters
#         real_time_messages = 0
#         batch_messages = 0
#         current_interval = 0
        
#         while time.time() < end_time and self.running and current_interval < total_intervals:
#             interval_start = time.time()
#             interval_end = interval_start + interval_seconds
            
#             # Determine current workload type
#             is_real_time = (current_interval % 2 == 0)
#             workload_type = "real_time" if is_real_time else "batch"
#             self.current_workload = workload_type
            
#             logger.info(f"Starting interval {current_interval+1}/{total_intervals}: {workload_type}")
            
#             if is_real_time:
#                 # Run real-time workload for this interval
#                 message_rate = messages_per_interval / interval_seconds
#                 logger.info(f"Real-time workload: Target rate {message_rate:.2f} msgs/sec")
                
#                 inter_message_delay = 1.0 / message_rate
#                 interval_messages_sent = 0
                
#                 while time.time() < interval_end and self.running:
#                     batch_start = time.time()
#                     # Calculate optimal batch size based on rate
#                     batch_size = min(50, max(1, int(message_rate / 10)))
                    
#                     batch_payload_size = 0
#                     for _ in range(batch_size):
#                         if interval_messages_sent >= messages_per_interval:
#                             break
                            
#                         message = self.generate_real_time_speech_data()
#                         message_json = json.dumps(message)
#                         batch_payload_size += len(message_json)
                        
#                         try:
#                             self.producer.produce(
#                                 self.topic_name,
#                                 key=str(uuid.uuid4()),
#                                 value=message_json.encode('utf-8'),
#                                 callback=self.delivery_report
#                             )
#                             interval_messages_sent += 1
#                         except BufferError:
#                             # If the local buffer is full, wait a bit and retry
#                             logger.warning("Local buffer full, waiting...")
#                             self.producer.poll(1)
#                             # Retry producing the message
#                             self.producer.produce(
#                                 self.topic_name,
#                                 key=str(uuid.uuid4()),
#                                 value=message_json.encode('utf-8'),
#                                 callback=self.delivery_report
#                             )
#                             interval_messages_sent += 1
                    
#                     # Poll to handle callbacks
#                     self.producer.poll(0)
                    
#                     if interval_messages_sent >= messages_per_interval:
#                         logger.info(f"Reached target message count for interval: {interval_messages_sent}")
#                         break
                    
#                     # Calculate how long to sleep to maintain the target rate
#                     batch_duration = time.time() - batch_start
#                     sleep_time = max(0, (batch_size * inter_message_delay) - batch_duration)
#                     if sleep_time > 0:
#                         time.sleep(sleep_time)
                
#                 # Update counters
#                 real_time_messages += interval_messages_sent
#                 logger.info(f"Real-time interval complete: Sent {interval_messages_sent} messages")
                
#                 # Log metrics
#                 avg_payload_size = batch_payload_size / batch_size if batch_size > 0 else 0
#                 self.log_metrics(
#                     workload_type="real_time",
#                     message_rate=message_rate,
#                     payload_size=avg_payload_size,
#                     batch_size=0
#                 )
                
#             else:
#                 # Run batch workload for this interval
#                 # Calculate how many batches to send in this interval
#                 batch_size = 10000  # Fixed batch size
#                 num_batches = max(1, messages_per_interval // batch_size)
                
#                 # If we can't fit exactly into batches, adjust the batch size
#                 if messages_per_interval % batch_size != 0:
#                     batch_size = messages_per_interval // num_batches
                
#                 batch_interval = interval_seconds / num_batches
#                 logger.info(f"Batch workload: {num_batches} batches of {batch_size} messages each")
#                 logger.info(f"Batch interval: {batch_interval:.2f} seconds")
                
#                 interval_messages_sent = 0
#                 batch_id = 0
                
#                 while time.time() < interval_end and self.running and interval_messages_sent < messages_per_interval:
#                     batch_start = time.time()
                    
#                     # Adjust last batch size to hit target exactly
#                     remaining_messages = messages_per_interval - interval_messages_sent
#                     current_batch_size = min(batch_size, remaining_messages)
                    
#                     logger.info(f"Sending batch #{batch_id+1}/{num_batches} with {current_batch_size} messages")
                    
#                     batch_payload_size = 0
#                     for i in range(current_batch_size):
#                         message = self.generate_batch_speech_data(batch_id)
#                         message_json = json.dumps(message)
#                         batch_payload_size += len(message_json)
                        
#                         try:
#                             self.producer.produce(
#                                 self.topic_name,
#                                 key=f"batch-{batch_id}-{i}",
#                                 value=message_json.encode('utf-8'),
#                                 callback=self.delivery_report
#                             )
#                         except BufferError:
#                             # Handle buffer errors
#                             logger.warning("Local buffer full, flushing and retrying...")
#                             self.producer.poll(1)
#                             self.producer.produce(
#                                 self.topic_name,
#                                 key=f"batch-{batch_id}-{i}",
#                                 value=message_json.encode('utf-8'),
#                                 callback=self.delivery_report
#                             )
                        
#                         # Poll to handle callbacks
#                         if i % 100 == 0:
#                             self.producer.poll(0)
                    
#                     # Flush to ensure delivery
#                     self.producer.flush(timeout=5.0)
                    
#                     interval_messages_sent += current_batch_size
#                     batch_id += 1
                    
#                     # Calculate sleep time to maintain batch interval
#                     batch_duration = time.time() - batch_start
#                     sleep_time = max(0, batch_interval - batch_duration)
                    
#                     # Only sleep if we haven't reached the end of the interval
#                     # and we haven't sent all messages yet
#                     if sleep_time > 0 and time.time() + sleep_time < interval_end and interval_messages_sent < messages_per_interval:
#                         logger.info(f"Sleeping for {sleep_time:.2f} seconds until next batch")
#                         time.sleep(sleep_time)
                
#                 # Update counters
#                 batch_messages += interval_messages_sent
#                 logger.info(f"Batch interval complete: Sent {interval_messages_sent} messages")
                
#                 # Log metrics
#                 avg_payload_size = batch_payload_size / current_batch_size if current_batch_size > 0 else 0
#                 self.log_metrics(
#                     workload_type="batch",
#                     message_rate=interval_messages_sent / interval_seconds,
#                     payload_size=avg_payload_size,
#                     batch_size=batch_size
#                 )
            
#             # Move to next interval
#             current_interval += 1
            
#             # If we finished the interval early, sleep until the next one
#             time_to_next = interval_end - time.time()
#             if time_to_next > 0 and self.running and current_interval < total_intervals:
#                 logger.info(f"Finished interval early, sleeping for {time_to_next:.2f} seconds until next interval")
#                 time.sleep(time_to_next)
        
#         # Final flush to ensure all messages are delivered
#         self.producer.flush(timeout=10.0)
        
#         # Log final stats
#         total_elapsed = time.time() - self.start_time
#         logger.info(f"Balanced workload complete:")
#         logger.info(f"- Real-time messages: {real_time_messages}")
#         logger.info(f"- Batch messages: {batch_messages}")
#         logger.info(f"- Total messages: {real_time_messages + batch_messages}")
#         logger.info(f"- Total time: {total_elapsed:.2f} seconds")
    
#     def stop(self):
#         """Stop the workload generator."""
#         logger.info("Stopping workload generator")
#         self.running = False
        
#         if self.producer:
#             self.producer.flush(timeout=10.0)
#             logger.info("Final flush completed")


# def main():
#     parser = argparse.ArgumentParser(description="Kafka AI Workload Generator")
#     # Use comma-separated bootstrap servers for multi-broker environment
#     parser.add_argument("--bootstrap-servers", default="kafka1:9092,kafka2:9093,kafka3:9094", 
#                        help="Comma-separated Kafka bootstrap servers")
#     parser.add_argument("--topic", default="ai_workloads", help="Kafka topic to produce to")
#     parser.add_argument("--metrics-port", type=int, default=8000, help="Port for Prometheus metrics")
#     parser.add_argument("--workload", choices=["real_time", "batch", "balanced"], 
#                         default="balanced", help="Workload type to generate")
#     parser.add_argument("--duration", type=int, default=3600, 
#                         help="Duration in seconds (for all workloads)")
#     parser.add_argument("--interval", type=int, default=300, 
#                         help="Interval in seconds between workload switches in balanced mode")
#     parser.add_argument("--total-messages", type=int, default=2160000, 
#                         help="Target total message count for balanced workload")
    
#     args = parser.parse_args()
    
#     # Setup error handling
#     try:
#         generator = WorkloadGenerator(
#             bootstrap_servers=args.bootstrap_servers,
#             topic_name=args.topic,
#             metrics_port=args.metrics_port
#         )
        
#         generator.connect()
        
#         try:
#             if args.workload == "real_time":
#                 generator.run_real_time_workload(duration_seconds=args.duration)
#             elif args.workload == "batch":
#                 generator.run_batch_workload(duration_seconds=args.duration)
#             elif args.workload == "balanced":
#                 generator.run_balanced_workload(
#                     total_duration_seconds=args.duration,
#                     interval_seconds=args.interval,
#                     total_messages=args.total_messages
#                 )
        
#         except KeyboardInterrupt:
#             logger.info("Workload generator interrupted by user")
        
#         finally:
#             generator.stop()
#             logger.info("Workload generator shutdown complete")
    
#     except Exception as e:
#         logger.error(f"Fatal error in workload generator: {e}", exc_info=True)
#         exit(1)


# if __name__ == "__main__":
#     main()