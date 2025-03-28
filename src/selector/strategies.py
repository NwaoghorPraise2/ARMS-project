from typing import Dict
from src.common.models import (
    RecoveryStrategy,
    ConsistencyLevel,
    AcknowledgementPolicy,
    PartitionReassignmentStrategy,
    SynchronisationMode,
    ConsumerRebalanceStrategy
)

def create_availability_prioritized_recovery() -> RecoveryStrategy:
    """
    Create an Availability-Prioritised Recovery (APR) strategy
    
    This strategy minimizes recovery time through expedited leader election
    and minimal synchronization requirements. Optimized for real-time, 
    event-driven workloads with high availability requirements.
    
    Returns:
        RecoveryStrategy configured for availability prioritization
    """
    return RecoveryStrategy(
        name="Availability-Prioritised Recovery",
        consistency_level=ConsistencyLevel.EVENTUAL,
        acknowledgement_policy=AcknowledgementPolicy.LEADER_ONLY,
        partition_reassignment_strategy=PartitionReassignmentStrategy.FASTEST_REPLICA_FIRST,
        synchronisation_mode=SynchronisationMode.BACKGROUND,
        consumer_rebalance_strategy=ConsumerRebalanceStrategy.STICKY,
        max_replicas_to_restore=1,
        validation_enabled=False,
        throttling_enabled=False,
        additional_params={
            "unclean.leader.election.enable": "true",
            "min.insync.replicas": "1",
            "replica.lag.time.max.ms": "5000"  # More tolerant of replica lag
        }
    )

def create_consistency_prioritized_recovery() -> RecoveryStrategy:
    """
    Create a Consistency-Prioritised Recovery (CPR) strategy
    
    This strategy extends recovery time in favor of comprehensive 
    synchronization and validation. Optimized for batch-oriented, 
    data-intensive workloads with strict consistency requirements.
    
    Returns:
        RecoveryStrategy configured for consistency prioritization
    """
    return RecoveryStrategy(
        name="Consistency-Prioritised Recovery",
        consistency_level=ConsistencyLevel.STRONG,
        acknowledgement_policy=AcknowledgementPolicy.ALL_REPLICAS,
        partition_reassignment_strategy=PartitionReassignmentStrategy.BALANCED,
        synchronisation_mode=SynchronisationMode.FOREGROUND,
        consumer_rebalance_strategy=ConsumerRebalanceStrategy.EAGER,
        max_replicas_to_restore=3,  # Full replication factor
        validation_enabled=True,
        throttling_enabled=False,
        additional_params={
            "unclean.leader.election.enable": "false",
            "min.insync.replicas": "2",
            "replica.lag.time.max.ms": "30000"  # Less tolerant of replica lag
        }
    )

def create_resource_constrained_recovery() -> RecoveryStrategy:
    """
    Create a Resource-Constrained Recovery (RCR) strategy
    
    This strategy extends recovery time in favor of minimal resource
    utilization through throttled operations and sequential processing.
    Suitable for both workload types under severe resource constraints.
    
    Returns:
        RecoveryStrategy configured for resource constraints
    """
    return RecoveryStrategy(
        name="Resource-Constrained Recovery",
        consistency_level=ConsistencyLevel.EVENTUAL,
        acknowledgement_policy=AcknowledgementPolicy.LEADER_ONLY,
        partition_reassignment_strategy=PartitionReassignmentStrategy.MINIMAL,
        synchronisation_mode=SynchronisationMode.LAZY,
        consumer_rebalance_strategy=ConsumerRebalanceStrategy.COOPERATIVE,
        max_replicas_to_restore=1,
        validation_enabled=False,
        throttling_enabled=True,
        additional_params={
            "unclean.leader.election.enable": "true",
            "min.insync.replicas": "1",
            "replica.fetch.max.bytes": "1048576",  # 1MB (reduced)
            "replica.fetch.response.max.bytes": "10485760",  # 10MB (reduced)
            "num.recovery.threads.per.data.dir": "1"  # Minimize thread usage
        }
    )

