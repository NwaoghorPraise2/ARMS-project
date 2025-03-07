import json
import joblib
from kafka import KafkaConsumer
from sklearn.preprocessing import LabelEncoder
import numpy as np

# Kafka topic for AI workloads
WORKLOAD_TOPIC = "ai_workloads"

# Load pre-trained classifier model
model = joblib.load("arms/models/workload_classifier.pkl")

# Initialize the LabelEncoder
label_encoder = LabelEncoder()

# Kafka consumer to read workloads
consumer = KafkaConsumer(
    WORKLOAD_TOPIC,
    bootstrap_servers="localhost:9092",
    value_deserializer=lambda v: json.loads(v.decode("utf-8"))
)

def encode_features(workload):
    """Encode categorical features and extract features from workload JSON."""
    taxonomy = workload["taxonomy"]
    parameters = workload["parameters"]
    
    try:
        # Encoding categorical features using LabelEncoder
        taxonomy["latency_sensitivity"] = label_encoder.fit_transform([taxonomy["latency_sensitivity"]])[0]
        taxonomy["data_criticality"] = label_encoder.fit_transform([taxonomy["data_criticality"]])[0]
        taxonomy["processing_pattern"] = label_encoder.fit_transform([taxonomy["processing_pattern"]])[0]
        taxonomy["resource_intensity"] = label_encoder.fit_transform([taxonomy["resource_intensity"]])[0]
        
        # Return the encoded features along with numerical features
        features = [
            taxonomy["latency_sensitivity"],
            taxonomy["data_criticality"],
            taxonomy["processing_pattern"],
            taxonomy["resource_intensity"],
            parameters["avg_processing_time_ms"],
            parameters["resource_requirements"]["cpu_percent"],
            parameters["resource_requirements"]["memory_percent"]
        ]
    except KeyError as e:
        print(f"Missing key in workload: {e}")
        features = [0] * 7  # Fallback values if there's a missing key
    return features

def classify_workload(workload):
    """Classify workload type."""
    features = encode_features(workload)
    
    # Check the features being passed to the model
    print(f"Features extracted: {features}")
    
    try:
        workload_type = model.predict([features])[0]
        print(f"Classified workload: {workload_type}")
    except Exception as e:
        print(f"Error in classification: {e}")
        workload_type = None
    
    return workload_type

print("Listening for workloads...")
for message in consumer:
    workload = message.value
    classify_workload(workload)
