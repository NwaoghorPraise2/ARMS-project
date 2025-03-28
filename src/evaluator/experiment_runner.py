import time
import threading
import json
import logging
import pandas as pd
from typing import Dict, List, Any, Optional
from confluent_kafka import Producer, Consumer

from src.common.models import WorkloadType, ExperimentConfig
from src.common.utils import setup_logging, get_timestamp, json_serialize, send_message
from src.evaluator.experiment_config import ExperimentCondition, ExperimentPlan

logger = setup_logging(__name__)

# Kafka topics for experiment coordination
CONTROL_TOPIC = "arms-experiment-control"
METRICS_TOPIC = "arms-recovery-metrics"
FAILURE_EVENTS_TOPIC = "arms-failure-events"

class ExperimentRunner:
    """Runs experiments according to an experiment plan"""
    
    def __init__(self, bootstrap_servers: str, results_dir: str = "experiments/results"):
        """
        Initialize the experiment runner
        
        Args:
            bootstrap_servers: Kafka bootstrap servers string
            results_dir: Directory to store experiment results
        """
        self.bootstrap_servers = bootstrap_servers
        self.results_dir = results_dir
        
        # Create Kafka producer
        self.producer = Producer({
            'bootstrap.servers': bootstrap_servers,
            'client.id': 'arms-experiment-runner'
        })
        
        # Create Kafka consumer for metrics
        self.consumer = Consumer({
            'bootstrap.servers': bootstrap_servers,
            'group.id': 'arms-experiment-consumer',
            'auto.offset.reset': 'latest',
            'enable.auto.commit': True,
        })
        
        # Subscribe to metrics topics
        self.consumer.subscribe([METRICS_TOPIC])
        
        # State variables
        self.running = False
        self.current_experiment = None
        self.metrics_collector_thread = None
        self.collected_metrics = []
        
    def run_experiment_plan(self, plan: ExperimentPlan) -> pd.DataFrame:
        """
        Run a complete experiment plan
        
        Args:
            plan: ExperimentPlan to run
            
        Returns:
            DataFrame with all collected metrics
        """
        logger.info(f"Running experiment plan: {plan.name} with {len(plan.conditions)} conditions")
        
        all_metrics = []
        
        # Run each condition
        for i, condition in enumerate(plan.conditions):
            logger.info(f"Running condition {i+1}/{len(plan.conditions)}: {condition}")
            
            # Run repetitions
            for rep in range(1, condition.repetitions + 1):
                logger.info(f"  Repetition {rep}/{condition.repetitions}")
                
                # Generate experiment ID
                experiment_id = condition.generate_experiment_id() + f"_rep{rep}"
                
                # Run single experiment
                metrics = self.run_experiment(condition, experiment_id)
                
                if metrics:
                    # Add condition info to metrics
                    for metric in metrics:
                        metric['workload_type'] = condition.workload_type.value
                        metric['workload_size'] = condition.workload_size
                        metric['failure_scenario'] = condition.failure_scenario
                        metric['recovery_approach'] = condition.recovery_approach
                        metric['repetition'] = rep
                        
                    all_metrics.extend(metrics)
                    
                    # Save intermediate results
                    self._save_metrics(all_metrics, f"{plan.name}_intermediate.csv")
                
                # Sleep between repetitions
                time.sleep(30)  # 30-second cooldown between repetitions
        
        # Convert all metrics to DataFrame
        results_df = pd.DataFrame(all_metrics)
        
        # Save final results
        self._save_metrics(all_metrics, f"{plan.name}_complete.csv")
        
        logger.info(f"Completed experiment plan with {len(all_metrics)} total metrics")
        return results_df
    
    def run_experiment(self, condition: ExperimentCondition, experiment_id: str) -> List[Dict[str, Any]]:
        """
        Run a single experiment condition
        
        Args:
            condition: ExperimentCondition to run
            experiment_id: Unique identifier for this experiment
            
        Returns:
            List of collected metrics dictionaries
        """
        try:
            logger.info(f"Starting experiment: {experiment_id}")
            
            # Reset metrics collection
            self.collected_metrics = []
            self.current_experiment = experiment_id
            
            # Start metrics collection thread
            self._start_metrics_collection()
            
            # Create experiment config
            config = ExperimentConfig(
                workload_type=condition.workload_type,
                workload_size=condition.workload_size,
                failure_scenario=condition.failure_scenario,
                recovery_approach=condition.recovery_approach,
                duration_minutes=condition.duration_minutes,
                repetitions=1,  # Each run is one repetition
                experiment_id=experiment_id
            )
            
            # Start workload
            self._start_workload(config)
            
            # Let workload stabilize
            logger.info(f"Allowing workload to stabilize for 60 seconds")
            time.sleep(60)
            
            # Inject failure after stabilization
            self._inject_failure(config)
            
            # Wait for recovery and data collection
            recovery_time = 300  # 5 minutes for recovery
            logger.info(f"Waiting {recovery_time} seconds for recovery and data collection")
            time.sleep(recovery_time)
            
            # Stop workload
            self._stop_workload()
            
            # Stop metrics collection
            self._stop_metrics_collection()
            
            logger.info(f"Experiment {experiment_id} completed with {len(self.collected_metrics)} metrics")
            return self.collected_metrics
            
        except Exception as e:
            logger.error(f"Error running experiment {experiment_id}: {e}")
            self._stop_metrics_collection()
            self._stop_workload()
            return []
    
    def _start_metrics_collection(self) -> None:
        """Start collecting metrics in a background thread"""
        self.running = True
        self.metrics_collector_thread = threading.Thread(
            target=self._collect_metrics,
            name="metrics-collector"
        )
        self.metrics_collector_thread.daemon = True
        self.metrics_collector_thread.start()
        logger.info("Started metrics collection")
    
    def _stop_metrics_collection(self) -> None:
        """Stop collecting metrics"""
        self.running = False
        if self.metrics_collector_thread:
            self.metrics_collector_thread.join(timeout=10)
            self.metrics_collector_thread = None
        logger.info("Stopped metrics collection")
    
    def _collect_metrics(self) -> None:
        """Collect metrics from Kafka in a loop"""
        logger.info("Metrics collector started")
        
        while self.running:
            try:
                # Poll for messages
                msg = self.consumer.poll(timeout=1.0)
                
                if msg is None:
                    continue
                
                if msg.error():
                    logger.error(f"Consumer error: {msg.error()}")
                    continue
                
                # Process message
                try:
                    metric_data = json.loads(msg.value().decode('utf-8'))
                    
                    # Only collect metrics for current experiment
                    experiment_id = metric_data.get('experiment_id', '')
                    if experiment_id and experiment_id == self.current_experiment:
                        self.collected_metrics.append(metric_data)
                        logger.debug(f"Collected metric for {experiment_id}")
                        
                except Exception as e:
                    logger.error(f"Error processing metric: {e}")
                
            except Exception as e:
                logger.error(f"Error in metrics collection: {e}")
            
            # Sleep briefly to avoid tight polling
            time.sleep(0.1)
        
        logger.info("Metrics collector stopped")
    
    def _start_workload(self, config: ExperimentConfig) -> None:
        """
        Start a workload for the experiment
        
        Args:
            config: Experiment configuration
        """
        logger.info(f"Starting workload: {config.workload_type.value} {config.workload_size}")
        
        # Create control message
        control_message = {
            'command': 'start_workload',
            'config': config.__dict__,
            'timestamp': get_timestamp()
        }
        
        # Send to control topic
        send_message(CONTROL_TOPIC, control_message, self.producer)
        
        logger.info(f"Workload start command sent")
    
    def _stop_workload(self) -> None:
        """Stop all workloads"""
        logger.info("Stopping all workloads")
        
        # Create control message
        control_message = {
            'command': 'stop_all_workloads',
            'timestamp': get_timestamp()
        }
        
        # Send to control topic
        send_message(CONTROL_TOPIC, control_message, self.producer)
        
        logger.info("Workload stop command sent")
    
    def _inject_failure(self, config: ExperimentConfig) -> None:
        """
        Inject a failure for the experiment
        
        Args:
            config: Experiment configuration
        """
        logger.info(f"Injecting failure: {config.failure_scenario}")
        
        # Create failure message
        failure_message = {
            'command': 'inject_failure',
            'failure_scenario': config.failure_scenario,
            'recovery_approach': config.recovery_approach,
            'experiment_id': config.experiment_id,
            'timestamp': get_timestamp()
        }
        
        # Send to failure events topic
        send_message(FAILURE_EVENTS_TOPIC, failure_message, self.producer)
        
        logger.info(f"Failure injection command sent")
    
    def _save_metrics(self, metrics: List[Dict[str, Any]], filename: str) -> None:
        """
        Save metrics to a CSV file
        
        Args:
            metrics: List of metric dictionaries
            filename: Filename to save to
        """
        import os
        filepath = os.path.join(self.results_dir, filename)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        # Convert to DataFrame and save
        df = pd.DataFrame(metrics)
        df.to_csv(filepath, index=False)
        
        logger.info(f"Saved {len(metrics)} metrics to {filepath}")
    
    def close(self) -> None:
        """Release resources"""
        self._stop_metrics_collection()
        self._stop_workload()
        
        if self.consumer:
            self.consumer.close()
        
        if self.producer:
            self.producer.flush()
            self.producer.close()
            
        logger.info("Experiment runner closed")