#!/usr/bin/env python3

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.model_selection import train_test_split, GridSearchCV, cross_val_score, KFold
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
from sklearn.metrics import confusion_matrix, classification_report, roc_curve, auc
from sklearn.preprocessing import StandardScaler, LabelEncoder
import joblib
import argparse
import os
import logging
import json
import time

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("model_training.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("model_training")

class WorkloadClassifierTrainer:
    def __init__(self, training_data, output_dir="model_output"):
        """Initialize with the training dataset and output directory."""
        self.training_data = training_data
        self.output_dir = output_dir
        self.X_train = None
        self.X_test = None
        self.y_train = None
        self.y_test = None
        self.model = None
        self.best_params = None
        self.feature_names = None
        
        # Create output directory if it doesn't exist
        os.makedirs(self.output_dir, exist_ok=True)
    
    def load_data(self):
        """Load the training data from CSV."""
        logger.info(f"Loading training data from {self.training_data}")
        
        try:
            data = pd.read_csv(self.training_data)
            
            # Check for at least two classes
            workload_counts = data['workload_type'].value_counts()
            logger.info(f"Workload class distribution: {workload_counts.to_dict()}")
            
            if len(workload_counts) < 2:
                logger.error(f"Training data must contain at least two classes, found {len(workload_counts)}")
                return False
            
            # Encode the target variable
            label_encoder = LabelEncoder()
            y = label_encoder.fit_transform(data['workload_type'])
            
            # Save label encoder for later use
            joblib.dump(label_encoder, f"{self.output_dir}/label_encoder.pkl")
            
            # Save class mapping
            class_mapping = {i: label for i, label in enumerate(label_encoder.classes_)}
            with open(f"{self.output_dir}/class_mapping.json", 'w') as f:
                json.dump(class_mapping, f, indent=2)
            
            logger.info(f"Class mapping: {class_mapping}")
            
            # Get feature columns (everything except workload_type)
            X = data.drop('workload_type', axis=1)
            self.feature_names = X.columns.tolist()
            
            # Save feature names for later use
            with open(f"{self.output_dir}/feature_names.json", 'w') as f:
                json.dump(self.feature_names, f, indent=2)
            
            # Split data into training and testing sets
            self.X_train, self.X_test, self.y_train, self.y_test = train_test_split(
                X, y, test_size=0.2, random_state=42, stratify=y
            )
            
            logger.info(f"Data loaded and split: {len(self.X_train)} training samples, {len(self.X_test)} testing samples")
            logger.info(f"Features: {self.feature_names}")
            
            return True
        
        except Exception as e:
            logger.error(f"Error loading data: {e}", exc_info=True)
            return False
    
    def train_model(self, cv_folds=5):
        """Train a Random Forest classifier with hyperparameter tuning."""
        logger.info("Training Random Forest classifier with hyperparameter tuning")
        
        if self.X_train is None or self.y_train is None:
            logger.error("No training data available")
            return False
        
        try:
            # Start timing
            start_time = time.time()
            
            # Define the parameter grid for GridSearchCV
            param_grid = {
                'n_estimators': [50, 100, 200],
                'max_depth': [None, 10, 20, 30],
                'min_samples_split': [2, 5, 10],
                'min_samples_leaf': [1, 2, 4]
            }
            
            # Create a base Random Forest classifier
            rf = RandomForestClassifier(random_state=42)
            
            # Perform grid search with cross-validation
            logger.info(f"Performing grid search with {cv_folds}-fold cross-validation")
            grid_search = GridSearchCV(
                estimator=rf,
                param_grid=param_grid,
                cv=cv_folds,
                scoring='f1',
                n_jobs=-1,
                verbose=1
            )
            
            grid_search.fit(self.X_train, self.y_train)
            
            # Get best parameters and model
            self.best_params = grid_search.best_params_
            self.model = grid_search.best_estimator_
            
            # Log best parameters
            logger.info(f"Best parameters: {self.best_params}")
            logger.info(f"Best cross-validation score: {grid_search.best_score_:.4f}")
            
            # Save best parameters
            with open(f"{self.output_dir}/best_params.json", 'w') as f:
                json.dump(self.best_params, f, indent=2)
            
            # Calculate training time
            training_time = time.time() - start_time
            logger.info(f"Model training completed in {training_time:.2f} seconds")
            
            return True
        
        except Exception as e:
            logger.error(f"Error training model: {e}", exc_info=True)
            return False
    
    def evaluate_model(self):
        """Evaluate the trained model on the test data."""
        logger.info("Evaluating model on test data")
        
        if self.model is None or self.X_test is None or self.y_test is None:
            logger.error("No model or test data available")
            return False
        
        try:
            # Make predictions on test data
            y_pred = self.model.predict(self.X_test)
            
            # Calculate evaluation metrics
            accuracy = accuracy_score(self.y_test, y_pred)
            precision = precision_score(self.y_test, y_pred, average='weighted')
            recall = recall_score(self.y_test, y_pred, average='weighted')
            f1 = f1_score(self.y_test, y_pred, average='weighted')
            
            # Log evaluation metrics
            logger.info(f"Test Accuracy: {accuracy:.4f}")
            logger.info(f"Test Precision: {precision:.4f}")
            logger.info(f"Test Recall: {recall:.4f}")
            logger.info(f"Test F1 Score: {f1:.4f}")
            
            # Create and save classification report
            report = classification_report(self.y_test, y_pred, output_dict=True)
            report_df = pd.DataFrame(report).transpose()
            report_df.to_csv(f"{self.output_dir}/classification_report.csv")
            
            # Create confusion matrix
            cm = confusion_matrix(self.y_test, y_pred)
            
            # Plot and save confusion matrix
            plt.figure(figsize=(8, 6))
            sns.heatmap(cm, annot=True, fmt='d', cmap='Blues')
            plt.title('Confusion Matrix')
            plt.ylabel('True Label')
            plt.xlabel('Predicted Label')
            plt.tight_layout()
            plt.savefig(f"{self.output_dir}/confusion_matrix.png", dpi=300)
            plt.close()
            
            # Calculate and plot ROC curve if binary classification
            if len(np.unique(self.y_test)) == 2:
                y_prob = self.model.predict_proba(self.X_test)[:, 1]
                fpr, tpr, _ = roc_curve(self.y_test, y_prob)
                roc_auc = auc(fpr, tpr)
                
                plt.figure(figsize=(8, 6))
                plt.plot(fpr, tpr, color='darkorange', lw=2, label=f'ROC curve (area = {roc_auc:.2f})')
                plt.plot([0, 1], [0, 1], color='navy', lw=2, linestyle='--')
                plt.xlim([0.0, 1.0])
                plt.ylim([0.0, 1.05])
                plt.xlabel('False Positive Rate')
                plt.ylabel('True Positive Rate')
                plt.title('Receiver Operating Characteristic')
                plt.legend(loc="lower right")
                plt.savefig(f"{self.output_dir}/roc_curve.png", dpi=300)
                plt.close()
            
            # Save evaluation metrics
            eval_metrics = {
                'accuracy': float(accuracy),
                'precision': float(precision),
                'recall': float(recall),
                'f1_score': float(f1)
            }
            
            with open(f"{self.output_dir}/evaluation_metrics.json", 'w') as f:
                json.dump(eval_metrics, f, indent=2)
            
            return True
        
        except Exception as e:
            logger.error(f"Error evaluating model: {e}", exc_info=True)
            return False
    
    def analyze_feature_importance(self):
        """Analyze and visualize feature importance."""
        logger.info("Analyzing feature importance")
        
        if self.model is None or self.feature_names is None:
            logger.error("No model or feature names available")
            return False
        
        try:
            # Get feature importances
            importances = self.model.feature_importances_
            
            # Create DataFrame for feature importances
            feature_importance_df = pd.DataFrame({
                'Feature': self.feature_names,
                'Importance': importances
            })
            
            # Sort by importance
            feature_importance_df = feature_importance_df.sort_values('Importance', ascending=False)
            
            # Save feature importances to CSV
            feature_importance_df.to_csv(f"{self.output_dir}/feature_importance.csv", index=False)
            
            # Create bar plot of feature importances
            plt.figure(figsize=(10, 8))
            sns.barplot(x='Importance', y='Feature', data=feature_importance_df)
            plt.title('Feature Importance')
            plt.tight_layout()
            plt.savefig(f"{self.output_dir}/feature_importance.png", dpi=300)
            plt.close()
            
            logger.info("Top 5 most important features:")
            for _, row in feature_importance_df.head(5).iterrows():
                logger.info(f"{row['Feature']}: {row['Importance']:.4f}")
            
            return True
        
        except Exception as e:
            logger.error(f"Error analyzing feature importance: {e}", exc_info=True)
            return False
    
    def save_model(self):
        """Save the trained model to disk."""
        logger.info("Saving model to disk")
        
        if self.model is None:
            logger.error("No model available to save")
            return False
        
        try:
            # Save the model
            model_path = f"{self.output_dir}/random_forest_model.pkl"
            joblib.dump(self.model, model_path)
            
            logger.info(f"Model saved to {model_path}")
            
            # Save model metadata
            metadata = {
                'model_type': 'RandomForestClassifier',
                'num_features': len(self.feature_names),
                'features': self.feature_names,
                'params': self.best_params,
                'n_classes': len(self.model.classes_),
                'timestamp': time.strftime("%Y-%m-%d %H:%M:%S"),
                'sklearn_version': joblib.__version__
            }
            
            with open(f"{self.output_dir}/model_metadata.json", 'w') as f:
                json.dump(metadata, f, indent=2)
            
            return True
        
        except Exception as e:
            logger.error(f"Error saving model: {e}", exc_info=True)
            return False
    
    def run_training_pipeline(self):
        """Run the complete model training pipeline."""
        logger.info("Starting model training pipeline")
        
        # Step 1: Load the training data
        if not self.load_data():
            return False
        
        # Step 2: Train the model
        if not self.train_model():
            return False
        
        # Step 3: Evaluate the model
        if not self.evaluate_model():
            return False
        
        # Step 4: Analyze feature importance
        if not self.analyze_feature_importance():
            return False
        
        # Step 5: Save the model
        if not self.save_model():
            return False
        
        logger.info("Model training pipeline completed successfully")
        logger.info(f"Model and evaluation artifacts saved to {self.output_dir}")
        
        return True


def main():
    parser = argparse.ArgumentParser(description="Train Random Forest Workload Classifier")
    parser.add_argument("--training-data", default="analysis_output/training_dataset.csv", 
                       help="CSV file containing training data with selected metrics")
    parser.add_argument("--output-dir", default="model_output", 
                       help="Directory to save model and evaluation artifacts")
    parser.add_argument("--cv-folds", type=int, default=5, 
                       help="Number of cross-validation folds for hyperparameter tuning")
    
    args = parser.parse_args()
    
    trainer = WorkloadClassifierTrainer(
        training_data=args.training_data,
        output_dir=args.output_dir
    )
    
    success = trainer.run_training_pipeline()
    
    if success:
        print(f"Training completed successfully. Model saved to {args.output_dir}")
    else:
        print("Training failed. Check the logs for details.")


if __name__ == "__main__":
    main()