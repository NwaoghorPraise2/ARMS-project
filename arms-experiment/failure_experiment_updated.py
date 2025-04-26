#!/usr/bin/env python3
"""
Kafka Failure Experiment Script

This script runs a series of controlled broker failure experiments with and without
ARMS recovery strategies, collecting metrics for analysis.
"""

import os
import sys
import json
import time
import csv
import argparse
import datetime
import random
import logging
import requests
import subprocess
import pandas as pd
import docker
from concurrent.futures import ThreadPoolExecutor

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("failure_experiment.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("failure_experiment")

class FailureExperiment:
    def __init__(self, 
                config_file=None,
                broker_urls=None,
                workload_api_url="http://workload-generator:5005",
                arms_api_url="http://arms-classifier:5001/api/strategy",
                prometheus_url="http://prometheus:9090/api/v1/query",
                metrics_file="experiment_results.csv",
                stabilization_time=60,
                experiment_runs=15,
                failure_duration=120):
        """
        Initialize the failure experiment
        
        Args:
            config_file: Path to config file (optional)
            broker_urls: List of Kafka broker URLs
            workload_api_url: URL for workload generator API
            arms_api_url: URL for ARMS strategy API
            prometheus_url: URL for Prometheus API
            metrics_file: Path to CSV file for results
            stabilization_time: Time to wait for system to stabilize (seconds)
            experiment_runs: Number of runs per experiment scenario
            failure_duration: How long to wait after failure injection (seconds)
        """
        # Load config from file if provided
        if config_file and os.path.exists(config_file):
            self.load_config(config_file)
        else:
            # Default configuration - use the actual Docker service names
            self.broker_urls = broker_urls or ["kafka1:9092", "kafka2:9093", "kafka3:9094"]
            self.workload_api_url = workload_api_url
            self.arms_api_url = arms_api_url
            self.prometheus_url = prometheus_url
            self.metrics_file = metrics_file
            self.stabilization_time = stabilization_time
            self.experiment_runs = experiment_runs
            self.failure_duration = failure_duration
        
        # Docker client for container operations
        try:
            self.docker_client = docker.from_env()
            logger.info("Successfully connected to Docker")
        except Exception as e:
            logger.error(f"Failed to connect to Docker: {e}")
            self.docker_client = None
        
        # Container names directly from Docker Compose
        self.broker_containers = {
            "kafka1": "kafka1",
            "kafka2": "kafka2",
            "kafka3": "kafka3",
        }
        
        # Map of broker URLs to container names
        self.broker_url_to_container = {}
        for container_name, _ in self.broker_containers.items():
            url = f"{container_name}:9092" if "9092" in self.broker_urls[0] else container_name  # Handle port variations
            self.broker_url_to_container[url] = container_name
        
        # Create metrics file with headers if doesn't exist
        self._init_metrics_file()

    def load_config(self, config_file):
        """Load configuration from JSON file"""
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
            
            self.broker_urls = config.get("broker_urls", ["kafka1:9092", "kafka2:9093", "kafka3:9094"])
            self.workload_api_url = config.get("workload_api_url", "http://workload-generator:5005")
            self.arms_api_url = config.get("arms_api_url", "http://arms-classifier:5001/api/strategy")
            self.prometheus_url = config.get("prometheus_url", "http://prometheus:9090/api/v1/query")
            self.metrics_file = config.get("metrics_file", "experiment_results.csv")
            self.stabilization_time = config.get("stabilization_time", 60)
            self.experiment_runs = config.get("experiment_runs", 15)
            self.failure_duration = config.get("failure_duration", 120)
            
            logger.info(f"Loaded configuration from {config_file}")
        except Exception as e:
            logger.error(f"Error loading config file: {e}")
            raise

    def _init_metrics_file(self):
        """Initialize metrics file with headers if it doesn't exist"""
        if not os.path.exists(self.metrics_file):
            logger.info(f"Creating metrics file: {self.metrics_file}")
            with open(self.metrics_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'experiment_id',
                    'timestamp',
                    'scenario',
                    'run_number',
                    'workload_type',
                    'arms_strategy',
                    'strategy',
                    'broker_url',
                    'recovery_time_seconds',
                    'cpu_usage_percent',
                    'memory_usage_percent',
                    'message_rate_before',
                    'message_rate_during',
                    'message_rate_after',
                    'under_replicated_before',
                    'under_replicated_after',
                    'offline_before',
                    'offline_after',
                    'result',
                    'details'
                ])

    def get_workload_state(self):
        """Get current workload generator state"""
        try:
            response = requests.get(f"{self.workload_api_url}/state", timeout=5)
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Error getting workload state: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Error connecting to workload generator: {e}")
            return None

    def get_workload_metrics(self):
        """Get metrics from workload generator"""
        try:
            response = requests.get(f"{self.workload_api_url}/metrics", timeout=5)
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Error getting workload metrics: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Error connecting to workload generator: {e}")
            return None

    def get_current_strategy(self):
        """Get current ARMS strategy from API"""
        try:
            response = requests.get(self.arms_api_url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success":
                    return data.get("strategy", {})
            return None
        except Exception as e:
            logger.error(f"Error getting strategy: {e}")
            return None

    def start_workload(self, workload_type, duration=3600, total_messages=1000000):
        """
        Start a specific workload type
        
        Args:
            workload_type: "real_time" or "batch"
            duration: Duration in seconds
            total_messages: Target number of messages
        """
        try:
            logger.info(f"Starting {workload_type} workload")
            
            # Build parameters for workload generator
            params = {
                "workload": workload_type,
                "duration": duration,
                "total_messages": total_messages
            }
            
            # Add batch size for batch workloads
            if workload_type == "batch":
                params["batch_size"] = 10000
            
            # Call workload generator API to start workload
            response = requests.post(f"{self.workload_api_url}/start", json=params, timeout=10)
            
            if response.status_code == 200 or response.status_code == 202:
                logger.info(f"Successfully started {workload_type} workload")
                return True
            else:
                logger.error(f"Failed to start workload: {response.status_code} - {response.text}")
                return False
            
        except Exception as e:
            logger.error(f"Error starting workload: {e}")
            return False

    def set_arms_strategy(self, strategy_type, workload_type, enabled=True):
        """
        Set ARMS strategy for experiment
        
        Args:
            strategy_type: "QUICK_REBALANCE", "CONTROLLED_RECOVERY", etc.
            workload_type: "REAL_TIME_EVENT_DRIVEN" or "BATCH_PROCESSING"
            enabled: Whether to enable this strategy
        """
        try:
            if not enabled:
                strategy_type = "DEFAULT"
            
            logger.info(f"Setting ARMS strategy to {strategy_type} for {workload_type} workload")
            
            # Example configuration for different strategies
            configs = {
                "QUICK_REBALANCE": {
                    "leader.imbalance.check.interval.seconds": 30,
                    "leader.imbalance.per.broker.percentage": 10,
                    "num.replica.fetchers": 4,
                    "rebalance.priority": "speed",
                    "replica.fetch.max.bytes": 1048576,
                    "replica.lag.time.max.ms": 10000
                },
                "FULL_RECOVERY": {
                    "leader.imbalance.check.interval.seconds": 60,
                    "leader.imbalance.per.broker.percentage": 15,
                    "num.replica.fetchers": 2,
                    "rebalance.priority": "resource",
                    "replica.fetch.max.bytes": 524288,
                    "replica.lag.time.max.ms": 30000
                },
                "DEFAULT": {
                    "leader.imbalance.check.interval.seconds": 300,
                    "leader.imbalance.per.broker.percentage": 10,
                    "num.replica.fetchers": 1,
                    "rebalance.priority": "controlled",
                    "replica.fetch.max.bytes": 1048576,
                    "replica.lag.time.max.ms": 30000
                }
            }
            
            # Create strategy data
            strategy_data = {
                "status": "success",
                "strategy": {
                    "confidence": 100.0,
                    "config": configs.get(strategy_type, configs["DEFAULT"]),
                    "strategy": strategy_type,
                    "timestamp": time.time(),
                    "workload_type": workload_type
                }
            }
            
            # Send strategy to API
            response = requests.post(
                self.arms_api_url, 
                json=strategy_data,
                timeout=5
            )
            
            if response.status_code == 200 or response.status_code == 202:
                logger.info(f"Successfully set ARMS strategy to {strategy_type}")
                return True
            else:
                logger.error(f"Failed to set ARMS strategy: {response.status_code} - {response.text}")
                return False
            
        except Exception as e:
            logger.error(f"Error setting ARMS strategy: {e}")
            return False

    def trigger_broker_failure(self, broker_url=None):
        """
        Trigger a broker failure by stopping the container
        
        Args:
            broker_url: Specific broker URL to fail (if None, a random one is selected)
        """
        if self.docker_client is None:
            logger.error("Docker client not available")
            return None
        
        # Select broker to fail
        if broker_url is None:
            # Randomly select a broker to fail
            broker_url = random.choice(self.broker_urls)
        
        # Get container name - split host:port and take just the host
        broker_host = broker_url.split(":")[0]
        container_name = self.broker_url_to_container.get(broker_url, broker_host)
        
        logger.info(f"Triggering failure for broker {broker_url} (container: {container_name})")
        
        try:
            # Get the container
            container = self.docker_client.containers.get(container_name)
            
            # Stop the container
            container.stop(timeout=5)
            logger.info(f"Successfully stopped container {container_name}")
            
            return broker_url
            
        except Exception as e:
            logger.error(f"Error stopping container {container_name}: {e}")
            return None

    def restart_broker(self, broker_url):
        """
        Restart a failed broker
        
        Args:
            broker_url: Broker URL to restart
        """
        if self.docker_client is None:
            logger.error("Docker client not available")
            return False
        
        # Get container name - split host:port and take just the host
        broker_host = broker_url.split(":")[0]
        container_name = self.broker_url_to_container.get(broker_url, broker_host)
        
        logger.info(f"Restarting broker {broker_url} (container: {container_name})")
        
        try:
            # Get the container
            container = self.docker_client.containers.get(container_name)
            
            # Start the container
            container.start()
            logger.info(f"Successfully started container {container_name}")
            
            # Wait for container to fully start
            time.sleep(10)
            
            return True
            
        except Exception as e:
            logger.error(f"Error starting container {container_name}: {e}")
            return False

    def get_prometheus_metrics(self, broker_url):
        """Get broker metrics from Prometheus"""
        try:
            # Extract broker name from URL (remove port if present)
            broker_name = broker_url.split(":")[0]
            
            # Construct the JMX port based on broker name
            jmx_port = "9980"  # Default for kafka1
            if broker_name == "kafka2":
                jmx_port = "9981"
            elif broker_name == "kafka3":
                jmx_port = "9982"
            
            # Query for under-replicated partitions
            ur_query = 'kafka_server_replicamanager_underreplicatedpartitions'
            ur_response = requests.get(
                self.prometheus_url,
                params={"query": ur_query},
                timeout=5
            ).json()
            
            # Query for offline partitions
            offline_query = 'kafka_controller_offlinepartitionscount'
            offline_response = requests.get(
                self.prometheus_url,
                params={"query": offline_query},
                timeout=5
            ).json()
            
            # Query for CPU usage using process_cpu_seconds_total rate
            cpu_query = f'rate(process_cpu_seconds_total{{instance="{broker_name}:{jmx_port}"}}[1m]) * 100'
            cpu_response = requests.get(
                self.prometheus_url,
                params={"query": cpu_query},
                timeout=5
            ).json()
            
            # Query for memory usage
            memory_query = f'sum(jvm_memory_bytes_used{{instance="{broker_name}:{jmx_port}"}}) / sum(jvm_memory_bytes_max{{instance="{broker_name}:{jmx_port}"}}) * 100'
            memory_response = requests.get(
                self.prometheus_url,
                params={"query": memory_query},
                timeout=5
            ).json()
            
            # Extract values from responses
            cpu = -1
            memory = -1
            under_replicated = -1
            offline = -1
            
            if ur_response.get('status') == 'success' and ur_response.get('data', {}).get('result'):
                under_replicated = float(ur_response['data']['result'][0]['value'][1])
            
            if offline_response.get('status') == 'success' and offline_response.get('data', {}).get('result'):
                offline = float(offline_response['data']['result'][0]['value'][1])
            
            if cpu_response.get('status') == 'success' and cpu_response.get('data', {}).get('result'):
                cpu = float(cpu_response['data']['result'][0]['value'][1])
            
            if memory_response.get('status') == 'success' and memory_response.get('data', {}).get('result'):
                memory = float(memory_response['data']['result'][0]['value'][1])
            
            return {
                "cpu": cpu,
                "memory": memory,
                "under_replicated": under_replicated,
                "offline": offline
            }
            
        except Exception as e:
            logger.error(f"Error getting Prometheus metrics: {e}")
            return {"cpu": -1, "memory": -1, "under_replicated": -1, "offline": -1}

    def get_message_rate(self):
        """Get current message rate from workload generator"""
        metrics = self.get_workload_metrics()
        if metrics:
            return metrics.get('messages_per_second', -1)
        return -1

    def wait_for_recovery(self, broker_url, max_wait=300):
        """
        Wait for broker to recover (or timeout)
        
        Args:
            broker_url: Broker URL to check
            max_wait: Maximum time to wait in seconds
            
        Returns:
            (recovery_time, success) tuple
        """
        start_time = time.time()
        broker_host = broker_url.split(":")[0]
        container_name = self.broker_url_to_container.get(broker_url, broker_host)
        
        if not container_name:
            logger.error(f"Could not find container for broker URL: {broker_url}")
            return max_wait, False
        
        logger.info(f"Waiting for recovery of broker {broker_url}")
        
        # Keep checking until timeout
        while time.time() - start_time < max_wait:
            try:
                # Check if container is running
                container = self.docker_client.containers.get(container_name)
                if container.status == "running":
                    # Check if Kafka is responding
                    if self.is_kafka_responding(broker_url):
                        recovery_time = time.time() - start_time
                        logger.info(f"Broker {broker_url} recovered in {recovery_time:.2f} seconds")
                        return recovery_time, True
            
            except Exception as e:
                logger.debug(f"Recovery check error: {e}")
            
            # Wait before checking again
            time.sleep(5)
        
        logger.warning(f"Broker {broker_url} did not recover within {max_wait} seconds")
        return max_wait, False

    def is_kafka_responding(self, broker_url):
        """Check if Kafka broker is responding to requests"""
        try:
            # Use docker exec to run a Kafka topics command
            broker_host = broker_url.split(":")[0]
            container_name = self.broker_url_to_container.get(broker_url, broker_host)
            
            cmd = [
                "docker", "exec", container_name,
                "kafka-topics", "--bootstrap-server", broker_url,
                "--list", "--command-config", "/etc/kafka/client.properties"
            ]
            
            # Run with timeout
            result = subprocess.run(cmd, capture_output=True, timeout=10)
            
            # Check result
            return result.returncode == 0
        except Exception as e:
            logger.debug(f"Kafka responsiveness check error: {e}")
            return False

    def collect_recovery_metrics(self, broker_url, recovery_time, success):
        """
        Collect all recovery metrics and log them
        
        Args:
            broker_url: The broker that was failed
            recovery_time: Measured recovery time
            success: Whether recovery was successful
        
        Returns:
            Dictionary of collected metrics
        """
        logger.info("Collecting recovery metrics")
        
        # Get current time
        timestamp = datetime.datetime.now().isoformat()
        
        # Get current strategy
        strategy_data = self.get_current_strategy() or {}
        strategy = strategy_data.get("strategy", "UNKNOWN")
        workload_type = strategy_data.get("workload_type", "UNKNOWN")
        
        # Get workload state
        workload_state = self.get_workload_state() or {}
        current_workload = workload_state.get("current_workload", "UNKNOWN")
        
        # Get message rate
        message_rate = self.get_message_rate()
        
        # Get Prometheus metrics
        prom_metrics = self.get_prometheus_metrics(broker_url)
        
        # Create metrics dictionary
        metrics = {
            'timestamp': timestamp,
            'strategy': strategy,
            'workload_type': workload_type,
            'current_workload': current_workload,
            'recovery_time_seconds': recovery_time,
            'cpu_usage_percent': prom_metrics.get("cpu", -1),
            'memory_usage_percent': prom_metrics.get("memory", -1),
            'message_rate': message_rate,
            'under_replicated': prom_metrics.get("under_replicated", -1),
            'offline': prom_metrics.get("offline", -1),
            'broker_url': broker_url,
            'result': 'SUCCESS' if success else 'FAILURE'
        }
        
        logger.info(f"Collected metrics: {metrics}")
        return metrics

    def run_single_experiment(self, experiment_id, run_number, workload_type, arms_enabled):
        """
        Run a single experiment
        
        Args:
            experiment_id: Unique experiment ID
            run_number: Run number within this experiment
            workload_type: "real_time" or "batch"
            arms_enabled: Whether to enable ARMS strategy
        
        Returns:
            Dictionary of metrics from this run
        """
        # Determine scenario name
        scenario = f"{workload_type}_{'with' if arms_enabled else 'without'}_arms"
        logger.info(f"Starting experiment run {experiment_id}-{run_number}: {scenario}")
        
        # Step 1: Set the appropriate workload type
        workload_kafka_type = "REAL_TIME_EVENT_DRIVEN" if workload_type == "real_time" else "BATCH_PROCESSING"
        
        # Step 2: Configure ARMS strategy
        strategy_type = "QUICK_REBALANCE" if arms_enabled else "DEFAULT" 
        self.set_arms_strategy(strategy_type, workload_kafka_type, arms_enabled)
        
        # Step 3: Start the workload
        self.start_workload(workload_type, duration=3600, total_messages=1000000)
        
        # Step 4: Wait for system to stabilize
        logger.info(f"Waiting {self.stabilization_time}s for system to stabilize")
        time.sleep(self.stabilization_time)
        
        # Step 5: Get pre-failure metrics
        message_rate_before = self.get_message_rate()
        prom_metrics_before = self.get_prometheus_metrics(self.broker_urls[0])
        under_replicated_before = prom_metrics_before.get("under_replicated", -1)
        offline_before = prom_metrics_before.get("offline", -1)
        
        # Step 6: Trigger broker failure
        failed_broker = self.trigger_broker_failure()
        if not failed_broker:
            logger.error("Failed to trigger broker failure, aborting experiment")
            return None
        
        # Step 7: Monitor during recovery process
        recovery_start_time = time.time()
        
        # Collect message rate during recovery
        message_rate_during = -1
        try:
            # Wait a bit for the failure to be detected
            time.sleep(10)
            message_rate_during = self.get_message_rate()
        except:
            pass
        
        # Step 8: Wait for automatic recovery or timeout
        recovery_time, success = self.wait_for_recovery(failed_broker, max_wait=self.failure_duration)
        
        # Step 9: If not recovered, manually restart the broker
        if not success:
            logger.warning(f"Broker {failed_broker} did not recover automatically. Manually restarting.")
            self.restart_broker(failed_broker)
            # Wait for broker to restart
            time.sleep(30)
        
        # Step 10: Get post-recovery metrics
        message_rate_after = self.get_message_rate()
        prom_metrics_after = self.get_prometheus_metrics(self.broker_urls[0])
        under_replicated_after = prom_metrics_after.get("under_replicated", -1)
        offline_after = prom_metrics_after.get("offline", -1)
        
        # Determine CPU and memory during recovery
        cpu_usage = prom_metrics_after.get("cpu", -1)
        memory_usage = prom_metrics_after.get("memory", -1)
        
        # Step 11: Record results
        # Get current strategy
        strategy_data = self.get_current_strategy() or {}
        strategy = strategy_data.get("strategy", "UNKNOWN")
        
        # Record metrics
        metrics = {
            'experiment_id': experiment_id,
            'timestamp': datetime.datetime.now().isoformat(),
            'scenario': scenario,
            'run_number': run_number,
            'workload_type': workload_type,
            'arms_strategy': arms_enabled,
            'strategy': strategy,
            'broker_url': failed_broker,
            'recovery_time_seconds': recovery_time,
            'cpu_usage_percent': cpu_usage,
            'memory_usage_percent': memory_usage,
            'message_rate_before': message_rate_before,
            'message_rate_during': message_rate_during,
            'message_rate_after': message_rate_after,
            'under_replicated_before': under_replicated_before,
            'under_replicated_after': under_replicated_after,
            'offline_before': offline_before,
            'offline_after': offline_after,
            'result': 'SUCCESS' if success else 'FAILURE',
            'details': f"{'Automatic' if success else 'Manual'} recovery"
        }
        
        # Log metrics to file
        self.log_experiment_metrics(metrics)
        
        # Step 12: Wait for system to fully stabilize before the next run
        logger.info(f"Experiment run complete. Waiting {self.stabilization_time}s before next run.")
        time.sleep(self.stabilization_time)
        
        return metrics

    def log_experiment_metrics(self, metrics):
        """Log experiment metrics to CSV file"""
        try:
            with open(self.metrics_file, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    metrics['experiment_id'],
                    metrics['timestamp'],
                    metrics['scenario'],
                    metrics['run_number'],
                    metrics['workload_type'],
                    metrics['arms_strategy'],
                    metrics['strategy'],
                    metrics['broker_url'],
                    metrics['recovery_time_seconds'],
                    metrics['cpu_usage_percent'],
                    metrics['memory_usage_percent'],
                    metrics['message_rate_before'],
                    metrics['message_rate_during'],
                    metrics['message_rate_after'],
                    metrics['under_replicated_before'],
                    metrics['under_replicated_after'],
                    metrics['offline_before'],
                    metrics['offline_after'],
                    metrics['result'],
                    metrics['details']
                ])
            logger.info(f"Logged metrics to {self.metrics_file}")
        except Exception as e:
            logger.error(f"Error logging metrics: {e}")

    def run_experiment_suite(self):
        """Run the full suite of experiments"""
        # Generate unique experiment ID
        experiment_id = f"exp_{int(time.time())}"
        logger.info(f"Starting experiment suite {experiment_id}")
        
        # Define the experiment scenarios (4 scenarios, 15 runs each)
        scenarios = [
            # (workload_type, arms_enabled)
            ("real_time", False),  # Real-time without ARMS
            ("batch", False),      # Batch without ARMS
            ("real_time", True),   # Real-time with ARMS
            ("batch", True)        # Batch with ARMS
        ]
        
        # Run all scenarios
        results = []
        for workload_type, arms_enabled in scenarios:
            scenario_name = f"{workload_type}_{'with' if arms_enabled else 'without'}_arms"
            logger.info(f"Starting scenario: {scenario_name}")
            
            # Run multiple experiments for this scenario
            for run in range(1, self.experiment_runs + 1):
                try:
                    result = self.run_single_experiment(
                        experiment_id=experiment_id,
                        run_number=run,
                        workload_type=workload_type,
                        arms_enabled=arms_enabled
                    )
                    
                    if result:
                        results.append(result)
                    else:
                        logger.error(f"Experiment run {run} for {scenario_name} failed")
                
                except Exception as e:
                    logger.error(f"Error in experiment run {run} for {scenario_name}: {e}")
                    # Continue with next run
        
        # Generate summary report
        self.generate_report(experiment_id, results)
        
        logger.info(f"Experiment suite {experiment_id} completed")
        return results

    def generate_report(self, experiment_id, results):
        """Generate a summary report from experiment results"""
        try:
            # Convert results to DataFrame
            if not results:
                logger.warning("No results to generate report from")
                return
            
            df = pd.DataFrame(results)
            
            # Group by scenario and calculate statistics
            summary = df.groupby(['scenario']).agg({
                'recovery_time_seconds': ['mean', 'min', 'max', 'std'],
                'cpu_usage_percent': 'mean',
                'memory_usage_percent': 'mean',
                'message_rate_before': 'mean',
                'message_rate_during': 'mean',
                'message_rate_after': 'mean',
                'under_replicated_before': 'mean',
                'under_replicated_after': 'mean',
            })
            
            # Calculate recovery impact (percentage of message rate reduction)
            summary['impact'] = (1 - (summary[('message_rate_during', 'mean')] / summary[('message_rate_before', 'mean')])) * 100
            
            # Save summary report
            report_file = f"experiment_summary_{experiment_id}.csv"
            summary.to_csv(report_file)
            
            # Print summary to console
            logger.info(f"Experiment Summary (ID: {experiment_id}):")
            for scenario in summary.index:
                logger.info(f"Scenario: {scenario}")
            logger.info(f"  Avg Recovery Time: {summary.loc[scenario, ('recovery_time_seconds', 'mean')]:.2f}s")
            logger.info(f"  Min Recovery Time: {summary.loc[scenario, ('recovery_time_seconds', 'min')]:.2f}s")
            logger.info(f"  Max Recovery Time: {summary.loc[scenario, ('recovery_time_seconds', 'max')]:.2f}s")
            logger.info(f"  Avg CPU Usage: {summary.loc[scenario, ('cpu_usage_percent', 'mean')]:.2f}%")
            logger.info(f"  Avg Memory Usage: {summary.loc[scenario, ('memory_usage_percent', 'mean')]:.2f}%")
            logger.info(f"  Message Rate Impact: {summary.loc[scenario, 'impact']:.2f}%")
            logger.info("")
            
            logger.info(f"Full summary saved to {report_file}")
            
        except Exception as e:
            logger.error(f"Error generating report: {e}")

