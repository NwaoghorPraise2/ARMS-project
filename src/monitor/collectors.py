import time
import json
import requests
import logging
from typing import Dict, List, Any
from abc import ABC, abstractmethod

from src.common.utils import setup_logging

logger = setup_logging(__name__)


class MetricCollector(ABC):
    """Base abstract class for metric collectors"""
    
    @abstractmethod
    def collect_metrics(self) -> Dict[str, Any]:
        """
        Collect and return metrics
        
        Returns:
            Dictionary of collected metrics
        """
        pass


class JMXMetricCollector(MetricCollector):
    """Collector for JMX metrics via Prometheus JMX exporter"""
    
    def __init__(self, jmx_exporter_url: str = "http://jmx-exporter:5556/metrics"):
        """
        Initialize JMX metric collector
        
        Args:
            jmx_exporter_url: URL of JMX exporter Prometheus endpoint
        """
        self.jmx_exporter_url = jmx_exporter_url
    
    def collect_metrics(self) -> Dict[str, Any]:
        """
        Collect JMX metrics from Kafka brokers
        
        Returns:
            Dictionary of JMX metrics
        """
        try:
            # Fetch metrics from JMX exporter
            response = requests.get(self.jmx_exporter_url, timeout=5)
            response.raise_for_status()
            
            # Parse Prometheus metrics format
            metrics = {}
            for line in response.text.split('\n'):
                if line.startswith('#') or not line.strip():
                    continue
                    
                # Parse metric line
                parts = line.split()
                if len(parts) >= 2:
                    metric_name = parts[0]
                    metric_value = float(parts[1])
                    metrics[metric_name] = metric_value
            
            return self._process_jmx_metrics(metrics)
            
        except Exception as e:
            logger.error(f"Error collecting JMX metrics: {e}")
            return {}
    
    def _process_jmx_metrics(self, raw_metrics: Dict[str, float]) -> Dict[str, Any]:
        """
        Process raw JMX metrics into structured format
        
        Args:
            raw_metrics: Raw metrics from JMX exporter
            
        Returns:
            Processed metrics in structured format
        """
        processed = {
            'broker_metrics': {},
            'topic_metrics': {},
            'jvm_metrics': {}
        }
        
        # Process broker metrics
        broker_metrics = {k: v for k, v in raw_metrics.items() if 'kafka_server' in k}
        for metric_name, value in broker_metrics.items():
            if 'MessagesInPerSec' in metric_name:
                processed['broker_metrics']['messages_in_rate'] = value
            elif 'BytesInPerSec' in metric_name:
                processed['broker_metrics']['bytes_in_rate'] = value
            elif 'BytesOutPerSec' in metric_name:
                processed['broker_metrics']['bytes_out_rate'] = value
            elif 'RequestQueueSize' in metric_name:
                processed['broker_metrics']['request_queue_size'] = value
            elif 'NetworkProcessorAvgIdlePercent' in metric_name:
                processed['broker_metrics']['network_processor_idle_percent'] = value
        
        # Process topic metrics
        topic_metrics = {k: v for k, v in raw_metrics.items() if 'kafka_server_BrokerTopicMetrics' in k}
        for metric_name, value in topic_metrics.items():
            if 'topic=' in metric_name:
                # Extract topic name
                topic_name = metric_name.split('topic=')[1].split(',')[0].strip('"')
                
                if topic_name not in processed['topic_metrics']:
                    processed['topic_metrics'][topic_name] = {}
                
                if 'MessagesInPerSec' in metric_name:
                    processed['topic_metrics'][topic_name]['messages_in_rate'] = value
                elif 'BytesInPerSec' in metric_name:
                    processed['topic_metrics'][topic_name]['bytes_in_rate'] = value
                elif 'BytesOutPerSec' in metric_name:
                    processed['topic_metrics'][topic_name]['bytes_out_rate'] = value
        
        # Process JVM metrics
        jvm_metrics = {k: v for k, v in raw_metrics.items() if 'java_lang' in k}
        for metric_name, value in jvm_metrics.items():
            if 'heap_memory_usage' in metric_name:
                if 'used' in metric_name:
                    processed['jvm_metrics']['heap_used'] = value
                elif 'max' in metric_name:
                    processed['jvm_metrics']['heap_max'] = value
            elif 'threads' in metric_name:
                if 'count' in metric_name:
                    processed['jvm_metrics']['thread_count'] = value
            elif 'cpu_load' in metric_name:
                processed['jvm_metrics']['cpu_load'] = value
        
        return processed


