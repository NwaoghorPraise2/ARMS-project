from enum import Enum
from dataclasses import dataclass
from typing import Dict, List, Optional, Any

class WorkloadType(Enum):
    """Enum representing the types of workloads"""
    BATCH_DATA_INTENSIVE = "batch_data_intensive"
    REALTIME_EVENT_DRIVEN = "realtime_event_driven"

@dataclass
class ExperimentConfig:
    workload_type: WorkloadType
    workload_size: str  # "small", "medium", "large" for batch; "low", "medium", "high" for real-time
    failure_scenario: str  # "single_broker", "multiple_broker"
    recovery_approach: str  # "arms_adaptive", "static_optimised", "default_kafka"
    duration_minutes: int
    repetitions: int
    experiment_id: str
