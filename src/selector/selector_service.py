import json
import time
import argparse
import threading
from typing import Dict, Any, Optional

from confluent_kafka import Consumer, Producer

from src.common.models import WorkloadClassification, SystemState, RecoveryStrategy, WorkloadType
from src.common.utils import setup_logging, get_timestamp, json_serialize, receive_message, send_message
from src.selector.rules import RuleEngine

# Set up logging
logger = setup_logging(__name__)

# Topics for communication
CLASSIFICATION_TOPIC = "arms-classifications"
SYSTEM_STATE_TOPIC = "arms-system-state"
STRATEGY_TOPIC = "arms-strategies"

class SelectorService:
    """Service for selecting recovery strategies based on classifications and system state"""
    
    def __init__(self, bootstrap_servers: str):
        """
        Initialize the selector service
        
        Args:
            bootstrap_servers: Kafka bootstrap servers string
        """
        self.bootstrap_servers = bootstrap_servers
        
        # Initialize rule engine
        self.rule_engine = RuleEngine()
        
        # Latest classification and system state
        self.latest_classification: Optional[WorkloadClassification] = None
        self.latest_system_state: Optional[SystemState] = None
        self.classification_lock = threading.Lock()
        self.system_state_lock = threading.Lock()
        
        # Create Kafka consumer for classifications and system state
        self.consumer = Consumer({
            'bootstrap.servers': bootstrap_servers,
            'group.id': 'arms-selector-service',
            'auto.offset.reset': 'latest',
            'enable.auto.commit': True,
        })
        
        # Create Kafka producer for strategies
        self.producer = Producer({
            'bootstrap.servers': bootstrap_servers,
            'client.id': 'arms-strategy-producer'
        })
        
        # Subscribe to topics
        self.consumer.subscribe([CLASSIFICATION_TOPIC, SYSTEM_STATE_TOPIC])
        
        # Service state
        self.running = False
        
    def process_classification(self, message: Dict[str, Any]) -> None:
        """
        Process a classification message
        
        Args:
            message: Classification message from Kafka
        """
        try:
            # Extract classification data
            classification_data = message.get('classification', {})
            
            # Create WorkloadClassification object
            classification = WorkloadClassification(
                workload_type=WorkloadType[classification_data.get('workload_type', 'BATCH_DATA_INTENSIVE')],
                confidence=classification_data.get('confidence', 0.0),
                features=classification_data.get('features', {}),
                timestamp=classification_data.get('timestamp', get_timestamp())
            )
            
            # Update latest classification
            with self.classification_lock:
                self.latest_classification = classification
            
            logger.info(f"Updated classification: {classification.workload_type.value} "
                      f"with {classification.confidence:.2f} confidence")
            
            # Try to select a strategy if we have both classification and system state
            self._try_select_strategy()
            
        except Exception as e:
            logger.error(f"Error processing classification message: {e}")
    
    def process_system_state(self, message: Dict[str, Any]) -> None:
        """
        Process a system state message
        
        Args:
            message: System state message from Kafka
        """
        try:
            # Create SystemState object
            system_state = SystemState(
                cpu_utilization=message.get('cpu_utilization', 0.0),
                memory_utilization=message.get('memory_utilization', 0.0),
                disk_io=message.get('disk_io', 0.0),
                network_io=message.get('network_io', 0.0),
                broker_states=message.get('broker_states', {}),
                timestamp=message.get('timestamp', get_timestamp())
            )
            
            # Update latest system state
            with self.system_state_lock:
                self.latest_system_state = system_state
            
            logger.info(f"Updated system state: CPU {system_state.cpu_utilization:.1f}%, "
                      f"Memory {system_state.memory_utilization:.1f}%")
            
            # Try to select a strategy if we have both classification and system state
            self._try_select_strategy()
            
        except Exception as e:
            logger.error(f"Error processing system state message: {e}")
    
    def _try_select_strategy(self) -> None:
        """
        Try to select a strategy if both classification and system state are available
        """
        # Get latest classification and system state
        with self.classification_lock:
            classification = self.latest_classification
        
        with self.system_state_lock:
            system_state = self.latest_system_state
        
        # If we have both, select a strategy
        if classification and system_state:
            # Don't select a strategy if the data is too old (over 30 seconds)
            classification_age = get_timestamp() - classification.timestamp
            system_state_age = get_timestamp() - system_state.timestamp
            
            if classification_age > 30 or system_state_age > 30:
                logger.warning(f"Data too old for strategy selection: "
                             f"classification age={classification_age:.1f}s, "
                             f"system state age={system_state_age:.1f}s")
                return
            
            # Select strategy
            strategy, rule = self.rule_engine.select_strategy(classification, system_state)
            
            # Prepare message
            strategy_message = {
                'strategy': strategy,
                'rule_name': rule.name if rule else "unknown",
                'rule_description': rule.description if rule else "",
                'workload_type': classification.workload_type.value,
                'workload_confidence': classification.confidence,
                'cpu_utilization': system_state.cpu_utilization,
                'memory_utilization': system_state.memory_utilization,
                'timestamp': get_timestamp()
            }
            
            # Send strategy to Kafka
            send_message(STRATEGY_TOPIC, strategy_message, self.producer)
            
            logger.info(f"Selected strategy {strategy.name} based on rule {rule.name if rule else 'unknown'}")
    
    def run(self) -> None:
        """Run the selector service main loop"""
        self.running = True
        logger.info("Starting selector service")
        
        try:
            while self.running:
                # Poll for messages
                message = receive_message(self.consumer, timeout_ms=1000)
                
                if message:
                    # Determine message type and process accordingly
                    if 'classification' in message:
                        self.process_classification(message)
                    elif 'cpu_utilization' in message:
                        self.process_system_state(message)
                    else:
                        logger.warning(f"Unknown message type: {message}")
                
                # Sleep briefly to avoid tight polling
                time.sleep(0.1)
                
        except KeyboardInterrupt:
            logger.info("Selector service interrupted")
        finally:
            # Clean up resources
            self.running = False
            self.consumer.close()
            logger.info("Selector service stopped")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='ARMS Strategy Selector Service')
    parser.add_argument('--bootstrap-servers', default='kafka-1:9092,kafka-2:9092,kafka-3:9092',
                      help='Kafka bootstrap servers')
    
    args = parser.parse_args()
    
    # Start the service
    service = SelectorService(args.bootstrap_servers)
    service.run()