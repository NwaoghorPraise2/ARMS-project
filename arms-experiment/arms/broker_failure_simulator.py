#!/usr/bin/env python3

import os
import argparse
import subprocess
import time
import random
import logging
import json
import requests
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("failure_simulator.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("failure_simulator")

class KafkaBrokerFailureSimulator:
    def __init__(self, 
                 broker_list, 
                 arms_api_url="http://localhost:5002/api/recovery/status",
                 strategy_api_url="http://localhost:5001/api/strategy",
                 failure_duration=300,
                 interval_between_failures=900,
                 random_failures=False):
        """
        Initialize the Kafka broker failure simulator
        
        Args:
            broker_list: List of Kafka broker containers or service names
            arms_api_url: URL to check ARMS recovery status
            strategy_api_url: URL to get current recovery strategy
            failure_duration: How long to keep broker down (seconds)
            interval_between_failures: Time between simulated failures (seconds)
            random_failures: Whether to randomly select broker to fail
        """
        self.broker_list = broker_list
        self.arms_api_url = arms_api_url
        self.strategy_api_url = strategy_api_url
        self.failure_duration = failure_duration
        self.interval_between_failures = interval_between_failures
        self.random_failures = random_failures
        self.recovery_stats = []
        
        # Create results directory if it doesn't exist
        os.makedirs("failure_results", exist_ok=True)
    
    def simulate_broker_failure(self, broker_name):
        """
        Simulate a broker failure by stopping a Docker container/service
        
        Args:
            broker_name: Name of broker container/service to stop
        """
        logger.info(f"Simulating failure for broker: {broker_name}")
        
        try:
            # Check current strategy before failure
            current_strategy = self.get_current_strategy()
            strategy_name = current_strategy.get("strategy", "UNKNOWN") if current_strategy else "UNKNOWN"
            workload_type = current_strategy.get("workload_type", "UNKNOWN") if current_strategy else "UNKNOWN"
            
            logger.info(f"Current strategy before failure: {strategy_name}, Workload: {workload_type}")
            
            # Stop the broker (Docker container or service)
            cmd = ["docker", "stop", broker_name]
            subprocess.run(cmd, check=True)
            
            logger.info(f"Successfully stopped broker: {broker_name}")
            
            # Record failure start time
            failure_start_time = time.time()
            
            # Wait for recovery to start
            logger.info("Waiting for recovery to start...")
            recovery_started = False
            recovery_start_check_time = time.time()
            
            while time.time() - recovery_start_check_time < 60:  # Check for 60 seconds
                if self.is_recovery_in_progress():
                    recovery_started = True
                    logger.info("Recovery process detected!")
                    break
                time.sleep(2)
            
            if not recovery_started:
                logger.warning("No recovery process detected within 60 seconds")
            
            # Wait for recovery to complete or timeout
            recovery_wait_start = time.time()
            max_recovery_wait = min(300, self.failure_duration - 30)  # Max 5 minutes or less than failure duration
            recovery_completed = False
            recovery_time = None
            
            while time.time() - recovery_wait_start < max_recovery_wait:
                if not self.is_recovery_in_progress():
                    recovery_completed = True
                    recovery_time = time.time() - failure_start_time
                    logger.info(f"Recovery completed in {recovery_time:.2f} seconds")
                    break
                time.sleep(5)
            
            if not recovery_completed:
                logger.warning(f"Recovery did not complete within {max_recovery_wait} seconds")
                recovery_time = max_recovery_wait
            
            # Wait until failure duration is complete
            remaining_time = self.failure_duration - (time.time() - failure_start_time)
            if remaining_time > 0:
                logger.info(f"Waiting {remaining_time:.2f} seconds until broker restart...")
                time.sleep(remaining_time)
            
            # Restart the broker
            cmd = ["docker", "start", broker_name]
            subprocess.run(cmd, check=True)
            logger.info(f"Restarted broker: {broker_name}")
            
            # Check if broker is running
            cmd = ["docker", "inspect", "--format={{.State.Running}}", broker_name]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            broker_running = result.stdout.strip() == "true"
            
            if broker_running:
                logger.info(f"Broker {broker_name} is running again")
            else:
                logger.error(f"Failed to restart broker {broker_name}")
            
            # Record failure details
            failure_stats = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "broker": broker_name,
                "strategy": strategy_name,
                "workload_type": workload_type,
                "failure_duration": self.failure_duration,
                "recovery_time": recovery_time,
                "recovery_completed": recovery_completed,
                "broker_restarted": broker_running
            }
            
            self.recovery_stats.append(failure_stats)
            
            # Save failure stats to file
            self._save_failure_stats(failure_stats)
            
            return failure_stats
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to simulate broker failure: {e}")
            return None
    
    def get_current_strategy(self):
        """Get current recovery strategy from the strategy API"""
        try:
            response = requests.get(self.strategy_api_url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data["status"] == "success":
                    return data["strategy"]
            return None
        except Exception as e:
            logger.error(f"Failed to get current strategy: {e}")
            return None
    
    def is_recovery_in_progress(self):
        """Check if recovery is currently in progress"""
        try:
            response = requests.get(self.arms_api_url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                return data.get("in_progress", False)
            return False
        except Exception as e:
            logger.error(f"Failed to check recovery status: {e}")
            return False
    
    def _save_failure_stats(self, stats):
        """Save failure statistics to a JSON file"""
        filename = f"failure_results/failure_{stats['timestamp'].replace(' ', '_').replace(':', '-')}.json"
        with open(filename, 'w') as f:
            json.dump(stats, f, indent=2)
        logger.info(f"Saved failure statistics to {filename}")
    
    def run_simulation_cycle(self):
        """Run a single simulation cycle"""
        if self.random_failures:
            broker_name = random.choice(self.broker_list)
        else:
            # Cycle through brokers in sequence
            broker_name = self.broker_list[0]
            self.broker_list.append(self.broker_list.pop(0))
        
        logger.info(f"Starting failure simulation cycle for broker: {broker_name}")
        
        # Check if broker is running before attempting to stop it
        cmd = ["docker", "inspect", "--format={{.State.Running}}", broker_name]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            broker_running = result.stdout.strip() == "true"
            
            if not broker_running:
                logger.warning(f"Broker {broker_name} is already stopped, skipping")
                return None
        except subprocess.CalledProcessError:
            logger.warning(f"Unable to check status of broker {broker_name}, skipping")
            return None
        
        # Simulate failure
        stats = self.simulate_broker_failure(broker_name)
        
        return stats
    
    def run_simulation(self, cycles=1):
        """
        Run failure simulation for a specified number of cycles
        
        Args:
            cycles: Number of failure cycles to simulate (0 for infinite)
        """
        logger.info(f"Starting failure simulation for {cycles if cycles > 0 else 'infinite'} cycles")
        
        cycle_count = 0
        try:
            while cycles == 0 or cycle_count < cycles:
                cycle_count += 1
                logger.info(f"Starting cycle {cycle_count}/{cycles if cycles > 0 else 'infinite'}")
                
                # Run a simulation cycle
                self.run_simulation_cycle()
                
                # Wait between failures
                if cycles == 0 or cycle_count < cycles:
                    wait_time = self.interval_between_failures
                    if self.random_failures:
                        # Add some randomness to the interval
                        wait_time = random.uniform(0.8 * wait_time, 1.2 * wait_time)
                    
                    logger.info(f"Waiting {wait_time:.2f} seconds until next failure simulation...")
                    time.sleep(wait_time)
        
        except KeyboardInterrupt:
            logger.info("Simulation interrupted by user")
        
        logger.info(f"Completed {cycle_count} simulation cycles")
        
        # Save summary of all failures
        self._save_summary(cycle_count)
    
    def _save_summary(self, total_cycles):
        """Save a summary of all failure simulations"""
        if not self.recovery_stats:
            logger.warning("No recovery statistics to summarize")
            return
        
        summary = {
            "total_cycles": total_cycles,
            "total_failures": len(self.recovery_stats),
            "failures_completed": sum(1 for s in self.recovery_stats if s["recovery_completed"]),
            "avg_recovery_time": sum(s["recovery_time"] for s in self.recovery_stats if s["recovery_time"]) / len(self.recovery_stats),
            "failures_by_strategy": {},
            "failures_by_workload": {},
            "failures": self.recovery_stats
        }
        
        # Count failures by strategy and workload
        for stat in self.recovery_stats:
            strategy = stat["strategy"]
            workload = stat["workload_type"]
            
            if strategy not in summary["failures_by_strategy"]:
                summary["failures_by_strategy"][strategy] = 0
            summary["failures_by_strategy"][strategy] += 1
            
            if workload not in summary["failures_by_workload"]:
                summary["failures_by_workload"][workload] = 0
            summary["failures_by_workload"][workload] += 1
        
        # Save to file
        filename = f"failure_results/simulation_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w') as f:
            json.dump(summary, f, indent=2)
        logger.info(f"Saved simulation summary to {filename}")
        
        # Print summary to console
        print("\n===== Simulation Summary =====")
        print(f"Total cycles: {total_cycles}")
        print(f"Total failures: {len(self.recovery_stats)}")
        print(f"Failures completed: {summary['failures_completed']} ({summary['failures_completed']/len(self.recovery_stats)*100:.1f}%)")
        print(f"Average recovery time: {summary['avg_recovery_time']:.2f} seconds")
        print("\nFailures by strategy:")
        for strategy, count in summary["failures_by_strategy"].items():
            print(f"  {strategy}: {count} ({count/len(self.recovery_stats)*100:.1f}%)")
        print("\nFailures by workload:")
        for workload, count in summary["failures_by_workload"].items():
            print(f"  {workload}: {count} ({count/len(self.recovery_stats)*100:.1f}%)")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Kafka Broker Failure Simulator")
    parser.add_argument('--brokers', required=True,
                       help='Comma-separated list of Kafka broker containers to simulate failures on')
    parser.add_argument('--arms-api', default="http://localhost:5002/api/recovery/status",
                       help='URL of the ARMS API to check recovery status')
    parser.add_argument('--strategy-api', default="http://localhost:5001/api/strategy",
                       help='URL of the strategy API to get current recovery strategy')
    parser.add_argument('--failure-duration', type=int, default=300,
                       help='How long to keep broker down (seconds)')
    parser.add_argument('--interval', type=int, default=900,
                       help='Time between simulated failures (seconds)')
    parser.add_argument('--cycles', type=int, default=1,
                       help='Number of failure cycles to simulate (0 for infinite)')
    parser.add_argument('--random', action='store_true',
                       help='Randomly select broker to fail (default is sequential)')
    
    args = parser.parse_args()
    
    # Parse broker list
    broker_list = [broker.strip() for broker in args.brokers.split(',')]
    
    # Check if brokers exist
    for broker in broker_list:
        cmd = ["docker", "inspect", broker]
        try:
            subprocess.run(cmd, capture_output=True, check=True)
        except subprocess.CalledProcessError:
            logger.error(f"Broker container {broker} does not exist. Please check broker names.")
            exit(1)
    
    # Initialize and run simulator
    simulator = KafkaBrokerFailureSimulator(
        broker_list=broker_list,
        arms_api_url=args.arms_api,
        strategy_api_url=args.strategy_api,
        failure_duration=args.failure_duration,
        interval_between_failures=args.interval,
        random_failures=args.random
    )
    
    simulator.run_simulation(args.cycles)