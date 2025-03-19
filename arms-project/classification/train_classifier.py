import os
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split, GridSearchCV
import joblib

def generate_synthetic_training_data(num_samples=1000):
    """Generate synthetic data for training based on known patterns"""
    # Create empty dataframe
    columns = [
        'message_rate_mean', 'message_rate_std', 'message_rate_max',
        'cpu_usage_mean', 'cpu_usage_std',
        'memory_usage_mean', 'memory_usage_std',
        'latency_p99_mean', 'latency_p99_max',
        'request_rate_mean', 'request_burst_ratio'
    ]
    
    data = pd.DataFrame(columns=columns)
    labels = []
    
    # Generate real-time event-driven samples
    for i in range(int(num_samples/2)):
        # Real-time workloads have high message rates with low std deviation
        sample = {
            'message_rate_mean': np.random.uniform(500, 5000),  # High message rate
            'message_rate_std': np.random.uniform(10, 100),     # Low variability
            'message_rate_max': np.random.uniform(1000, 10000), # High peaks
            'cpu_usage_mean': np.random.uniform(0.4, 0.9),      # Moderate to high CPU
            'cpu_usage_std': np.random.uniform(0.05, 0.2),      # Some variability
            'memory_usage_mean': np.random.uniform(0.3, 0.7),   # Moderate memory
            'memory_usage_std': np.random.uniform(0.05, 0.15),  # Low variability
            'latency_p99_mean': np.random.uniform(5, 100),      # Low latency
            'latency_p99_max': np.random.uniform(50, 500),      # Moderate max latency
            'request_rate_mean': np.random.uniform(100, 1000),  # High request rate
            'request_burst_ratio': np.random.uniform(1.5, 3)    # Moderate bursts
        }
        
        data = pd.concat([data, pd.DataFrame([sample])], ignore_index=True)
        labels.append("real_time_event_driven")
    
    # Generate batch data-intensive samples
    for i in range(int(num_samples/2)):
        # Batch workloads have lower average rates but high bursts and variability
        sample = {
            'message_rate_mean': np.random.uniform(10, 500),     # Lower message rate
            'message_rate_std': np.random.uniform(100, 1000),    # High variability
            'message_rate_max': np.random.uniform(1000, 10000),  # High peaks during batches
            'cpu_usage_mean': np.random.uniform(0.2, 0.8),       # Variable CPU
            'cpu_usage_std': np.random.uniform(0.2, 0.5),        # High variability
            'memory_usage_mean': np.random.uniform(0.5, 0.9),    # Higher memory usage
            'memory_usage_std': np.random.uniform(0.15, 0.4),    # High variability
            'latency_p99_mean': np.random.uniform(100, 5000),    # Higher latency
            'latency_p99_max': np.random.uniform(1000, 10000),   # High max latency
            'request_rate_mean': np.random.uniform(5, 100),      # Lower request rate
            'request_burst_ratio': np.random.uniform(5, 20)      # Very high bursts
        }
        
        data = pd.concat([data, pd.DataFrame([sample])], ignore_index=True)
        labels.append("batch_data_intensive")
    
    return data, np.array(labels)

def train_classifier():
    """Train a Random Forest classifier on synthetic data"""
    X, y = generate_synthetic_training_data()
    
    # Split data
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    # Scale features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    # Define parameter grid for optimization
    param_grid = {
        'n_estimators': [50, 100, 200],
        'max_depth': [None, 10, 20, 30],
        'min_samples_split': [2, 5, 10],
        'min_samples_leaf': [1, 2, 4]
    }
    
    # Grid search for best parameters
    grid_search = GridSearchCV(
        RandomForestClassifier(random_state=42),
        param_grid,
        cv=5,
        scoring='f1_macro'
    )
    
    grid_search.fit(X_train_scaled, y_train)
    
    # Get best model
    best_model = grid_search.best_estimator_
    
    # Evaluate model
    accuracy = best_model.score(X_test_scaled, y_test)
    print(f"Model accuracy: {accuracy:.4f}")
    
    # Save model
    model_path = "models/workload_classifier.pkl"
    os.makedirs(os.path.dirname(model_path), exist_ok=True)
    joblib.dump({'model': best_model, 'scaler': scaler}, model_path)
    print(f"Model saved to {model_path}")
    
    return best_model, scaler, accuracy

if __name__ == "__main__":
    train_classifier()
