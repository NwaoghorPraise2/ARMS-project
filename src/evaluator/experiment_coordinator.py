import os
import argparse
import logging
import time
import json
from typing import Optional

from src.common.utils import setup_logging
from src.evaluator.experiment_config import ExperimentPlan, create_default_experiment_plan
from src.evaluator.experiment_runner import ExperimentRunner
from src.evaluator.analysis import RecoveryAnalyzer

logger = setup_logging(__name__)

class ExperimentCoordinator:
    """Coordinates the execution of experiments and generation of analysis reports"""
    
    def __init__(self, bootstrap_servers: str, 
                 experiment_plan_file: Optional[str] = None,
                 results_dir: str = "experiments/results",
                 analysis_dir: str = "experiments/analysis"):
        """
        Initialize the experiment coordinator
        
        Args:
            bootstrap_servers: Kafka bootstrap servers string
            experiment_plan_file: Path to experiment plan file (optional)
            results_dir: Directory to store experiment results
            analysis_dir: Directory to store analysis outputs
        """
        self.bootstrap_servers = bootstrap_servers
        self.experiment_plan_file = experiment_plan_file
        self.results_dir = results_dir
        self.analysis_dir = analysis_dir
        
        # Ensure directories exist
        os.makedirs(results_dir, exist_ok=True)
        os.makedirs(analysis_dir, exist_ok=True)
        
        # Initialize experiment plan
        self.experiment_plan = self._load_experiment_plan()
        
        # Initialize experiment runner
        self.experiment_runner = ExperimentRunner(bootstrap_servers, results_dir)
    
    def _load_experiment_plan(self) -> ExperimentPlan:
        """
        Load experiment plan from file or create default
        
        Returns:
            ExperimentPlan object
        """
        if self.experiment_plan_file and os.path.exists(self.experiment_plan_file):
            logger.info(f"Loading experiment plan from {self.experiment_plan_file}")
            return ExperimentPlan.load_from_file(self.experiment_plan_file)
        else:
            logger.info("Creating default experiment plan")
            return create_default_experiment_plan()
    
    def run_experiments(self) -> str:
        """
        Run all experiments in the plan
        
        Returns:
            Path to results file
        """
        logger.info(f"Starting experiments for plan: {self.experiment_plan.name}")
        
        try:
            # Run experiments and collect results
            results_df = self.experiment_runner.run_experiment_plan(self.experiment_plan)
            
            # Save results to file
            timestamp = int(time.time())
            results_file = os.path.join(self.results_dir, f"{self.experiment_plan.name}_{timestamp}.csv")
            results_df.to_csv(results_file, index=False)
            
            logger.info(f"Experiment execution completed, results saved to {results_file}")
            return results_file
            
        except Exception as e:
            logger.error(f"Error running experiments: {e}")
            return ""
        finally:
            # Clean up resources
            self.experiment_runner.close()
    
    def run_analysis(self, results_file: str) -> str:
        """
        Run analysis on experiment results
        
        Args:
            results_file: Path to results CSV file
            
        Returns:
            Path to analysis report
        """
        logger.info(f"Starting analysis of results from {results_file}")
        
        try:
            # Create analyzer
            analyzer = RecoveryAnalyzer(results_file, self.analysis_dir)
            
            # Generate comprehensive report
            analyzer.generate_comprehensive_report()
            
            report_file = os.path.join(self.analysis_dir, "evaluation_report.md")
            logger.info(f"Analysis completed, report saved to {report_file}")
            
            return report_file
            
        except Exception as e:
            logger.error(f"Error running analysis: {e}")
            return ""
    
    def run_full_evaluation(self) -> None:
        """Run complete evaluation process: experiments and analysis"""
        logger.info("Starting full evaluation process")
        
        # Run experiments
        results_file = self.run_experiments()
        
        if results_file:
            # Run analysis
            report_file = self.run_analysis(results_file)
            
            if report_file:
                logger.info(f"Full evaluation completed successfully. Report: {report_file}")
            else:
                logger.error("Analysis failed, but experiment results are available")
        else:
            logger.error("Experiment execution failed")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='ARMS Experiment Coordinator')
    parser.add_argument('--bootstrap-servers', default='kafka-1:9092,kafka-2:9092,kafka-3:9092',
                      help='Kafka bootstrap servers')
    parser.add_argument('--experiment-plan', 
                      help='Path to experiment plan file')
    parser.add_argument('--results-dir', default='experiments/results',
                      help='Directory to store experiment results')
    parser.add_argument('--analysis-dir', default='experiments/analysis',
                      help='Directory to store analysis outputs')
    
    args = parser.parse_args()
    
    # Create and run coordinator
    coordinator = ExperimentCoordinator(
        bootstrap_servers=args.bootstrap_servers,
        experiment_plan_file=args.experiment_plan,
        results_dir=args.results_dir,
        analysis_dir=args.analysis_dir
    )
    
    coordinator.run_full_evaluation()