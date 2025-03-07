import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score

# Generate sample AI workload data
data = pd.DataFrame({
    "latency_sensitivity": np.random.choice([0, 1, 2], 1000),
    "data_criticality": np.random.choice([0, 1, 2], 1000),
    "processing_pattern": np.random.choice([0, 1, 2], 1000),
    "resource_intensity": np.random.choice([0, 1, 2], 1000),
    "avg_processing_time_ms": np.random.randint(100, 5000, 1000),
    "cpu_percent": np.random.uniform(10, 90, 1000),
    "memory_percent": np.random.uniform(10, 90, 1000),
    "label": np.random.choice(["real_time", "batch", "hybrid"], 1000)
})

# Extract features and labels
X = data.drop("label", axis=1)
y = data["label"]

# Split dataset
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Train model
model = RandomForestClassifier(n_estimators=100)
model.fit(X_train, y_train)

# Evaluate accuracy
predictions = model.predict(X_test)
print(f"Model Accuracy: {accuracy_score(y_test, predictions)}")

# Save model
joblib.dump(model, "arms/models/workload_classifier.pkl")
