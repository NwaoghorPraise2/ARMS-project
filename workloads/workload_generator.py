import json
import random
import time
from kafka import KafkaProducer
from datetime import datetime

WORKLOAD_TYPES = [
    "real_time", "near_real_time", "batch"
]
CRITICALITY = [
    "mission_critical", "business_critical", "non_critical"
]
PATTERNS = [
    "event_driven", "stream_processing", "batch"
]
RESOURCE_INTENSITY = [
    "compute_intensive", "io_intensive", "hybrid"
]

producer = KafkaProducer(
    bootstrap_servers=["localhost:9092"],
    value_serializer=lambda v: json.dumps(v).encode("utf-8")
)

def generate_workload():
    return {
        "workload_id": f"{random.randint(1000, 9999)}",
        "timestamp": datetime.utcnow().isoformat(),
        "taxonomy": {
            "latency_sensitivity": random.choice(WORKLOAD_TYPES),
            "data_criticality": random.choice(CRITICALITY),
            "processing_pattern": random.choice(PATTERNS),
            "resource_intensity": random.choice(RESOURCE_INTENSITY)
        },
        "parameters": {
            "message_loss_tolerance": round(random.uniform(0, 0.05), 5),
            "avg_processing_time_ms": random.randint(100, 5000),
            "resource_requirements": {
                "cpu_percent": random.uniform(10, 90),
                "memory_percent": random.uniform(10, 90)
            }
        }
    }

while True:
    workload = generate_workload()
    producer.send("ai_workloads", value=workload)
    print(f"Sent: {workload}")
    time.sleep(1)
