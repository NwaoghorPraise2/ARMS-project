import os
import numpy as np
import pandas as pd
import argparse
from typing import List, Dict, Any
from src.common.models import WorkloadType
from src.common.utils import setup_logging

logger = setup_logging(__name__)

def generate_batch_workload_features(count: int) -> List[Dict[str, Any]]:
    """
    Generate synthetic features for batch data-intensive workloads
    
    Args:
        count: Number of samples to generate
    
    Returns:
        List of feature dictionaries
    """
    features = []
    
    for _ in range(count):
        # Batch workloads typically have:
        # - Lower message rates but higher message sizes
        # - Higher batch sizes
        # - More variable inter-message times
        # - Higher consumer lag
        
        # Generate with some randomness to create varied samples
        sample = {
            'message_rate': np.random.uniform(10, 500),  # Messages per second
            'message_size_avg': np.random.uniform(50*1024, 1024*1024),  # 50KB to 1MB
            'message_size_stddev': np.random.uniform(10*1024, 100*1024),  # 10KB to 100KB
            'consumer_lag_avg': np.random.uniform(100, 10000),  # Messages
            'processing_time_avg': np.random.uniform(50, 500),  # milliseconds
            'inter_message_time_stddev': np.random.uniform(0.1, 2.0),  # seconds
            'batch_size_avg': np.random.uniform(100, 1000),  # messages
            'topic_partition_count': np.random.randint(1, 20),  # partitions
            'consumer_count': np.random.randint(1, 10),  # consumers
            'throughput_mbps': np.random.uniform(1, 50),  # MB/s
            'concurrent_consumers': np.random.randint(1, 5),  # consumers
            'peak_to_average_ratio': np.random.uniform(1.5, 5.0),  # ratio
            'workload_type': WorkloadType.BATCH_DATA_INTENSIVE.value
        }
        
        features.append(sample)
        
    return features

def generate_realtime_workload_features(count: int) -> List[Dict[str, Any]]:
    """
    Generate synthetic features for real-time event-driven workloads
    
    Args:
        count: Number of samples to generate
    
    Returns:
        List of feature dictionaries
    """
    features = []
    
    for _ in range(count):
        # Real-time workloads typically have:
        # - Higher message rates but smaller message sizes
        # - Smaller batch sizes
        # - More consistent inter-message times
        # - Lower consumer lag
        
        # Generate with some randomness to create varied samples
        sample = {
            'message_rate': np.random.uniform(500, 10000),  # Messages per second
            'message_size_avg': np.random.uniform(1*1024, 50*1024),  # 1KB to 50KB
            'message_size_stddev': np.random.uniform(100, 5*1024),  # 100B to 5KB
            'consumer_lag_avg': np.random.uniform(0, 100),  # Messages
            'processing_time_avg': np.random.uniform(1, 50),  # milliseconds
            'inter_message_time_stddev': np.random.uniform(0.001, 0.1),  # seconds
            'batch_size_avg': np.random.uniform(1, 100),  # messages
            'topic_partition_count': np.random.randint(10, 100),  # partitions
            'consumer_count': np.random.randint(5, 50),  # consumers
            'throughput_mbps': np.random.uniform(10, 200),  # MB/s
            'concurrent_consumers': np.random.randint(5, 20),  # consumers
            'peak_to_average_ratio': np.random.uniform(1.0, 2.0),  # ratio
            'workload_type': WorkloadType.REALTIME_EVENT_DRIVEN.value
        }
        
        features.append(sample)
        
    return features

def generate_training_data(output_file: str, batch_count: int = 5000, realtime_count: int = 5000) -> None:
    """
    Generate and save synthetic training data
    
    Args:
        output_file: Path to save the CSV file
        batch_count: Number of batch workload samples to generate
        realtime_count: Number of real-time workload samples to generate
    """
    logger.info(f"Generating {batch_count} batch and {realtime_count} real-time samples")
    
    # Generate features
    batch_features = generate_batch_workload_features(batch_count)
    realtime_features = generate_realtime_workload_features(realtime_count)
    
    # Combine features
    all_features = batch_features + realtime_features
    
    # Convert to DataFrame
    df = pd.DataFrame(all_features)
    
    # Ensure output directory exists
    os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)
    
    # Save to CSV
    df.to_csv(output_file, index=False)
    
    logger.info(f"Training data saved to {output_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Generate synthetic training data for ARMS classifier')
    parser.add_argument('--output', default='data/training_data.csv',
                      help='Path to save the generated training data')
    parser.add_argument('--batch-count', type=int, default=5000,
                      help='Number of batch workload samples to generate')
    parser.add_argument('--realtime-count', type=int, default=5000,
                      help='Number of real-time workload samples to generate')
    
    args = parser.parse_args()
    
    generate_training_data(args.output, args.batch_count, args.realtime_count)