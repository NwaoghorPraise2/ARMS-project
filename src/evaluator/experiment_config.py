import os
from dataclasses import dataclass, asdict
from typing import List, Dict, Any
import yaml
import json
import uuid

from src.common.models import WorkloadType
from src.common.utils import setup_logging

logger = setup_logging(__name__)

@dataclass
class ExperimentCondition:
    """A single experimental condition to evaluate"""
    workload_type: WorkloadType
    workload_size: str  # "small", "medium", "large" for batch; "low", "medium", "high" for real-time
    failure_scenario: str  # "single_broker", "multiple_broker"
    recovery_approach: str  # "arms_adaptive", "static_optimised", "default_kafka"
    repetitions: int = 10
    duration_minutes: int = 10

    def to_dict(self) -> Dict[str, Any]:
        """Convert condition to dictionary"""
        result = asdict(self)
        result['workload_type'] = self.workload_type.value
        return result
    
    def generate_experiment_id(self) -> str:
        """Generate a unique experiment ID based on condition parameters"""
        return f"{self.workload_type.value}_{self.workload_size}_{self.failure_scenario}_{self.recovery_approach}_{uuid.uuid4().hex[:8]}"


class ExperimentPlan:
    """Manages a collection of experiment conditions to run"""
    
    def __init__(self, name: str = "arms_evaluation"):
        """
        Initialize an experiment plan
        
        Args:
            name: Name of the experiment plan
        """
        self.name = name
        self.conditions: List[ExperimentCondition] = []
    
    def add_condition(self, condition: ExperimentCondition) -> None:
        """
        Add an experiment condition to the plan
        
        Args:
            condition: ExperimentCondition to add
        """
        self.conditions.append(condition)
        logger.info(f"Added experiment condition: {condition}")
    
    def generate_full_factorial_plan(self) -> None:
        """Generate a full factorial experiment plan with all combinations"""
        # Define factor levels
        workload_types = [WorkloadType.BATCH_DATA_INTENSIVE, WorkloadType.REALTIME_EVENT_DRIVEN]
        
        workload_sizes = {
            WorkloadType.BATCH_DATA_INTENSIVE: ["small", "medium", "large"],
            WorkloadType.REALTIME_EVENT_DRIVEN: ["low", "medium", "high"]
        }
        
        failure_scenarios = ["single_broker", "multiple_broker"]
        recovery_approaches = ["arms_adaptive", "static_optimised", "default_kafka"]
        
        # Generate all combinations
        for workload_type in workload_types:
            for workload_size in workload_sizes[workload_type]:
                for failure_scenario in failure_scenarios:
                    for recovery_approach in recovery_approaches:
                        condition = ExperimentCondition(
                            workload_type=workload_type,
                            workload_size=workload_size,
                            failure_scenario=failure_scenario,
                            recovery_approach=recovery_approach,
                            repetitions=10,
                            duration_minutes=10
                        )
                        self.add_condition(condition)
        
        logger.info(f"Generated full factorial plan with {len(self.conditions)} conditions")
    
    def save_to_file(self, filepath: str) -> None:
        """
        Save experiment plan to a file
        
        Args:
            filepath: Path to save the experiment plan
        """
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        
        plan_data = {
            "name": self.name,
            "conditions": [condition.to_dict() for condition in self.conditions]
        }
        
        with open(filepath, "w") as f:
            if filepath.endswith(".json"):
                json.dump(plan_data, f, indent=2)
            else:
                yaml.dump(plan_data, f, default_flow_style=False)
        
        logger.info(f"Saved experiment plan to {filepath}")
    
    @classmethod
    def load_from_file(cls, filepath: str) -> "ExperimentPlan":
        """
        Load experiment plan from a file
        
        Args:
            filepath: Path to load the experiment plan from
            
        Returns:
            ExperimentPlan object
        """
        with open(filepath, "r") as f:
            if filepath.endswith(".json"):
                plan_data = json.load(f)
            else:
                plan_data = yaml.safe_load(f)
        
        plan = cls(name=plan_data.get("name", "loaded_plan"))
        
        for condition_dict in plan_data.get("conditions", []):
            workload_type_str = condition_dict.get("workload_type")
            workload_type = WorkloadType(workload_type_str)
            
            condition = ExperimentCondition(
                workload_type=workload_type,
                workload_size=condition_dict.get("workload_size"),
                failure_scenario=condition_dict.get("failure_scenario"),
                recovery_approach=condition_dict.get("recovery_approach"),
                repetitions=condition_dict.get("repetitions", 10),
                duration_minutes=condition_dict.get("duration_minutes", 10)
            )
            plan.add_condition(condition)
        
        logger.info(f"Loaded experiment plan from {filepath} with {len(plan.conditions)} conditions")
        return plan


def create_default_experiment_plan() -> ExperimentPlan:
    """
    Create a default experiment plan for ARMS evaluation
    
    Returns:
        ExperimentPlan object with default configuration
    """
    plan = ExperimentPlan(name="arms_default_evaluation")
    plan.generate_full_factorial_plan()
    return plan