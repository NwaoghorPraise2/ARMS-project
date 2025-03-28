from typing import Dict, List, Any, Optional, Callable
import logging
from src.common.models import WorkloadClassification, SystemState, RecoveryStrategy, WorkloadType
from src.common.utils import setup_logging
from src.selector.strategies import get_strategy, RECOVERY_STRATEGIES

logger = setup_logging(__name__)

class Rule:
    """Represents a single rule for strategy selection"""
    
    def __init__(self, 
                name: str, 
                priority: int, 
                condition: Callable[[WorkloadClassification, SystemState], bool],
                strategy_key: str,
                description: str = ""):
        """
        Initialize a rule
        
        Args:
            name: Rule identifier
            priority: Rule priority (higher number = higher priority)
            condition: Function that determines if the rule applies
            strategy_key: Key of the strategy to apply when rule matches
            description: Human-readable description of the rule
        """
        self.name = name
        self.priority = priority
        self.condition = condition
        self.strategy_key = strategy_key
        self.description = description
        
    def evaluate(self, classification: WorkloadClassification, system_state: SystemState) -> bool:
        """
        Evaluate whether the rule applies to the given classification and system state
        
        Args:
            classification: WorkloadClassification from classifier
            system_state: Current SystemState
            
        Returns:
            True if rule applies, False otherwise
        """
        try:
            return self.condition(classification, system_state)
        except Exception as e:
            logger.error(f"Error evaluating rule {self.name}: {e}")
            return False
    
    def get_strategy(self) -> RecoveryStrategy:
        """
        Get the recovery strategy associated with this rule
        
        Returns:
            RecoveryStrategy for this rule
        """
        return get_strategy(self.strategy_key)
    
    def __str__(self) -> str:
        return f"Rule(name={self.name}, priority={self.priority}, strategy={self.strategy_key})"


