import os
import time
import argparse
import subprocess
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('FailureSimulator')

def stop_broker(broker_id):
    """Stop a Kafka broker container"""
    logger.info(f"Stopping Kafka broker {broker_id}")
    result = subprocess.run(["docker", "stop", f"kafka{broker_id}"], capture_output=True, text=True)
    if result.returncode == 0:
        logger.info(f"Successfully stopped broker {broker_id}")
    else:
        logger.error(f"Failed to stop broker {broker_id}: {result.stderr}")

def start_broker(broker_id):
    """Start a Kafka broker container"""
    logger.info(f"Starting Kafka broker {broker_id}")
    result = subprocess.run(["docker", "start", f"kafka{broker_id}"], capture_output=True, text=True)
    if result.returncode == 0:
        logger.info(f"Successfully started broker {broker_id}")
    else:
        logger.error(f"Failed to start broker {broker_id}: {result.stderr}")

def simulate_network_partition(broker_id):
    """Simulate a network partition by disconnecting a broker from the network"""
    logger.info(f"Simulating network partition for broker {broker_id}")
    result = subprocess.run([
        "docker", "network", "disconnect", "arms-network", f"kafka{broker_id}"
    ], capture_output=True, text=True)
    
    if result.returncode == 0:
        logger.info(f"Successfully disconnected broker {broker_id} from network")
    else:
        logger.error(f"Failed to disconnect broker {broker_id}: {result.stderr}")

def restore_network(broker_id):
    """Restore network connectivity for a broker"""
    logger.info(f"Restoring network connectivity for broker {broker_id}")
    result = subprocess.run([
        "docker", "network", "connect", "arms-network", f"kafka{broker_id}"
    ], capture_output=True, text=True)
    
    if result.returncode == 0:
        logger.info(f"Successfully reconnected broker {broker_id} to network")
    else:
        logger.error(f"Failed to reconnect broker {broker_id}: {result.stderr}")

def parse_args():
    parser = argparse.ArgumentParser(description='Simulate failures for ARMS testing')
    parser.add_argument('--failure-type', default='broker_shutdown',
                        choices=['broker_shutdown', 'network_partition'],
                        help='Type of failure to simulate')
    parser.add_argument('--broker-id', type=int, default=2,
                        help='ID of the broker to affect (1, 2, or 3)')
    parser.add_argument('--duration', type=int, default=60,
                        help='Duration in seconds to maintain the failure')
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    
    if args.broker_id < 1 or args.broker_id > 3:
        logger.error("Broker ID must be 1, 2, or 3")
        exit(1)
    
    if args.failure_type == 'broker_shutdown':
        # Stop the broker
        stop_broker(args.broker_id)
        
        # Wait for specified duration
        logger.info(f"Waiting for {args.duration} seconds...")
        time.sleep(args.duration)
        
        # Restart the broker
        start_broker(args.broker_id)
    
    elif args.failure_type == 'network_partition':
        # Disconnect broker from network
        simulate_network_partition(args.broker_id)
        
        # Wait for specified duration
        logger.info(f"Waiting for {args.duration} seconds...")
        time.sleep(args.duration)
        
        # Reconnect broker to network
        restore_network(args.broker_id)
    
    else:
        logger.error(f"Unknown failure type: {args.failure_type}")
