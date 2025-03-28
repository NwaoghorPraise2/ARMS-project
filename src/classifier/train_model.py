import argparse
from src.classifier.training import WorkloadClassifierTrainer
from src.common.utils import setup_logging

logger = setup_logging(__name__)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Train ARMS workload classifier')
    parser.add_argument('--data', default='data/training_data.csv',
                      help='Path to training data CSV')
    parser.add_argument('--model-output', default='models/workload_classifier.joblib',
                      help='Path to save trained model')
    
    args = parser.parse_args()
    
    # Create trainer with specified model output path
    trainer = WorkloadClassifierTrainer(model_path=args.model_output)
    
    # Train and save model
    trainer.train_and_save(args.data)
    
    logger.info("Training complete")