def create_critical_data_recovery() -> RecoveryStrategy:
    """
    Create a Critical-Data Recovery (CDR) strategy
    
    This strategy prioritizes data integrity above all else, with the
    longest recovery time but most thorough validation. For batch workloads
    processing irreplaceable or mission-critical data.
    
    Returns:
        RecoveryStrategy configured for critical data protection
    """
    return RecoveryStrategy(
        name="Critical-Data Recovery",
        consistency_level=ConsistencyLevel.STRICT,
        acknowledgement_policy=AcknowledgementPolicy.ALL_REPLICAS,
        partition_reassignment_strategy=PartitionReassignmentStrategy.FASTEST_REPLICA_FIRST,
        synchronisation_mode=SynchronisationMode.FOREGROUND,
        consumer_rebalance_strategy=ConsumerRebalanceStrategy.STATIC,
        max_replicas_to_restore=3,  # Full replication factor
        validation_enabled=True,
        throttling_enabled=False,
        additional_params={
            "unclean.leader.election.enable": "false",
            "min.insync.replicas": "3",  # Maximum consistency
            "replica.lag.time.max.ms": "60000",  # Ensure full sync
            "log.flush.interval.messages": "1",  # Sync after every message
            "log.flush.interval.ms": "1000"  # Frequent disk flushes
        }
    )

def create_balanced_recovery() -> RecoveryStrategy:
    """
    Create a Balanced Recovery (BR) strategy
    
    This strategy strikes a balance between recovery time and
    consistency guarantees. Suitable for mixed workloads or
    ambiguous classification cases.
    
    Returns:
        RecoveryStrategy configured for balanced recovery
    """
    return RecoveryStrategy(
        name="Balanced Recovery",
        consistency_level=ConsistencyLevel.STRONG,
        acknowledgement_policy=AcknowledgementPolicy.QUORUM,
        partition_reassignment_strategy=PartitionReassignmentStrategy.BALANCED,
        synchronisation_mode=SynchronisationMode.BACKGROUND,
        consumer_rebalance_strategy=ConsumerRebalanceStrategy.RANGE,
        max_replicas_to_restore=2,  # N-1 for 3-replica system
        validation_enabled=False,
        throttling_enabled=False,
        additional_params={
            "unclean.leader.election.enable": "false",
            "min.insync.replicas": "2",
            "replica.lag.time.max.ms": "10000"
        }
    )

def create_conservative_recovery() -> RecoveryStrategy:
    """
    Create a Conservative Recovery (CR) strategy
    
    This strategy takes a cautious approach to recovery with
    thorough validation. Suitable for low-confidence classifications
    or highly ambiguous workload characteristics.
    
    Returns:
        RecoveryStrategy configured for conservative recovery
    """
    return RecoveryStrategy(
        name="Conservative Recovery",
        consistency_level=ConsistencyLevel.STRONG,
        acknowledgement_policy=AcknowledgementPolicy.QUORUM,
        partition_reassignment_strategy=PartitionReassignmentStrategy.BALANCED,
        synchronisation_mode=SynchronisationMode.BACKGROUND,
        consumer_rebalance_strategy=ConsumerRebalanceStrategy.RANGE,
        max_replicas_to_restore=3,  # Full replication factor
        validation_enabled=True,
        throttling_enabled=False,
        additional_params={
            "unclean.leader.election.enable": "false",
            "min.insync.replicas": "2",
            "replica.lag.time.max.ms": "15000"
        }
    )

# Dictionary of all available strategies for easy lookup
RECOVERY_STRATEGIES = {
    "APR": create_availability_prioritized_recovery(),
    "CPR": create_consistency_prioritized_recovery(),
    "RCR": create_resource_constrained_recovery(),
    "CDR": create_critical_data_recovery(),
    "BR": create_balanced_recovery(),
    "CR": create_conservative_recovery()
}

def get_strategy(strategy_key: str) -> RecoveryStrategy:
    """
    Get a recovery strategy by key
    
    Args:
        strategy_key: Key for the strategy (e.g., "APR", "CPR")
        
    Returns:
        RecoveryStrategy for the given key
    """
    if strategy_key not in RECOVERY_STRATEGIES:
        raise ValueError(f"Unknown strategy key: {strategy_key}")
    
    return RECOVERY_STRATEGIES[strategy_key]