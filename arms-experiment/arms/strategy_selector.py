import json
import time
import os
import logging
import threading

logger = logging.getLogger("strategy_selector")

# Define recovery strategies
QUICK_REBALANCE = "QUICK_REBALANCE"
RESOURCE_OPTIMIZED = "RESOURCE_OPTIMIZED"
CONTROLLED_GRADUAL = "CONTROLLED_GRADUAL"

# Strategy configurations
STRATEGY_CONFIGS = {
    QUICK_REBALANCE: {
        "leader.imbalance.check.interval.seconds": 30,
        "leader.imbalance.per.broker.percentage": 10,
        "replica.lag.time.max.ms": 10000,
        "replica.fetch.max.bytes": 1048576,
        "num.replica.fetchers": 4,
        "rebalance.priority": "speed"
    },
    RESOURCE_OPTIMIZED: {
        "leader.imbalance.check.interval.seconds": 300,
        "leader.imbalance.per.broker.percentage": 20,
        "replica.lag.time.max.ms": 30000,
        "replica.fetch.max.bytes": 524288,
        "num.replica.fetchers": 2,
        "rebalance.priority": "resource"
    },
    CONTROLLED_GRADUAL: {
        "leader.imbalance.check.interval.seconds": 120,
        "leader.imbalance.per.broker.percentage": 25,
        "replica.lag.time.max.ms": 30000,
        "replica.fetch.max.bytes": 1048576,
        "num.replica.fetchers": 2,
        "rebalance.priority": "controlled"
    }
}

class StrategySelector:
    def __init__(self, buffer_path="/app/data/strategy_buffer.json", update_interval=2):
        """
        Initialize the Strategy Selector
        
        Args:
            buffer_path: Path to store the strategy buffer
            update_interval: How often to update the buffer (in seconds)
        """
        self.buffer_path = buffer_path
        self.update_interval = update_interval
        self.current_strategy = None
        self.current_workload = None
        self.confidence = 0
        self.running = False
        
        # Ensure buffer directory exists
        os.makedirs(os.path.dirname(buffer_path), exist_ok=True)
        
        # Initialize buffer with default strategy
        self._write_to_buffer(CONTROLLED_GRADUAL)
    
    def _write_to_buffer(self, strategy):
        """Write strategy configuration to buffer file"""
        if strategy != self.current_strategy:
            logger.info(f"Updating strategy buffer to: {strategy}")
        
        self.current_strategy = strategy
        
        buffer_data = {
            "timestamp": time.time(),
            "strategy": strategy,
            "config": STRATEGY_CONFIGS[strategy],
            "workload_type": self.current_workload,
            "confidence": self.confidence
        }
        
        with open(self.buffer_path, 'w') as f:
            json.dump(buffer_data, f, indent=2)
    
    def select_strategy(self, workload_type, confidence, actual_workload_type=None):
        """
        Select appropriate recovery strategy based on workload
        
        Args:
            workload_type: The predicted workload type (0 or 1)
            confidence: Confidence score of the prediction (0-100)
            actual_workload_type: Actual workload type from generator (if available)
        """
        self.confidence = confidence
        
        # If actual workload type is available and confidence is high enough to trust it,
        # use it instead of the predicted type
        if actual_workload_type is not None and confidence >= 90:
            logger.info(f"Using actual workload type from generator: {actual_workload_type}")
            workload_type = actual_workload_type
        
        if confidence >= 90:
            if workload_type == 0:  # REAL_TIME_EVENT_DRIVEN
                self.current_workload = "REAL_TIME_EVENT_DRIVEN"
                selected_strategy = QUICK_REBALANCE
            elif workload_type == 1:  # BATCH_DATA_INTENSIVE
                self.current_workload = "BATCH_DATA_INTENSIVE"
                selected_strategy = RESOURCE_OPTIMIZED
            else:
                self.current_workload = "HYBRID_UNKNOWN"
                selected_strategy = CONTROLLED_GRADUAL
        else:
            # Low confidence, use controlled gradual approach
            self.current_workload = "HYBRID_UNKNOWN"
            selected_strategy = CONTROLLED_GRADUAL
        
        # Update buffer with selected strategy
        self._write_to_buffer(selected_strategy)
        return selected_strategy
    
    def start(self):
        """Start the strategy selector service"""
        self.running = True
        
        def buffer_update_loop():
            while self.running:
                # Ensure buffer is always up to date
                if self.current_strategy:
                    self._write_to_buffer(self.current_strategy)
                
                time.sleep(self.update_interval)
        
        # Start buffer update thread
        self.update_thread = threading.Thread(target=buffer_update_loop)
        self.update_thread.daemon = True
        self.update_thread.start()
        logger.info(f"Strategy selector started with update interval {self.update_interval}s")
    
    def stop(self):
        """Stop the strategy selector service"""
        self.running = False
        if hasattr(self, 'update_thread'):
            self.update_thread.join(timeout=30)
        logger.info("Strategy selector stopped")





























