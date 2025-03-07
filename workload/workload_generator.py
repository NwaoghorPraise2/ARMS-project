import random
import uuid
import time
import json
import numpy as np
from datetime import datetime, timedelta

class ARMSWorkloadGenerator:
    """
    AI Workload Generator for Adaptive Recovery Management System (ARMS)
    
    Generates synthetic AI workloads based on the taxonomy for message brokering systems,
    categorizing workloads across four dimensions:
    - Latency Sensitivity
    - Data Criticality
    - Processing Patterns
    - Resource Intensity
    """
    
    def __init__(self, seed=None):
        """Initialize the workload generator with optional seed for reproducibility"""
        if seed is not None:
            random.seed(seed)
            np.random.seed(seed)
            
        # Define taxonomy categories based on the document
        self.latency_sensitivity = {
            "real_time": {"delay_tolerance_ms": (0, 1000), "weight": 0.3},
            "near_real_time": {"delay_tolerance_ms": (1000, 60000), "weight": 0.5},
            "batch": {"delay_tolerance_ms": (60000, 3600000), "weight": 0.2}
        }
        
        self.data_criticality = {
            "mission_critical": {"loss_tolerance": 0.0, "weight": 0.25},
            "business_critical": {"loss_tolerance": 0.01, "weight": 0.45},
            "non_critical": {"loss_tolerance": 0.05, "weight": 0.3}
        }
        
        self.processing_patterns = {
            "event_driven": {"batch_size": 1, "weight": 0.4},
            "stream_processing": {"batch_size": (10, 100), "weight": 0.35},
            "batch_workload": {"batch_size": (1000, 10000), "weight": 0.25}
        }
        
        self.resource_intensity = {
            "compute_intensive": {
                "cpu_usage": (70, 95), 
                "memory_usage": (30, 60), 
                "io_usage": (10, 30), 
                "weight": 0.4
            },
            "io_intensive": {
                "cpu_usage": (20, 50), 
                "memory_usage": (40, 70), 
                "io_usage": (70, 95), 
                "weight": 0.35
            },
            "hybrid": {
                "cpu_usage": (50, 80), 
                "memory_usage": (50, 80), 
                "io_usage": (50, 80), 
                "weight": 0.25
            }
        }
        
        # Define AI model types that can be simulated
        self.ai_model_types = {
            "classification": {"weight": 0.3, "complexity": (1, 5)},
            "regression": {"weight": 0.2, "complexity": (1, 4)},
            "nlp": {"weight": 0.2, "complexity": (3, 8)},
            "computer_vision": {"weight": 0.15, "complexity": (5, 10)},
            "recommendation": {"weight": 0.15, "complexity": (4, 9)}
        }
        
        # Associate examples with taxonomy categories for realistic workload generation
        self.workload_examples = {
            ("real_time", "mission_critical", "event_driven", "compute_intensive"): 
                ["autonomous_vehicle_decision", "emergency_response_system"],
            ("real_time", "mission_critical", "stream_processing", "hybrid"): 
                ["patient_monitoring", "critical_infrastructure_monitoring"],
            ("real_time", "business_critical", "event_driven", "compute_intensive"): 
                ["speech_recognition", "facial_authentication"],
            ("near_real_time", "business_critical", "event_driven", "compute_intensive"): 
                ["fraud_detection", "content_moderation"],
            ("near_real_time", "business_critical", "stream_processing", "io_intensive"): 
                ["real_time_analytics", "language_translation"],
            ("near_real_time", "non_critical", "stream_processing", "hybrid"): 
                ["sentiment_analysis", "social_media_monitoring"],
            ("batch", "business_critical", "batch_workload", "compute_intensive"): 
                ["model_training", "risk_analysis"],
            ("batch", "non_critical", "batch_workload", "io_intensive"): 
                ["log_analysis", "recommendation_batch_processing"]
        }
    
    def _select_weighted_category(self, category_dict):
        """Select a category based on its weight"""
        categories = list(category_dict.keys())
        weights = [category_dict[cat]["weight"] for cat in categories]
        return random.choices(categories, weights=weights, k=1)[0]
    
    def _get_random_range_value(self, value_range):
        """Get a random value from a range tuple"""
        if isinstance(value_range, tuple) and len(value_range) == 2:
            return random.uniform(value_range[0], value_range[1])
        return value_range
    
    def _generate_workload_name(self, latency, criticality, pattern, resource):
        """Generate a realistic workload name based on the taxonomy combination"""
        key = (latency, criticality, pattern, resource)
        if key in self.workload_examples:
            base_name = random.choice(self.workload_examples[key])
        else:
            # For combinations without specific examples, generate a generic name
            base_name = f"{latency}_{pattern}_{resource}_workload"
        
        # Add a unique identifier
        unique_id = str(uuid.uuid4())[:8]
        return f"{base_name}_{unique_id}"
    
    def _generate_processing_time(self, latency_category):
        """Generate appropriate processing time based on latency sensitivity"""
        if latency_category == "real_time":
            return random.uniform(10, 500)  # 10-500ms
        elif latency_category == "near_real_time":
            return random.uniform(500, 30000)  # 0.5-30s
        else:  # batch
            return random.uniform(30000, 1800000)  # 30s-30min
    
    def generate_workload(self):
        """Generate a single synthetic AI workload based on the taxonomy"""
        # Select categories from each taxonomy dimension
        latency_category = self._select_weighted_category(self.latency_sensitivity)
        criticality_category = self._select_weighted_category(self.data_criticality)
        pattern_category = self._select_weighted_category(self.processing_patterns)
        resource_category = self._select_weighted_category(self.resource_intensity)
        model_type = self._select_weighted_category(self.ai_model_types)
        
        # Generate attribute values based on selected categories
        delay_tolerance = self._get_random_range_value(
            self.latency_sensitivity[latency_category]["delay_tolerance_ms"])
        loss_tolerance = self.data_criticality[criticality_category]["loss_tolerance"]
        batch_size = self._get_random_range_value(
            self.processing_patterns[pattern_category]["batch_size"])
        
        # Generate resource utilization values
        cpu_usage = self._get_random_range_value(
            self.resource_intensity[resource_category]["cpu_usage"])
        memory_usage = self._get_random_range_value(
            self.resource_intensity[resource_category]["memory_usage"])
        io_usage = self._get_random_range_value(
            self.resource_intensity[resource_category]["io_usage"])
        
        # Generate model complexity based on model type
        model_complexity = random.randint(
            *self.ai_model_types[model_type]["complexity"])
        
        # Generate a realistic workload name
        workload_name = self._generate_workload_name(
            latency_category, criticality_category, pattern_category, resource_category)
        
        # Calculate processing time based on latency category
        avg_processing_time_ms = self._generate_processing_time(latency_category)
        
        # Return the generated workload as a dictionary
        return {
            "workload_id": str(uuid.uuid4()),
            "name": workload_name,
            "timestamp": datetime.now().isoformat(),
            "taxonomy": {
                "latency_sensitivity": latency_category,
                "data_criticality": criticality_category,
                "processing_pattern": pattern_category,
                "resource_intensity": resource_category
            },
            "model": {
                "type": model_type,
                "complexity": model_complexity
            },
            "parameters": {
                "delay_tolerance_ms": round(delay_tolerance, 2),
                "message_loss_tolerance": loss_tolerance,
                "batch_size": int(batch_size) if isinstance(batch_size, (int, float)) else 1,
                "avg_processing_time_ms": round(avg_processing_time_ms, 2),
                "resource_requirements": {
                    "cpu_percent": round(cpu_usage, 2),
                    "memory_percent": round(memory_usage, 2),
                    "io_percent": round(io_usage, 2)
                }
            }
        }
    
    def generate_workload_batch(self, count=10):
        """Generate multiple workloads with specified distribution"""
        return [self.generate_workload() for _ in range(count)]
    
    def generate_workload_stream(self, duration_seconds=60, rate_range=(1, 10)):
        """Generate a stream of workloads over time with variable arrival rate"""
        start_time = time.time()
        end_time = start_time + duration_seconds
        workloads = []
        
        current_time = start_time
        while current_time < end_time:
            # Vary the arrival rate over time
            arrival_rate = random.uniform(*rate_range)  # workloads per second
            next_arrival = random.expovariate(arrival_rate)  # exponential distribution
            
            # Generate timestamp for this workload
            current_time += next_arrival
            if current_time > end_time:
                break
                
            # Generate workload with timestamp
            workload = self.generate_workload()
            workload["timestamp"] = datetime.fromtimestamp(current_time).isoformat()
            workloads.append(workload)
            
        return workloads
    
    def simulate_failure_scenario(self, workloads, failure_rate=0.05, 
                                recovery_time_range=(1000, 30000)):
        """
        Simulate failure scenarios on a set of workloads
        Args:
            workloads: List of workload dictionaries
            failure_rate: Probability of a workload experiencing failure
            recovery_time_range: Range of recovery times in ms (min, max)
        Returns:
            List of workloads with added failure information
        """
        for workload in workloads:
            if random.random() < failure_rate:
                # Simulate a failure
                failure_type = random.choice([
                    "node_failure", "network_partition", "resource_exhaustion",
                    "message_corruption", "queue_overflow"
                ])
                
                # Calculate recovery time based on workload criticality and latency sensitivity
                criticality_factor = {
                    "mission_critical": 0.7,  # Faster recovery due to priority
                    "business_critical": 1.0,
                    "non_critical": 1.3      # Slower recovery for non-critical workloads
                }[workload["taxonomy"]["data_criticality"]]
                
                latency_factor = {
                    "real_time": 0.6,        # Faster recovery for real-time workloads
                    "near_real_time": 1.0,
                    "batch": 1.5             # Slower recovery for batch workloads
                }[workload["taxonomy"]["latency_sensitivity"]]
                
                base_recovery_time = random.uniform(*recovery_time_range)
                adjusted_recovery_time = base_recovery_time * criticality_factor * latency_factor
                
                # Add failure information to the workload
                workload["failure"] = {
                    "occurred": True,
                    "type": failure_type,
                    "timestamp": (datetime.fromisoformat(workload["timestamp"]) + 
                                 timedelta(seconds=random.uniform(0.1, 5))).isoformat(),
                    "recovery_time_ms": round(adjusted_recovery_time, 2),
                    "messages_affected": random.randint(1, workload["parameters"]["batch_size"]),
                    "resource_impact": {
                        "cpu_percent": round(random.uniform(10, 50), 2),
                        "memory_percent": round(random.uniform(10, 40), 2),
                        "io_percent": round(random.uniform(10, 60), 2)
                    }
                }
            else:
                workload["failure"] = {"occurred": False}
                
        return workloads
    
    def save_workloads_to_file(self, workloads, filename="arms_workloads.json"):
        """Save generated workloads to a JSON file"""
        with open(filename, 'w') as f:
            json.dump(workloads, f, indent=2)
        print(f"Saved {len(workloads)} workloads to {filename}")
    
    def generate_recovery_scenario(self, days=7, workloads_per_day=100, 
                                  failure_rates=(0.03, 0.08)):
        """
        Generate a realistic recovery scenario spanning multiple days
        with varying workload patterns and failure rates
        """
        all_workloads = []
        start_date = datetime.now() - timedelta(days=days)
        
        for day in range(days):
            current_date = start_date + timedelta(days=day)
            
            # Vary failure rates based on time (e.g., higher at night)
            hour_multipliers = {
                "business_hours": 0.7,  # 9am-5pm: lower failure rate
                "evening": 1.0,         # 5pm-11pm: normal failure rate
                "night": 1.5            # 11pm-9am: higher failure rate
            }
            
            # Generate workloads for different times of day
            for period, multiplier in hour_multipliers.items():
                if period == "business_hours":
                    hours_range = range(9, 17)  # 9am-5pm
                elif period == "evening":
                    hours_range = range(17, 23)  # 5pm-11pm
                else:  # night
                    hours_range = list(range(23, 24)) + list(range(0, 9))  # 11pm-9am
                
                workloads_this_period = int(workloads_per_day * 
                                          (len(hours_range) / 24))
                
                daily_workloads = self.generate_workload_batch(count=workloads_this_period)
                
                # Set timestamps within this period
                for workload in daily_workloads:
                    hour = random.choice(hours_range)
                    minute = random.randint(0, 59)
                    second = random.randint(0, 59)
                    workload_time = current_date.replace(
                        hour=hour, minute=minute, second=second)
                    workload["timestamp"] = workload_time.isoformat()
                
                # Apply period-specific failure rates
                failure_rate = random.uniform(*failure_rates) * multiplier
                daily_workloads = self.simulate_failure_scenario(
                    daily_workloads, failure_rate=failure_rate)
                
                all_workloads.extend(daily_workloads)
        
        # Sort workloads by timestamp
        all_workloads.sort(key=lambda w: w["timestamp"])
        return all_workloads


# Example usage
if __name__ == "__main__":
    # Initialize generator with seed for reproducibility
    generator = ARMSWorkloadGenerator(seed=42)
    
    # Generate a single workload
    single_workload = generator.generate_workload()
    print("Single Workload Example:")
    print(json.dumps(single_workload, indent=2))
    print("\n")
    
    # Generate a batch of workloads
    workload_batch = generator.generate_workload_batch(count=5)
    print(f"Generated {len(workload_batch)} workloads")
    
    # Simulate failure scenarios
    workloads_with_failures = generator.simulate_failure_scenario(workload_batch)
    
    # Generate a full recovery scenario
    print("Generating a week-long recovery scenario...")
    recovery_scenario = generator.generate_recovery_scenario(days=3, workloads_per_day=5)
    print(f"Generated {len(recovery_scenario)} workloads in the recovery scenario")
    
    # Save to file
    generator.save_workloads_to_file(recovery_scenario, "arms_recovery_scenario.json")







   
