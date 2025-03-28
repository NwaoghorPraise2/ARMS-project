import numpy as np
import pandas as pd
import joblib
import logging
from typing import Dict, Tuple, List, Any
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix
from sklearn.preprocessing import StandardScaler

from src.common.models import WorkloadType
from src.common.utils import setup_logging

logger = setup_logging(__name__)

class WorkloadClassifierTrainer:
    """Trains the machine learning model for workload classification"""
    
    def __init__(self, model_path: str = "models/workload_classifier.joblib"):
        """
        Initialize the classifier trainer
        
        Args:
            model_path: Path to save the trained model
        """
        self.model_path = model_path
        self.features = [
            'message_rate', 'message_size_avg', 'message_size_stddev',
            'consumer_lag_avg', 'processing_time_avg', 'inter_message_time_stddev',
            'batch_size_avg', 'topic_partition_count', 'consumer_count',
            'throughput_mbps', 'concurrent_consumers', 'peak_to_average_ratio'
        ]
        self.scaler = StandardScaler()
        self.model = None
        
    def load_training_data(self, filepath: str) -> pd.DataFrame:
        """
        Load training data from CSV file
        
        Args:
            filepath: Path to CSV file with training data
            
        Returns:
            DataFrame with training data
        """
        logger.info(f"Loading training data from {filepath}")
        try:
            df = pd.read_csv(filepath)
            logger.info(f"Loaded {len(df)} training samples")
            return df
        except Exception as e:
            logger.error(f"Error loading training data: {e}")
            raise
            
    def preprocess_data(self, df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
        """
        Preprocess training data
        
        Args:
            df: DataFrame with training data
            
        Returns:
            Tuple of feature array X and label array y
        """
        logger.info("Preprocessing training data")
        
        # Select feature columns and scale
        X = df[self.features].values
        X = self.scaler.fit_transform(X)
        
        # Convert workload_type to numeric labels (0 for batch, 1 for real-time)
        y = np.array([
            1 if workload_type == WorkloadType.REALTIME_EVENT_DRIVEN.value else 0
            for workload_type in df['workload_type']
        ])
        
        logger.info(f"Preprocessed {len(X)} samples with {X.shape[1]} features")
        return X, y
        
    def train_model(self, X: np.ndarray, y: np.ndarray) -> RandomForestClassifier:
        """
        Train the Random Forest classifier with hyperparameter optimization
        
        Args:
            X: Feature array
            y: Label array
            
        Returns:
            Trained classifier model
        """
        logger.info("Training Random Forest classifier with grid search")
        
        # Split data into train and validation sets
        X_train, X_val, y_train, y_val = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        
        # Define parameter grid for grid search
        param_grid = {
            'n_estimators': [100, 200, 300],
            'max_depth': [10, 20, 30, None],
            'min_samples_split': [2, 5, 10],
            'min_samples_leaf': [1, 2, 4]
        }
        
        # Create grid search with cross-validation
        grid_search = GridSearchCV(
            RandomForestClassifier(random_state=42),
            param_grid=param_grid,
            cv=5,
            scoring='f1',
            n_jobs=-1,
            verbose=1
        )
        
        # Train model
        grid_search.fit(X_train, y_train)
        
        # Get best model
        best_model = grid_search.best_estimator_
        logger.info(f"Best parameters: {grid_search.best_params_}")
        
        # Evaluate on validation set
        y_pred = best_model.predict(X_val)
        accuracy = accuracy_score(y_val, y_pred)
        precision = precision_score(y_val, y_pred)
        recall = recall_score(y_val, y_pred)
        f1 = f1_score(y_val, y_pred)
        
        logger.info(f"Validation metrics: accuracy={accuracy:.3f}, precision={precision:.3f}, "
                    f"recall={recall:.3f}, f1={f1:.3f}")
        
        # Calculate feature importance
        feature_importance = sorted(zip(self.features, best_model.feature_importances_),
                                    key=lambda x: x[1], reverse=True)
        logger.info("Feature importance:")
        for feature, importance in feature_importance:
            logger.info(f"  {feature}: {importance:.4f}")
            
        return best_model
    
    def save_model(self, model: RandomForestClassifier, scaler: StandardScaler) -> None:
        """
        Save trained model and scaler to disk
        
        Args:
            model: Trained model
            scaler: Fitted scaler
        """
        import os
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        
        # Save both model and scaler in the same file
        joblib.dump({
            'model': model,
            'scaler': scaler,
            'features': self.features
        }, self.model_path)
        
        logger.info(f"Model saved to {self.model_path}")
    
    def train_and_save(self, data_filepath: str) -> None:
        """
        Complete training process: load data, train model, save model
        
        Args:
            data_filepath: Path to training data CSV
        """
        # Load and preprocess data
        df = self.load_training_data(data_filepath)
        X, y = self.preprocess_data(df)
        
        # Train model
        self.model = self.train_model(X, y)
        
        # Save model and scaler
        self.save_model(self.model, self.scaler)
        
        logger.info("Training completed successfully")