def main():
    parser = argparse.ArgumentParser(description='Kafka Failure Experiment')
    parser.add_argument('--config', help='Path to config file')
    parser.add_argument('--brokers', default="kafka1:9092,kafka2:9093,kafka3:9094", 
                       help='Comma-separated list of Kafka broker URLs')
    parser.add_argument('--workload-api', default="http://workload-generator:5005",
                       help='URL for workload generator API')
    parser.add_argument('--arms-api', default="http://arms-classifier:5001/api/strategy",
                       help='URL for ARMS strategy API')
    parser.add_argument('--prometheus', default="http://prometheus:9090/api/v1/query",
                       help='URL for Prometheus API')
    parser.add_argument('--output', default="experiment_results.csv",
                       help='Path to output CSV file')
    parser.add_argument('--stabilization-time', type=int, default=60,
                       help='Time to wait for system to stabilize (seconds)')
    parser.add_argument('--runs', type=int, default=15,
                       help='Number of runs per experiment scenario')
    parser.add_argument('--failure-duration', type=int, default=120,
                       help='How long to wait after failure injection (seconds)')
    parser.add_argument('--scenario', choices=['all', 'real_time_no_arms', 'batch_no_arms', 
                                              'real_time_arms', 'batch_arms'],
                       default='all', help='Specific scenario to run (default: all)')
    
    args = parser.parse_args()
    
    # Parse broker URLs if provided
    broker_urls = [broker.strip() for broker in args.brokers.split(',')]
    
    # Initialize experiment
    experiment = FailureExperiment(
        config_file=args.config,
        broker_urls=broker_urls,
        workload_api_url=args.workload_api,
        arms_api_url=args.arms_api,
        prometheus_url=args.prometheus,
        metrics_file=args.output,
        stabilization_time=args.stabilization_time,
        experiment_runs=args.runs,
        failure_duration=args.failure_duration
    )
    
    # Run specific scenario or all scenarios
    if args.scenario == 'all':
        experiment.run_experiment_suite()
    else:
        # Parse scenario string to parameters
        workload_type = 'real_time' if 'real_time' in args.scenario else 'batch'
        arms_enabled = 'arms' in args.scenario
        
        # Generate experiment ID
        experiment_id = f"exp_{int(time.time())}"
        
        # Run the specific scenario for multiple runs
        results = []
        for run in range(1, args.runs + 1):
            result = experiment.run_single_experiment(
                experiment_id=experiment_id,
                run_number=run,
                workload_type=workload_type,
                arms_enabled=arms_enabled
            )
            if result:
                results.append(result)
        
        # Generate report for this scenario
        experiment.generate_report(experiment_id, results)

if __name__ == "__main__":
    main()