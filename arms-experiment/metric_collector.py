#!/usr/bin/env python3

import requests
import csv
import time
import datetime
import threading
import logging
import os
from urllib.parse import urljoin

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("metrics_collector.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("metrics_collector")

class MetricsCollector:
    def __init__(self, output_file="all_metrics.csv", collection_interval=15):
        """Initialize the metrics collector."""
        self.output_file = output_file
        self.collection_interval = collection_interval
        self.running = False
        self.prometheus_url = "http://localhost:9090"
        self.csv_file = None
        self.csv_writer = None
        self.headers = ["timestamp"]
        self.metrics = {}
        
        # Define Prometheus endpoints to query
        self.prometheus_endpoints = [
            # Workload generator metrics
            {"name": "workload_type", "endpoint": "/api/v1/query", "params": {"query": "workload_type"}},
            {"name": "message_rate", "endpoint": "/api/v1/query", "params": {"query": "message_rate"}},
            {"name": "payload_size", "endpoint": "/api/v1/query", "params": {"query": "payload_size"}},
            {"name": "batch_size", "endpoint": "/api/v1/query", "params": {"query": "batch_size"}},

            # Traffic Characteristics metrics
            {"name": "kafka_server_brokertopicmetrics_messagesin_total",
             "endpoint": "/api/v1/query",
             "params": {"query": 'sum(rate(kafka_server_brokertopicmetrics_messagesin_total[5m]))'}},
            
            {"name": "kafka_server_brokertopicmetrics_bytesin_total",
             "endpoint": "/api/v1/query",
             "params": {"query": 'sum(rate(kafka_server_brokertopicmetrics_bytesin_total[5m]))'}},
            
            {"name": "message_size_bytes",
             "endpoint": "/api/v1/query",
             "params": {"query": 'sum(rate(kafka_server_brokertopicmetrics_bytesin_total[5m])) / sum(rate(kafka_server_brokertopicmetrics_messagesin_total[5m]))'}},
            
            {"name": "message_rate_variance",
             "endpoint": "/api/v1/query",
             "params": {"query": 'stddev(rate(kafka_server_brokertopicmetrics_messagesin_total[1m]))'}},
            
            # Resource Utilization metrics
            {"name": "process_cpu_seconds_total",
             "endpoint": "/api/v1/query",
             "params": {"query": 'avg(rate(process_cpu_seconds_total[5m]) * 100)'}},
            
            {"name": "java_lang_memory_heapmemoryusage_used",
             "endpoint": "/api/v1/query",
             "params": {"query": 'avg(java_lang_memory_heapmemoryusage_used)'}},
            
            {"name": "node_disk_io_time_seconds_total",
             "endpoint": "/api/v1/query",
             "params": {"query": 'sum(rate(node_disk_io_time_seconds_total[5m]) * 100)'}},
            
            {"name": "memory_usage_variance",
             "endpoint": "/api/v1/query",
             "params": {"query": 'stddev(java_lang_memory_heapmemoryusage_used) / avg(java_lang_memory_heapmemoryusage_used)'}},
            
            # System Responsiveness metrics
            {"name": "kafka_network_requestmetrics_totaltimems",
             "endpoint": "/api/v1/query",
             "params": {"query": 'avg(rate(kafka_network_requestmetrics_totaltimems{request="Produce"}[1m]))'}},
            



            {"name": "kafka_server_brokertopicmetrics_totalproducerequests_total",
             "endpoint": "/api/v1/query",
             "params": {"query": 'sum(rate(kafka_server_brokertopicmetrics_totalproducerequests_total[5m]))'}},
            
            {"name": "java_lang_threading_threadcount",
             "endpoint": "/api/v1/query",
             "params": {"query": 'avg(java_lang_threading_threadcount)'}},
            
            {"name": "request_rate_variance",
             "endpoint": "/api/v1/query",
             "params": {"query": 'stddev_over_time(sum(rate(kafka_server_brokertopicmetrics_totalproducerequests_total[1m]))[15m:1m])'}},
            
            # System metrics
            {"name": "node_memory_MemAvailable_bytes",
             "endpoint": "/api/v1/query",
             "params": {"query": 'avg(node_memory_MemAvailable_bytes)'}},
            
            {"name": "node_disk_read_bytes_total",
             "endpoint": "/api/v1/query",
             "params": {"query": 'sum(rate(node_disk_read_bytes_total[1m]))'}},
            
            {"name": "node_disk_write_bytes_total",
             "endpoint": "/api/v1/query",
             "params": {"query": 'sum(rate(node_disk_written_bytes_total[1m]))'}}
        ]
        
    
    def initialize_csv(self):
        """Initialize the CSV file with headers."""
        # Create CSV headers from metric names
        self.headers = ["timestamp"]
        for endpoint in self.prometheus_endpoints:
            self.headers.append(endpoint["name"])
        
        # Create or overwrite the CSV file with headers
        with open(self.output_file, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(self.headers)
        
        logger.info(f"Initialized CSV file with headers: {self.headers}")
    
    def fetch_metrics(self):
        """Fetch metrics from Prometheus."""
        current_time = datetime.datetime.now().isoformat()
        metrics = {"timestamp": current_time}
        
        for endpoint in self.prometheus_endpoints:
            try:
                url = urljoin(self.prometheus_url, endpoint["endpoint"])
                response = requests.get(url, params=endpoint["params"])
                
                if response.status_code == 200:
                    data = response.json()
                    # Extract metric value(s) from response
                    if data["status"] == "success" and data["data"]["result"]:
                        # For simplicity, we'll just take the first result
                        # In a more complete implementation, you'd handle multiple results differently
                        value = data["data"]["result"][0]["value"][1]
                        metrics[endpoint["name"]] = value
                    else:
                        metrics[endpoint["name"]] = "N/A"
                else:
                    logger.warning(f"Failed to fetch metric {endpoint['name']}: {response.status_code}")
                    metrics[endpoint["name"]] = "N/A"
            
            except Exception as e:
                logger.error(f"Error fetching metric {endpoint['name']}: {e}")
                metrics[endpoint["name"]] = "N/A"
        
        return metrics
    
    def write_metrics_to_csv(self, metrics):
        """Write the collected metrics to CSV."""
        with open(self.output_file, 'a', newline='') as csvfile:
            writer = csv.writer(csvfile)
            
            # Create a row with values in the same order as headers
            row = []
            for header in self.headers:
                row.append(metrics.get(header, "N/A"))
            
            writer.writerow(row)
    
    def collect_metrics_loop(self):
        """Main loop to continuously collect metrics."""
        while self.running:
            try:
                # Fetch metrics from Prometheus
                metrics = self.fetch_metrics()
                
                # Write metrics to CSV
                self.write_metrics_to_csv(metrics)
                
                logger.info(f"Metrics collected at {metrics['timestamp']}")
            
            except Exception as e:
                logger.error(f"Error in metrics collection: {e}")
            
            # Sleep until next collection interval
            time.sleep(self.collection_interval)
    
    def start(self):
        """Start the metrics collector."""
        logger.info("Starting metrics collector")
        
        # Initialize CSV file
        self.initialize_csv()
        
        # Start collection loop in a separate thread
        self.running = True
        self.collection_thread = threading.Thread(target=self.collect_metrics_loop)
        self.collection_thread.daemon = True
        self.collection_thread.start()
        
        logger.info(f"Metrics collector started, writing to {self.output_file}")
    
    def stop(self):
        """Stop the metrics collector."""
        logger.info("Stopping metrics collector")
        self.running = False
        
        if hasattr(self, 'collection_thread') and self.collection_thread.is_alive():
            self.collection_thread.join(timeout=5.0)
        
        logger.info("Metrics collector stopped")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Prometheus Metrics Collector")
    parser.add_argument("--output", default="all_metrics.csv", help="Output CSV file")
    parser.add_argument("--interval", type=int, default=15, help="Collection interval in seconds")
    parser.add_argument("--prometheus-url", default="http://localhost:9090", help="Prometheus URL")
    
    args = parser.parse_args()
    
    collector = MetricsCollector(
        output_file=args.output,
        collection_interval=args.interval
    )
    collector.prometheus_url = args.prometheus_url
    
    try:
        collector.start()
        
        # Keep running until interrupted
        print("Metrics collector running. Press Ctrl+C to stop.")
        while True:
            time.sleep(1)
    
    except KeyboardInterrupt:
        print("Stopping metrics collector...")
    
    finally:
        collector.stop()
        print("Metrics collector stopped.")