class KafkaAdminMetricCollector(MetricCollector):
    """Collector for metrics via Kafka AdminClient"""
    
    def __init__(self, bootstrap_servers: str):
        """
        Initialize Kafka admin metric collector
        
        Args:
            bootstrap_servers: Kafka bootstrap servers string
        """
        from confluent_kafka.admin import AdminClient
        
        self.bootstrap_servers = bootstrap_servers
        self.admin_client = AdminClient({'bootstrap.servers': bootstrap_servers})
    
    def collect_metrics(self) -> Dict[str, Any]:
        """
        Collect metrics using Kafka AdminClient
        
        Returns:
            Dictionary of AdminClient metrics
        """
        try:
            metrics = {
                'broker_info': {},
                'topic_info': {},
                'consumer_groups': {}
            }
            
            # Get broker metadata
            metadata = self.admin_client.list_topics(timeout=10)
            
            # Process broker info
            for broker_id, broker in metadata.brokers.items():
                metrics['broker_info'][broker_id] = {
                    'id': broker_id,
                    'host': broker.host,
                    'port': broker.port
                }
            # Process topic info
            for topic_name, topic_metadata in metadata.topics.items():
                if topic_metadata.error is not None:
                    continue
                    
                metrics['topic_info'][topic_name] = {
                    'partitions': len(topic_metadata.partitions),
                    'partition_info': {}
                }
                
                # Process partition info
                for partition_id, partition in topic_metadata.partitions.items():
                    metrics['topic_info'][topic_name]['partition_info'][partition_id] = {
                        'id': partition_id,
                        'leader': partition.leader,
                        'replicas': partition.replicas,
                        'isrs': partition.isrs
                    }
            
            # Get consumer groups
            consumer_groups = self.admin_client.list_consumer_groups()
            valid_groups = [group for group in consumer_groups.valid]
            
            # Process consumer group info
            for group in valid_groups:
                metrics['consumer_groups'][group.group_id] = {
                    'state': group.state
                }
                
                # Get consumer group offsets (if needed)
                # Note: This can be resource-intensive, so it's commented out
                """
                consumer_group_offsets = self.admin_client.list_consumer_group_offsets(group.group_id)
                for topic_partition, offset in consumer_group_offsets.items():
                    if topic_partition.topic not in metrics['consumer_groups'][group.group_id]:
                        metrics['consumer_groups'][group.group_id][topic_partition.topic] = {}
                    
                    metrics['consumer_groups'][group.group_id][topic_partition.topic][topic_partition.partition] = {
                        'offset': offset.offset
                    }
                """
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error collecting Kafka admin metrics: {e}")
            return {}


class SystemMetricCollector(MetricCollector):
    """Collector for system metrics"""
    
    def __init__(self):
        """Initialize system metric collector"""
        import psutil
        self.psutil = psutil
    
    def collect_metrics(self) -> Dict[str, Any]:
        """
        Collect system metrics
        
        Returns:
            Dictionary of system metrics
        """
        try:
            metrics = {}
            
            # CPU metrics
            metrics['cpu_percent'] = self.psutil.cpu_percent(interval=0.5)
            metrics['cpu_count'] = self.psutil.cpu_count()
            
            # Memory metrics
            memory = self.psutil.virtual_memory()
            metrics['memory_total'] = memory.total
            metrics['memory_available'] = memory.available
            metrics['memory_used'] = memory.used
            metrics['memory_percent'] = memory.percent
            
            # Disk metrics
            disk = self.psutil.disk_usage('/')
            metrics['disk_total'] = disk.total
            metrics['disk_used'] = disk.used
            metrics['disk_free'] = disk.free
            metrics['disk_percent'] = disk.percent
            
            # Network metrics
            net_io = self.psutil.net_io_counters()
            metrics['net_bytes_sent'] = net_io.bytes_sent
            metrics['net_bytes_recv'] = net_io.bytes_recv
            metrics['net_packets_sent'] = net_io.packets_sent
            metrics['net_packets_recv'] = net_io.packets_recv
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
            return {}


class MetricsCollectorManager:
    """Manager for coordinating multiple metric collectors"""
    
    def __init__(self, bootstrap_servers: str):
        """
        Initialize the metrics collector manager
        
        Args:
            bootstrap_servers: Kafka bootstrap servers string
        """
        self.collectors = {
            'jmx': JMXMetricCollector(),
            'kafka_admin': KafkaAdminMetricCollector(bootstrap_servers),
            'system': SystemMetricCollector()
        }
    
    def collect_all_metrics(self) -> Dict[str, Any]:
        """
        Collect metrics from all collectors
        
        Returns:
            Combined dictionary of all metrics
        """
        all_metrics = {
            'timestamp': time.time()
        }
        
        # Collect from each collector
        for name, collector in self.collectors.items():
            try:
                metrics = collector.collect_metrics()
                all_metrics[name] = metrics
            except Exception as e:
                logger.error(f"Error collecting metrics from {name}: {e}")
                all_metrics[name] = {'error': str(e)}
        
        return all_metrics