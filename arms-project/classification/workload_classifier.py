import os
import time
import json
import logging
import glob
import joblib
import pandas as pd
import numpy as np
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('WorkloadClassifier')

class WorkloadClassifier:
    def __init__(self, model_path):
        self.model_path = model_path
        self.model = None
        self.scaler = None
        self.feature_names = None
        self.load_model()
        logger.info(f"WorkloadClassifier initialized with model: {model_path}")
    
    def _generate_feature_names(self):
        """Generate feature names based on training data"""
        return [
            'message_rate_mean', 'message_rate_std', 'message_rate_max', 
            'cpu_usage_mean', 'cpu_usage_std', 
            'memory_usage_mean', 'memory_usage_std', 
            'latency_p99_mean', 'latency_p99_max', 
            'request_rate_mean', 'request_burst_ratio'
        ]
    
    def load_model(self):
        """Load the classification model from disk"""
        try:
            saved_model = joblib.load(self.model_path)
            self.model = saved_model['model']
            self.scaler = saved_model['scaler']
            
            # Ensure feature names are stored
            self.feature_names = saved_model.get('feature_names', self._generate_feature_names())
            
            logger.info(f"Model loaded from {self.model_path}")
            return True
        except Exception as e:
            logger.error(f"Error loading model: {e}")
            # If no model exists, train a simple one
            logger.info("Training a simple model...")
            self._train_simple_model()
            return False
    
    def _train_simple_model(self):
        """Train a simple model for initial use"""
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.preprocessing import StandardScaler
        import numpy as np
        import pandas as pd
        
        # Create some synthetic data for two workload types
        X = []
        y = []
        
        # Feature names for the synthetic data
        self.feature_names = self._generate_feature_names()
        
        # Real-time event-driven samples
        for i in range(50):
            sample = {
                'message_rate_mean': np.random.uniform(500, 5000),
                'message_rate_std': np.random.uniform(10, 100),
                'message_rate_max': np.random.uniform(1000, 10000),
                'cpu_usage_mean': np.random.uniform(0.4, 0.9),
                'cpu_usage_std': np.random.uniform(0.05, 0.2),
                'memory_usage_mean': np.random.uniform(0.3, 0.7),
                'memory_usage_std': np.random.uniform(0.05, 0.15),
                'latency_p99_mean': np.random.uniform(5, 100),
                'latency_p99_max': np.random.uniform(50, 500),
                'request_rate_mean': np.random.uniform(100, 1000),
                'request_burst_ratio': np.random.uniform(1.5, 3)
            }
            X.append(list(sample.values()))
            y.append("real_time_event_driven")
        
        # Batch data-intensive samples
        for i in range(50):
            sample = {
                'message_rate_mean': np.random.uniform(10, 500),
                'message_rate_std': np.random.uniform(100, 1000),
                'message_rate_max': np.random.uniform(1000, 10000),
                'cpu_usage_mean': np.random.uniform(0.2, 0.8),
                'cpu_usage_std': np.random.uniform(0.2, 0.5),
                'memory_usage_mean': np.random.uniform(0.5, 0.9),
                'memory_usage_std': np.random.uniform(0.15, 0.4),
                'latency_p99_mean': np.random.uniform(100, 5000),
                'latency_p99_max': np.random.uniform(1000, 10000),
                'request_rate_mean': np.random.uniform(5, 100),
                'request_burst_ratio': np.random.uniform(5, 20)
            }
            X.append(list(sample.values()))
            y.append("batch_data_intensive")
        
        # Create a DataFrame to ensure feature names are preserved
        X_df = pd.DataFrame(X, columns=self.feature_names)
        
        # Scale features
        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X_df)
        
        # Train model
        self.model = RandomForestClassifier(n_estimators=100, random_state=42)
        self.model.fit(X_scaled, y)
        
        # Save model with feature names
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        joblib.dump({
            'model': self.model, 
            'scaler': self.scaler, 
            'feature_names': self.feature_names
        }, self.model_path)
        logger.info(f"Simple model trained and saved to {self.model_path}")
    
    def classify(self, features):
        """Classify workload based on features"""
        if self.model is None or self.scaler is None:
            logger.error("Model not loaded")
            return None
        
        # Ensure features are in correct format
        feature_df = pd.DataFrame([features])
        
        # Fill missing values with zeros and ensure all expected features are present
        for col in self.feature_names:
            if col not in feature_df.columns:
                feature_df[col] = 0
        
        # Ensure correct column order
        feature_df = feature_df[self.feature_names]
        
        # Scale features while preserving column names
        features_scaled = self.scaler.transform(feature_df)
        
        # Predict workload type
        workload_type = self.model.predict(features_scaled)[0]
        
        # Get prediction probabilities
        probabilities = self.model.predict_proba(features_scaled)[0]
        confidence = max(probabilities)
        
        result = {
            'workload_type': workload_type,
            'confidence': float(confidence),
            'timestamp': datetime.now().isoformat()
        }
        
        return result
    
    def run_classification_loop(self):
        """Run continuous classification loop"""
        while True:
            try:
                # Get the latest feature file
                feature_files = sorted(glob.glob("/app/data/features_*.json"))
                if not feature_files:
                    logger.info("No feature files found, waiting...")
                    time.sleep(10)
                    continue
                
                latest_file = feature_files[-1]
                
                # Load features
                with open(latest_file, "r") as f:
                    features = json.load(f)
                
                # Classify workload
                result = self.classify(features)
                if result:
                    # Save classification result
                    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                    with open(f"/app/data/classification_{timestamp}.json", "w") as f:
                        json.dump(result, f)
                    
                    logger.info(f"Classification result: {result}")
                
                time.sleep(15)
            except Exception as e:
                logger.error(f"Error in classification loop: {e}")
                time.sleep(30)  # Wait a bit before retrying

if __name__ == "__main__":
    model_path = os.environ.get("MODEL_PATH", "/app/models/workload_classifier.pkl")
    
    classifier = WorkloadClassifier(model_path)
    classifier.run_classification_loop()