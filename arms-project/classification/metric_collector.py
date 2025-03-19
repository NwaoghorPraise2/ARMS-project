import os
import time
import json
import logging
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('MetricCollector')

class MetricCollector:
    def __init__(self, prometheus_url, collection_interval=15):
        self.prometheus_url = prometheus_url
        self.collection_interval = collection_interval
        self.metrics_cache = {}
        logger.info(f"MetricCollector initialized with Prometheus URL: {prometheus_url}")
        
    def query_range(self, query, start_time, end_time, step='15s'):
        """Query Prometheus for a range of time"""
        params = {
            'query': query,
            'start': start_time.timestamp(),
            'end': end_time.timestamp(),
            'step': step
        }
        response = requests.get(f"{self.prometheus_url}/api/v1/query_range", params=params)
        return response.json()
    
    def collect_metrics(self, duration_minutes=5):
        """Collect metrics for a specific duration"""
        end_time = datetime.now()
        start_time = end_time - timedelta(minutes=duration_minutes)
        
        metrics = {}
        
        # Message rate metrics
        metrics['message_rate'] = self.query_range(
            'sum(rate(kafka_server_brokertopicmetrics_messagesin_total[1m]))',
            start_time, end_time
        )
        
        # Broker CPU usage
        metrics['broker_cpu'] = self.query_range(
            'sum(rate(process_cpu_seconds_total{job="kafka"}[1m]))',
            start_time, end_time
        )
        
        # Broker memory usage
        metrics['broker_memory'] = self.query_range(
            'sum(java_lang_memory_heapmemoryusage_used{job="kafka"})',
            start_time, end_time
        )
        
        # Request latency
        metrics['request_latency'] = self.query_range(
            'kafka_network_requestmetrics_totaltimems{quantile="0.99"}',
            start_time, end_time
        )
        
        # Producer/consumer request rate
        metrics['request_rate'] = self.query_range(
            'sum(rate(kafka_server_brokertopicmetrics_totalproducerequests_total[1m]))',
            start_time, end_time
        )
        
        return metrics
    
    def extract_features(self, metrics):
        """Extract features from collected metrics"""
        features = {}
        
        # Process message rate
        if 'message_rate' in metrics and 'data' in metrics['message_rate'] and metrics['message_rate']['data']['result']:
            values = [float(point[1]) for point in metrics['message_rate']['data']['result'][0]['values'] if point[1] != 'NaN']
            features['message_rate_mean'] = np.mean(values) if values else 0
            features['message_rate_std'] = np.std(values) if values else 0
            features['message_rate_max'] = np.max(values) if values else 0
        
        # Process CPU usage
        if 'broker_cpu' in metrics and 'data' in metrics['broker_cpu'] and metrics['broker_cpu']['data']['result']:
            values = [float(point[1]) for point in metrics['broker_cpu']['data']['result'][0]['values'] if point[1] != 'NaN']
            features['cpu_usage_mean'] = np.mean(values) if values else 0
            features['cpu_usage_std'] = np.std(values) if values else 0
        
        # Process memory usage
        if 'broker_memory' in metrics and 'data' in metrics['broker_memory'] and metrics['broker_memory']['data']['result']:
            values = [float(point[1]) for point in metrics['broker_memory']['data']['result'][0]['values'] if point[1] != 'NaN']
            features['memory_usage_mean'] = np.mean(values) if values else 0
            features['memory_usage_std'] = np.std(values) if values else 0
        
        # Process request latency
        if 'request_latency' in metrics and 'data' in metrics['request_latency'] and metrics['request_latency']['data']['result']:
            values = [float(point[1]) for point in metrics['request_latency']['data']['result'][0]['values'] if point[1] != 'NaN']
            features['latency_p99_mean'] = np.mean(values) if values else 0
            features['latency_p99_max'] = np.max(values) if values else 0
        
        # Request rate (activity level)
        if 'request_rate' in metrics and 'data' in metrics['request_rate'] and metrics['request_rate']['data']['result']:
            values = [float(point[1]) for point in metrics['request_rate']['data']['result'][0]['values'] if point[1] != 'NaN']
            features['request_rate_mean'] = np.mean(values) if values else 0
            features['request_burst_ratio'] = np.max(values) / np.mean(values) if np.mean(values) > 0 else 1
        
        return features
    
    def run_collection_loop(self):
        """Run continuous collection loop"""
        while True:
            try:
                logger.info("Collecting metrics...")
                metrics = self.collect_metrics()
                features = self.extract_features(metrics)
                
                # Save features to file
                timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                with open(f"/app/data/features_{timestamp}.json", "w") as f:
                    json.dump(features, f)
                
                logger.info(f"Features extracted and saved: {features}")
                time.sleep(self.collection_interval)
            except Exception as e:
                logger.error(f"Error in collection loop: {e}")
                time.sleep(30)  # Wait a bit before retrying

if __name__ == "__main__":
    prometheus_url = os.environ.get("PROMETHEUS_URL", "http://prometheus:9090")
    collection_interval = int(os.environ.get("COLLECTION_INTERVAL", 15))
    
    collector = MetricCollector(prometheus_url, collection_interval)
    collector.run_collection_loop()
