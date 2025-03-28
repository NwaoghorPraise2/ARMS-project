import os
import numpy as np
import joblib
import logging
from typing import Dict, Any, Optional
from src.common.models import WorkloadClassification, WorkloadType
from src.common.utils import setup_logging, get_timestamp

logger = setup_logging(__name__)

class WorkloadClassifier:
    """Classifies workload types based on extracted features"""
    
    def __init__(self, model_path: str = "models/workload_classifier.joblib"):
        """
        Initialize the workload classifier
        
        Args:
            model_path: Path to the trained model file
        """
        self.model_path = model_path
        self.model = None
        self.scaler = None
        self.features = None
        self.load_model()
        
    def load_model(self) -> None:
        """Load the trained model from disk"""
        try:
            if not os.path.exists(self.model_path):
                logger.error(f"Model file not found at {self.model_path}")
                raise FileNotFoundError(f"Model file not found at {self.model_path}")
                
            # Load model, scaler, and feature list
            saved_data = joblib.load(self.model_path)
            self.model = saved_data['model']
            self.scaler = saved_data['scaler']
            self.features = saved_data['features']
            
            logger.info(f"Model loaded from {self.model_path}")
        except Exception as e:
            logger.error(f"Error loading model: {e}")
            raise
            
    def classify(self, features: Dict[str, float]) -> WorkloadClassification:
        """
        Classify workload based on extracted features
        
        Args:
            features: Dictionary of feature values
            
        Returns:
            WorkloadClassification with type and confidence
        """
        try:
            # Extract and order features according to expected order
            feature_vector = []
            for feature_name in self.features:
                if feature_name in features:
                    feature_vector.append(features[feature_name])
                else:
                    logger.warning(f"Feature {feature_name} not found in input, using 0")
                    feature_vector.append(0.0)
            
            # Scale features
            feature_vector = np.array([feature_vector])
            feature_vector = self.scaler.transform(feature_vector)
            
            # Make prediction
            class_probabilities = self.model.predict_proba(feature_vector)[0]
            class_index = np.argmax(class_probabilities)
            confidence = class_probabilities[class_index]
            
            # Convert to WorkloadType
            workload_type = WorkloadType.REALTIME_EVENT_DRIVEN if class_index == 1 else WorkloadType.BATCH_DATA_INTENSIVE
            
            # Create classification result
            classification = WorkloadClassification(
                workload_type=workload_type,
                confidence=float(confidence),
                features=features,
                timestamp=get_timestamp()
            )
            
            logger.info(f"Classified workload as {workload_type.value} with {confidence:.2f} confidence")
            return classification
            
        except Exception as e:
            logger.error(f"Error during classification: {e}")
            # Return default classification with low confidence
            return WorkloadClassification(
                workload_type=WorkloadType.BATCH_DATA_INTENSIVE,
                confidence=0.5,
                features=features,
                timestamp=get_timestamp()
            )