class RuleEngine:
    """Engine for evaluating rules and selecting recovery strategies"""
    
    def __init__(self):
        """Initialize the rule engine with default rules"""
        self.rules = self._create_default_rules()
        
    def _create_default_rules(self) -> List[Rule]:
        """
        Create the default set of rules
        
        Returns:
            List of Rule objects
        """
        rules = [
            # Resource constraint rules (highest priority)
            Rule(
                name="severe_resource_constraint",
                priority=100,
                condition=lambda c, s: s.cpu_utilization > 90.0 or s.memory_utilization > 90.0,
                strategy_key="RCR",
                description="Apply resource-constrained recovery when system resources are severely limited"
            ),
            
            # Critical data rules
            Rule(
                name="critical_batch_data",
                priority=90,
                condition=lambda c, s: (
                    c.workload_type == WorkloadType.BATCH_DATA_INTENSIVE and
                    c.confidence > 0.8 and
                    c.features.get('consumer_count', 0) > 5 and  # Multiple consumers monitoring
                    c.features.get('topic_partition_count', 0) > 10  # Large topic
                ),
                strategy_key="CDR",
                description="Apply critical-data recovery for important batch workloads"
            ),
            
            # High-confidence classification rules
            Rule(
                name="high_conf_realtime",
                priority=80,
                condition=lambda c, s: (
                    c.workload_type == WorkloadType.REALTIME_EVENT_DRIVEN and
                    c.confidence > 0.8
                ),
                strategy_key="APR",
                description="Apply availability-prioritized recovery for high-confidence real-time workloads"
            ),
            
            Rule(
                name="high_conf_batch",
                priority=80,
                condition=lambda c, s: (
                    c.workload_type == WorkloadType.BATCH_DATA_INTENSIVE and
                    c.confidence > 0.8
                ),
                strategy_key="CPR",
                description="Apply consistency-prioritized recovery for high-confidence batch workloads"
            ),
            
            # Medium-confidence classification rules
            Rule(
                name="medium_conf_realtime",
                priority=70,
                condition=lambda c, s: (
                    c.workload_type == WorkloadType.REALTIME_EVENT_DRIVEN and
                    0.6 <= c.confidence <= 0.8
                ),
                strategy_key="APR",
                description="Apply availability-prioritized recovery for medium-confidence real-time workloads"
            ),
            
            Rule(
                name="medium_conf_batch",
                priority=70,
                condition=lambda c, s: (
                    c.workload_type == WorkloadType.BATCH_DATA_INTENSIVE and
                    0.6 <= c.confidence <= 0.8
                ),
                strategy_key="CPR",
                description="Apply consistency-prioritized recovery for medium-confidence batch workloads"
            ),
            
            # Low-confidence classification rules
            Rule(
                name="low_conf_realtime",
                priority=60,
                condition=lambda c, s: (
                    c.workload_type == WorkloadType.REALTIME_EVENT_DRIVEN and
                    c.confidence < 0.6
                ),
                strategy_key="BR",
                description="Apply balanced recovery for low-confidence real-time workloads"
            ),
            
            Rule(
                name="low_conf_batch",
                priority=60,
                condition=lambda c, s: (
                    c.workload_type == WorkloadType.BATCH_DATA_INTENSIVE and
                    c.confidence < 0.6
                ),
                strategy_key="BR",
                description="Apply balanced recovery for low-confidence batch workloads"
            ),
            
            # Mixed resource constraint rules
            Rule(
                name="moderate_resource_constraint",
                priority=50,
                condition=lambda c, s: 70.0 < s.cpu_utilization <= 90.0 or 70.0 < s.memory_utilization <= 90.0,
                strategy_key="RCR",
                description="Apply resource-constrained recovery when system resources are moderately limited"
            ),
            
            # Default fallback rule (lowest priority)
            Rule(
                name="default_fallback",
                priority=0,
                condition=lambda c, s: True,  # Always matches
                strategy_key="CR",
                description="Default conservative recovery when no other rules match"
            )
        ]
        
        # Sort rules by priority (descending)
        return sorted(rules, key=lambda r: r.priority, reverse=True)
    
    def select_strategy(self, 
                      classification: WorkloadClassification, 
                      system_state: SystemState) -> tuple[RecoveryStrategy, Rule]:
        """
        Select the best recovery strategy based on classification and system state
        
        Args:
            classification: WorkloadClassification from classifier
            system_state: Current SystemState
            
        Returns:
            Tuple of (selected RecoveryStrategy, matching Rule)
        """
        logger.info("Selecting recovery strategy")
        
        # Evaluate rules in priority order
        for rule in self.rules:
            if rule.evaluate(classification, system_state):
                logger.info(f"Rule matched: {rule.name} (priority {rule.priority})")
                strategy = rule.get_strategy()
                logger.info(f"Selected strategy: {strategy.name}")
                return strategy, rule
        
        # This should never happen due to the default fallback rule
        logger.warning("No rule matched, using Conservative Recovery as fallback")
        return get_strategy("CR"), None
    
    def add_rule(self, rule: Rule) -> None:
        """
        Add a new rule to the engine
        
        Args:
            rule: Rule to add
        """
        self.rules.append(rule)
        # Resort rules by priority
        self.rules = sorted(self.rules, key=lambda r: r.priority, reverse=True)
        logger.info(f"Added rule: {rule.name} (priority {rule.priority})")
    
    def remove_rule(self, rule_name: str) -> None:
        """
        Remove a rule from the engine
        
        Args:
            rule_name: Name of the rule to remove
        """
        self.rules = [r for r in self.rules if r.name != rule_name]
        logger.info(f"Removed rule: {rule_name}")
    
    def get_rules(self) -> List[Dict[str, Any]]:
        """
        Get all rules as dictionaries
        
        Returns:
            List of dictionaries with rule information
        """
        return [
            {
                "name": rule.name,
                "priority": rule.priority,
                "strategy": rule.strategy_key,
                "description": rule.description
            }
            for rule in self.rules
        ]