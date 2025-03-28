import numpy as np
import time
from typing import Dict, List, Any, Optional
from collections import deque

from src.common.utils import setup_logging

logger = setup_logging(__name__)


class FeatureExtractor:
    """
    Extracts features from raw metrics for workload classification
    """
    
    def __init__(self, window_size: int = 60):
        """
        Initialize the feature extractor
        
        Args:
            window_size: Size of the sliding window for feature calculation (in seconds)
        """
        self.window_size = window_size
        self.metrics_history = deque(maxlen=window_size)
    
    def add_metrics(self, metrics: Dict[str, Any]):
        """
        Add a new metrics snapshot to the history
        
        Args:
            metrics: Metrics dictionary from collectors
        """
        self.metrics_history.append(metrics)
    
    def extract_features(self) -> Optional[Dict[str, float]]:
        """
        Extract classification features from the metrics history
        
        Returns:
            Dictionary of features for classification, or None if insufficient data
        """
        # Need at least a few data points for meaningful features
        if len(self.metrics_history) < 5:
            logger.debug("Insufficient metrics history for feature extraction")
            return None
        
        features = {}
        
        try:
            # Extract message rate feature
            features['message_rate'] = self._extract_message_rate()
            
            # Extract message size features
            message_sizes = self._extract_message_sizes()
            features['message_size_avg'] = np.mean(message_sizes) if message_sizes else 0
            features['message_size_stddev'] = np.std(message_sizes) if message_sizes else 0
            
            # Extract consumer lag metrics
            features['consumer_lag_avg'] = self._extract_consumer_lag()
            
            # Extract processing time
            features['processing_time_avg'] = self._extract_processing_time()
            
            # Extract inter-message arrival time variability
            features['inter_message_time_stddev'] = self._extract_inter_message_time_stddev()
            
            # Extract batch size
            features['batch_size_avg'] = self._extract_batch_size()
            
            # Extract topic and partition metrics
            features['topic_partition_count'] = self._extract_topic_partition_count()
            
            # Extract consumer count
            features['consumer_count'] = self._extract_consumer_count()
            
            # Extract throughput
            features['throughput_mbps'] = self._extract_throughput()
            
            # Extract concurrent consumers
            features['concurrent_consumers'] = self._extract_concurrent_consumers()
            
            # Extract peak-to-average ratio
            features['peak_to_average_ratio'] = self._extract_peak_to_average_ratio()

            return features
        
        except Exception as e:
            logger.error(f"Error extracting features: {e}")
            return None

    def _extract_message_rate(self) -> float:
        """
        Extract average message rate feature (messages per second)
        
        Returns:
            Average message rate across all topics
        """
        rates = []
        
        for metrics in self.metrics_history:
            if 'jmx' in metrics and 'broker_metrics' in metrics['jmx']:
                if 'messages_in_rate' in metrics['jmx']['broker_metrics']:
                    rates.append(metrics['jmx']['broker_metrics']['messages_in_rate'])
            
            # Also check topic-specific metrics if available
            if 'jmx' in metrics and 'topic_metrics' in metrics['jmx']:
                for topic, topic_metrics in metrics['jmx']['topic_metrics'].items():
                    if 'messages_in_rate' in topic_metrics:
                        rates.append(topic_metrics['messages_in_rate'])
        
        return np.mean(rates) if rates else 0.0

    def _extract_message_sizes(self) -> List[float]:
        """
        Extract message sizes from metrics
        
        Returns:
            List of message sizes
        """
        sizes = []
        
        for metrics in self.metrics_history:
            if 'jmx' in metrics and 'topic_metrics' in metrics['jmx']:
                for topic, topic_metrics in metrics['jmx']['topic_metrics'].items():
                    if 'bytes_in_rate' in topic_metrics and 'messages_in_rate' in topic_metrics:
                        # Calculate average message size (bytes per message)
                        if topic_metrics['messages_in_rate'] > 0:
                            avg_size = topic_metrics['bytes_in_rate'] / topic_metrics['messages_in_rate']
                            sizes.append(avg_size)
        
        return sizes

    def _extract_consumer_lag(self) -> float:
        """
        Extract average consumer lag
        
        Returns:
            Average consumer lag across all consumer groups
        """
        # This is a simplified implementation - in a real system,
        # you would need to calculate actual lag between produced and consumed offsets
        # For now, we'll use a proxy metric based on queue sizes
        
        queue_sizes = []
        
        for metrics in self.metrics_history:
            if 'jmx' in metrics and 'broker_metrics' in metrics['jmx']:
                if 'request_queue_size' in metrics['jmx']['broker_metrics']:
                    queue_sizes.append(metrics['jmx']['broker_metrics']['request_queue_size'])
        
        return np.mean(queue_sizes) if queue_sizes else 0.0

    def _extract_processing_time(self) -> float:
        """
        Extract average processing time
        
        Returns:
            Average processing time in milliseconds
        """
        # This is a proxy implementation - in a real system, 
        # you would track actual processing times
        
        # Idle time is inversely related to processing time
        idle_percents = []
        
        for metrics in self.metrics_history:
            if 'jmx' in metrics and 'broker_metrics' in metrics['jmx']:
                if 'network_processor_idle_percent' in metrics['jmx']['broker_metrics']:
                    idle_percents.append(metrics['jmx']['broker_metrics']['network_processor_idle_percent'])
        
        avg_idle = np.mean(idle_percents) if idle_percents else 50.0
        
        # Convert idle percent to processing time (milliseconds)
        # This is a heuristic - less idle time means more processing time
        return max(0.1, 10.0 * (100.0 - avg_idle) / 100.0)

    def _extract_inter_message_time_stddev(self) -> float:
        """
        Extract standard deviation of inter-message arrival time
        
        Returns:
            Standard deviation of inter-message times
        """
        # Extract timestamps and message rates
        timestamps = []
        rates = []
        
        for metrics in self.metrics_history:
            if 'timestamp' in metrics:
                timestamps.append(metrics['timestamp'])
                
                if 'jmx' in metrics and 'broker_metrics' in metrics['jmx']:
                    if 'messages_in_rate' in metrics['jmx']['broker_metrics']:
                        rates.append(metrics['jmx']['broker_metrics']['messages_in_rate'])
                    else:
                        rates.append(0)
                else:
                    rates.append(0)
        
        # Calculate variability in rates
        if len(rates) > 1:
            return np.std(rates)
        else:
            return 0.0

    def _extract_batch_size(self) -> float:
        """
        Extract average batch size
        
        Returns:
            Average batch size
        """
        # This is a proxy implementation - in a real system,
        # you would track actual batch sizes from producer metrics
        
        # For now, infer from bytes per second and message rate
        batch_sizes = []
        
        for metrics in self.metrics_history:
            if 'jmx' in metrics and 'broker_metrics' in metrics['jmx']:
                if ('bytes_in_rate' in metrics['jmx']['broker_metrics'] and 
                    'messages_in_rate' in metrics['jmx']['broker_metrics']):
                    if metrics['jmx']['broker_metrics']['messages_in_rate'] > 0:
                        bytes_per_msg = metrics['jmx']['broker_metrics']['bytes_in_rate'] / metrics['jmx']['broker_metrics']['messages_in_rate']
                        # Rough heuristic for batch size based on message size
                        batch_size = max(1, min(100, int(bytes_per_msg / 1024)))
                        batch_sizes.append(batch_size)
        
        return np.mean(batch_sizes) if batch_sizes else 1.0

    def _extract_topic_partition_count(self) -> float:
        """
        Extract topic partition count
        
        Returns:
            Average number of partitions across topics
        """
        partition_counts = []
        
        for metrics in self.metrics_history:
            if 'kafka_admin' in metrics and 'topic_info' in metrics['kafka_admin']:
                for topic, topic_info in metrics['kafka_admin']['topic_info'].items():
                    if 'partitions' in topic_info:
                        partition_counts.append(topic_info['partitions'])
        
        return np.mean(partition_counts) if partition_counts else 0.0

    def _extract_consumer_count(self) -> float:
        """
        Extract consumer count
        
        Returns:
            Average number of consumer groups
        """
        consumer_counts = []
        
        for metrics in self.metrics_history:
            if 'kafka_admin' in metrics and 'consumer_groups' in metrics['kafka_admin']:
                consumer_counts.append(len(metrics['kafka_admin']['consumer_groups']))
        
        return np.mean(consumer_counts) if consumer_counts else 0.0

    def _extract_throughput(self) -> float:
        """
        Extract throughput in MB/s
        
        Returns:
            Average throughput in megabytes per second
        """
        throughputs = []
        
        for metrics in self.metrics_history:
            if 'jmx' in metrics and 'broker_metrics' in metrics['jmx']:
                if 'bytes_in_rate' in metrics['jmx']['broker_metrics']:
                    # Convert bytes/s to MB/s
                    throughput_mbps = metrics['jmx']['broker_metrics']['bytes_in_rate'] / (1024 * 1024)
                    throughputs.append(throughput_mbps)
        
        return np.mean(throughputs) if throughputs else 0.0

    def _extract_concurrent_consumers(self) -> float:
        """
        Extract number of concurrent consumers
        
        Returns:
            Estimated number of concurrent consumers
        """
        # This is a simplified implementation
        # In a real system, you would track active consumers more precisely
        active_consumer_counts = []
        
        for metrics in self.metrics_history:
            if 'kafka_admin' in metrics and 'consumer_groups' in metrics['kafka_admin']:
                # Count active consumer groups (simplified)
                active_count = 0
                for group_id, group_info in metrics['kafka_admin']['consumer_groups'].items():
                    if 'state' in group_info and group_info['state'] == 'Stable':
                        active_count += 1
                
                active_consumer_counts.append(active_count)
        
        return np.mean(active_consumer_counts) if active_consumer_counts else 0.0

    def _extract_peak_to_average_ratio(self) -> float:
        """
        Extract peak-to-average ratio of message rates
        
        Returns:
            Ratio of peak rate to average rate
        """
        rates = []
        
        for metrics in self.metrics_history:
            if 'jmx' in metrics and 'broker_metrics' in metrics['jmx']:
                if 'messages_in_rate' in metrics['jmx']['broker_metrics']:
                    rates.append(metrics['jmx']['broker_metrics']['messages_in_rate'])
        
        if rates:
            avg_rate = np.mean(rates)
            peak_rate = np.max(rates)
            
            if avg_rate > 0:
                return peak_rate / avg_rate
        
        return 1.0  # Default to 1.0 (no peaks)