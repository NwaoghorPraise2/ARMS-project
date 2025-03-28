from src.common.models import WorkloadType
from src.workloadgenerator.generator import WorkloadConfig

# Batch Data-Intensive Workload Templates

def create_batch_small_workload(duration_seconds=600, topic_name=None):
    """Create a small-scale batch data-intensive workload configuration"""
    return WorkloadConfig(
        workload_type=WorkloadType.BATCH_DATA_INTENSIVE,
        workload_size="small",
        message_rate=50,  # 50 messages per second
        message_size_mean=100 * 1024,  # 100KB average
        message_size_stddev=20 * 1024,  # 20KB standard deviation
        burst_factor=2.0,  # Double rate during bursts
        burst_frequency=60,  # Burst every 60 seconds
        duration_seconds=duration_seconds,
        topic_name=topic_name
    )

def create_batch_medium_workload(duration_seconds=600, topic_name=None):
    """Create a medium-scale batch data-intensive workload configuration"""
    return WorkloadConfig(
        workload_type=WorkloadType.BATCH_DATA_INTENSIVE,
        workload_size="medium",
        message_rate=200,  # 200 messages per second
        message_size_mean=250 * 1024,  # 250KB average
        message_size_stddev=50 * 1024,  # 50KB standard deviation
        burst_factor=2.5,  # 2.5x rate during bursts
        burst_frequency=120,  # Burst every 2 minutes
        duration_seconds=duration_seconds,
        topic_name=topic_name
    )

def create_batch_large_workload(duration_seconds=600, topic_name=None):
    """Create a large-scale batch data-intensive workload configuration"""
    return WorkloadConfig(
        workload_type=WorkloadType.BATCH_DATA_INTENSIVE,
        workload_size="large",
        message_rate=500,  # 500 messages per second
        message_size_mean=500 * 1024,  # 500KB average
        message_size_stddev=100 * 1024,  # 100KB standard deviation
        burst_factor=3.0,  # 3x rate during bursts
        burst_frequency=180,  # Burst every 3 minutes
        duration_seconds=duration_seconds,
        topic_name=topic_name
    )

# Real-time Event-Driven Workload Templates

def create_realtime_low_workload(duration_seconds=600, topic_name=None):
    """Create a low-rate real-time event-driven workload configuration"""
    return WorkloadConfig(
        workload_type=WorkloadType.REALTIME_EVENT_DRIVEN,
        workload_size="low",
        message_rate=1000,  # 1000 messages per second
        message_size_mean=5 * 1024,  # 5KB average
        message_size_stddev=1 * 1024,  # 1KB standard deviation
        burst_factor=1.2,  # Small bursts
        burst_frequency=30,  # Brief burst every 30 seconds
        duration_seconds=duration_seconds,
        topic_name=topic_name
    )

def create_realtime_medium_workload(duration_seconds=600, topic_name=None):
    """Create a medium-rate real-time event-driven workload configuration"""
    return WorkloadConfig(
        workload_type=WorkloadType.REALTIME_EVENT_DRIVEN,
        workload_size="medium",
        message_rate=3000,  # 3000 messages per second
        message_size_mean=10 * 1024,  # 10KB average
        message_size_stddev=2 * 1024,  # 2KB standard deviation
        burst_factor=1.5,  # More significant bursts
        burst_frequency=20,  # More frequent bursts
        duration_seconds=duration_seconds,
        topic_name=topic_name
    )

def create_realtime_high_workload(duration_seconds=600, topic_name=None):
    """Create a high-rate real-time event-driven workload configuration"""
    return WorkloadConfig(
        workload_type=WorkloadType.REALTIME_EVENT_DRIVEN,
        workload_size="high",
        message_rate=5000,  # 5000 messages per second
        message_size_mean=15 * 1024,  # 15KB average
        message_size_stddev=3 * 1024,  # 3KB standard deviation
        burst_factor=1.7,  # Significant bursts
        burst_frequency=15,  # Very frequent bursts
        duration_seconds=duration_seconds,
        topic_name=topic_name
    )

# Factory function to create workloads of any type and size
def create_workload(workload_type: WorkloadType, workload_size: str, 
                   duration_seconds=600, topic_name=None):
    """
    Factory function to create workload configurations
    
    Args:
        workload_type: Type of workload (batch or real-time)
        workload_size: Size category (small/medium/large or low/medium/high)
        duration_seconds: Duration of the workload in seconds
        topic_name: Optional topic name
        
    Returns:
        Configured WorkloadConfig instance
    """
    if workload_type == WorkloadType.BATCH_DATA_INTENSIVE:
        if workload_size == "small":
            return create_batch_small_workload(duration_seconds, topic_name)
        elif workload_size == "medium":
            return create_batch_medium_workload(duration_seconds, topic_name)
        elif workload_size == "large":
            return create_batch_large_workload(duration_seconds, topic_name)
    
    elif workload_type == WorkloadType.REALTIME_EVENT_DRIVEN:
        if workload_size == "low":
            return create_realtime_low_workload(duration_seconds, topic_name)
        elif workload_size == "medium":
            return create_realtime_medium_workload(duration_seconds, topic_name)
        elif workload_size == "high":
            return create_realtime_high_workload(duration_seconds, topic_name)
    
    raise ValueError(f"Unsupported workload type {workload_type} or size {workload_size}")