# -*- coding: utf-8 -*-
# strategy_selector.py
# import json
# import time
# import os
# import logging
# import threading

# logger = logging.getLogger("strategy_selector")

# # Define recovery strategies
# QUICK_REBALANCE = "QUICK_REBALANCE"
# RESOURCE_OPTIMIZED = "RESOURCE_OPTIMIZED"
# CONTROLLED_GRADUAL = "CONTROLLED_GRADUAL"

# # Strategy configurations
# STRATEGY_CONFIGS = {
#     QUICK_REBALANCE: {
#         "leader.imbalance.check.interval.seconds": 30,
#         "leader.imbalance.per.broker.percentage": 10,
#         "replica.lag.time.max.ms": 10000,
#         "replica.fetch.max.bytes": 1048576,
#         "num.replica.fetchers": 4,
#         "rebalance.priority": "speed"
#     },
#     RESOURCE_OPTIMIZED: {
#         "leader.imbalance.check.interval.seconds": 300,
#         "leader.imbalance.per.broker.percentage": 20,
#         "replica.lag.time.max.ms": 30000,
#         "replica.fetch.max.bytes": 524288,
#         "num.replica.fetchers": 2,
#         "rebalance.priority": "resource"
#     },
#     CONTROLLED_GRADUAL: {
#         "leader.imbalance.check.interval.seconds": 120,
#         "leader.imbalance.per.broker.percentage": 25,
#         "replica.lag.time.max.ms": 30000,
#         "replica.fetch.max.bytes": 1048576,
#         "num.replica.fetchers": 2,
#         "rebalance.priority": "controlled"
#     }
# }

# class StrategySelector:
#     def __init__(self, buffer_path="/app/data/strategy_buffer.json", update_interval=2):
#         """
#         Initialize the Strategy Selector
        
#         Args:
#             buffer_path: Path to store the strategy buffer
#             update_interval: How often to update the buffer (in seconds)
#         """
#         self.buffer_path = buffer_path
#         self.update_interval = update_interval
#         self.current_strategy = None
#         self.current_workload = None
#         self.confidence = 0
#         self.running = False
        
#         # Ensure buffer directory exists
#         os.makedirs(os.path.dirname(buffer_path), exist_ok=True)
        
#         # Initialize buffer with default strategy
#         self._write_to_buffer(CONTROLLED_GRADUAL)
    
#     def _write_to_buffer(self, strategy):
#         """Write strategy configuration to buffer file"""
#         if strategy != self.current_strategy:
#             logger.info(f"Updating strategy buffer to: {strategy}")
        
#         self.current_strategy = strategy
        
#         buffer_data = {
#             "timestamp": time.time(),
#             "strategy": strategy,
#             "config": STRATEGY_CONFIGS[strategy],
#             "workload_type": self.current_workload,
#             "confidence": self.confidence
#         }
        
#         with open(self.buffer_path, 'w') as f:
#             json.dump(buffer_data, f, indent=2)
    
#     def select_strategy(self, workload_type, confidence):
#         """
#         Select appropriate recovery strategy based on workload
        
#         Args:
#             workload_type: The predicted workload type (0 or 1)
#             confidence: Confidence score of the prediction (0-100)
#         """
#         self.confidence = confidence
        
#         if confidence >= 90:
#             if workload_type == 0:  # REAL_TIME_EVENT_DRIVEN
#                 self.current_workload = "REAL_TIME_EVENT_DRIVEN"
#                 selected_strategy = QUICK_REBALANCE
#             elif workload_type == 1:  # BATCH_DATA_INTENSIVE
#                 self.current_workload = "BATCH_DATA_INTENSIVE"
#                 selected_strategy = RESOURCE_OPTIMIZED
#             else:
#                 self.current_workload = "HYBRID_UNKNOWN"
#                 selected_strategy = CONTROLLED_GRADUAL
#         else:
#             # Low confidence, use controlled gradual approach
#             self.current_workload = "HYBRID_UNKNOWN"
#             selected_strategy = CONTROLLED_GRADUAL
        
#         # Update buffer with selected strategy
#         self._write_to_buffer(selected_strategy)
#         return selected_strategy
    
#     def start(self):
#         """Start the strategy selector service"""
#         self.running = True
        
#         def buffer_update_loop():
#             while self.running:
#                 # Ensure buffer is always up to date
#                 if self.current_strategy:
#                     self._write_to_buffer(self.current_strategy)
                
#                 time.sleep(self.update_interval)
        
#         # Start buffer update thread
#         self.update_thread = threading.Thread(target=buffer_update_loop)
#         self.update_thread.daemon = True
#         self.update_thread.start()
#         logger.info(f"Strategy selector started with update interval {self.update_interval}s")
    
#     def stop(self):
#         """Stop the strategy selector service"""
#         self.running = False
#         if hasattr(self, 'update_thread'):
#             self.update_thread.join(timeout=30)
#         logger.info("Strategy selector stopped")