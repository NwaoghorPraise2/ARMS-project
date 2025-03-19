"""
AI Workload Taxonomy for Recovery Requirements
"""

class WorkloadTaxonomy:
    # Workload types
    REAL_TIME_EVENT_DRIVEN = "real_time_event_driven"
    BATCH_DATA_INTENSIVE = "batch_data_intensive"
    
    # Recovery requirements by workload type
    recovery_requirements = {
        REAL_TIME_EVENT_DRIVEN: {
            "max_recovery_time_ms": 30000,  # Based on Hazelwood et al. (2018)
            "message_loss_tolerance": 0.0,  # No message loss acceptable
            "resource_priority": "recovery_speed",  # Prioritize recovery speed
            "preferred_strategy": "quick_rebalance"  # Default strategy
        },
        BATCH_DATA_INTENSIVE: {
            "max_recovery_time_ms": 300000,  # 5 minutes, based on Sharma et al. (2024)
            "message_loss_tolerance": 0.01,  # Can tolerate minor loss
            "resource_priority": "resource_efficiency",  # Prioritize resource usage
            "preferred_strategy": "resource_optimized"  # Default strategy
        }
    }
    
    # Feature thresholds for classification
    classification_thresholds = {
        "message_rate_per_sec": {
            "high": 1000,  # Based on Van Dongen & Van den Poel (2021a)
            "medium": 100,
            "low": 10
        },
        "latency_sensitivity_ms": {
            "high": 100,  # Based on Militone et al. (2023)
            "medium": 1000,
            "low": 10000
        },
        "resource_utilization": {
            "high": 0.8,  # 80% CPU/memory usage
            "medium": 0.5,
            "low": 0.3
        }
    }

class RecoveryStrategies:
    # Strategy definitions
    QUICK_REBALANCE = "quick_rebalance"
    CONTROLLED_GRADUAL = "controlled_gradual"
    RESOURCE_OPTIMIZED = "resource_optimized"
    HIGH_REDUNDANCY = "high_redundancy"
    
    # Strategy configurations
    strategy_configs = {
        QUICK_REBALANCE: {
            "leader.imbalance.check.interval.seconds": 30,
            "leader.imbalance.per.broker.percentage": 10,
            "replica.lag.time.max.ms": 10000,
            "replica.fetch.max.bytes": 1048576,  # 1 MB
            "num.replica.fetchers": 4
        },
        CONTROLLED_GRADUAL: {
            "leader.imbalance.check.interval.seconds": 300,
            "leader.imbalance.per.broker.percentage": 20,
            "replica.lag.time.max.ms": 30000,
            "replica.fetch.max.bytes": 524288,  # 512 KB
            "num.replica.fetchers": 2
        },
        RESOURCE_OPTIMIZED: {
            "leader.imbalance.check.interval.seconds": 600,
            "leader.imbalance.per.broker.percentage": 40,
            "replica.lag.time.max.ms": 60000,
            "replica.fetch.max.bytes": 262144,  # 256 KB
            "num.replica.fetchers": 1
        },
        HIGH_REDUNDANCY: {
            "leader.imbalance.check.interval.seconds": 60,
            "leader.imbalance.per.broker.percentage": 5,
            "replica.lag.time.max.ms": 5000,
            "replica.fetch.max.bytes": 1048576,  # 1 MB
            "num.replica.fetchers": 4,
            "min.insync.replicas": 2
        }
    }
