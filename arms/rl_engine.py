import tensorflow as tf
import numpy as np
import json
from kafka import KafkaAdminClient, KafkaConsumer, KafkaProducer
from kafka.admin import NewTopic

WORKLOAD_TOPIC = "ai_workloads"

# Kafka Admin for dynamic updates
admin_client = KafkaAdminClient(bootstrap_servers="localhost:9092")

# Kafka producer to apply configuration
producer = KafkaProducer(bootstrap_servers="localhost:9092")

# Define the RL model
model = tf.keras.Sequential([
    tf.keras.layers.Dense(64, activation="relu"),
    tf.keras.layers.Dense(32, activation="relu"),
    tf.keras.layers.Dense(3, activation="softmax")  # 3 actions: low, medium, high
])

model.compile(optimizer="adam", loss="mse")

def adjust_kafka_config(workload):
    """Dynamically update Kafka configurations based on workload parameters."""
    # Extract necessary parameters from the workload
    avg_processing_time = workload["parameters"]["avg_processing_time_ms"]
    cpu_percent = workload["parameters"]["resource_requirements"]["cpu_percent"]
    memory_percent = workload["parameters"]["resource_requirements"]["memory_percent"]

    # You can add more logic based on these features for the action selection
    action = np.argmax(model.predict(np.array([[avg_processing_time, cpu_percent, memory_percent]])))
    
    # Set new partition count based on the action
    new_partitions = 1 if action == 0 else (3 if action == 1 else 5)
    print(f"Adjusting Kafka to {new_partitions} partitions based on workload characteristics")

    # Check if the topic exists before attempting to create or alter it
    existing_topics = admin_client.list_topics()

    if WORKLOAD_TOPIC in existing_topics:
        # Alter the topic partitions using create_partitions
        print(f"Topic '{WORKLOAD_TOPIC}' already exists. Attempting to alter partitions.")
        try:
            # Correct usage of create_partitions with the new partition count
            admin_client.create_partitions({
                WORKLOAD_TOPIC: {"partitions": new_partitions}
            })
        except Exception as e:
            print(f"Topic update failed: {e}")
    else:
        # Create a new topic if it doesn't exist
        topic = NewTopic(name=WORKLOAD_TOPIC, num_partitions=new_partitions, replication_factor=1)
        try:
            admin_client.create_topics([topic])
        except Exception as e:
            print(f"Topic creation failed: {e}")

def reinforcement_loop():
    consumer = KafkaConsumer(WORKLOAD_TOPIC, bootstrap_servers="localhost:9092", value_deserializer=lambda v: json.loads(v.decode("utf-8")))
    
    for message in consumer:
        workload = message.value

        # Adjust Kafka topic configuration based on the current workload
        adjust_kafka_config(workload)

        # Feature extraction (to be used for further processing if needed)
        features = np.array([
            workload["parameters"]["avg_processing_time_ms"],
            workload["parameters"]["resource_requirements"]["cpu_percent"],
            workload["parameters"]["resource_requirements"]["memory_percent"]
        ])

        # Predict action (0: low, 1: medium, 2: high)
        action = np.argmax(model.predict(features.reshape(1, -1)))

        # Here you can process the workload data further based on the predicted action
        print(f"Processing workload with action {action}")
        # You can add more processing code here

if __name__ == "__main__":
    print("Starting RL Decision Engine")
    reinforcement_loop()
