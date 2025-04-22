#!/usr/bin/env python3

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import json
import os
import logging
import argparse
from scipy import stats
import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("recovery_analysis.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("recovery_analysis")

class RecoveryAnalyzer:
    def __init__(self, log_dir, output_dir="recovery_analysis"):
        """Initialize with log directory and output directory."""
        self.log_dir = log_dir
        self.output_dir = output_dir
        self.classification_data = None
        self.metrics_data = None
        self.recovery_metrics = None
        
        # Create output directory if it doesn't exist
        os.makedirs(self.output_dir, exist_ok=True)
    
    def load_data(self):
        """Load the classification and metrics data."""
        logger.info(f"Loading data from {self.log_dir}")
        
        try:
            # Load classification log
            classification_path = os.path.join(self.log_dir, "classification_log.csv")
            self.classification_data = pd.read_csv(classification_path)
            
            # Convert timestamp to datetime
            self.classification_data['timestamp'] = pd.to_datetime(self.classification_data['timestamp'])
            
            logger.info(f"Loaded {len(self.classification_data)} classification records")
            
            # Load metrics data
            metrics_path = os.path.join(self.log_dir, "workload_metrics.csv")
            self.metrics_data = pd.read_csv(metrics_path)
            
            # Convert timestamp to datetime
            self.metrics_data['timestamp'] = pd.to_datetime(self.metrics_data['timestamp'])
            
            logger.info(f"Loaded {len(self.metrics_data)} metric records")
            
            return True
        
        except Exception as e:
            logger.error(f"Error loading data: {e}", exc_info=True)
            return False
    
    def identify_recovery_period(self):
        """Identify the recovery period from the metrics data."""
        logger.info("Identifying recovery period")
        
        try:
            # In a real implementation, this would analyze metrics to find 
            # the time when broker failure occurred and when recovery completed
            
            # For this example, we'll simulate by assuming the recovery period
            # can be identified by looking for spikes in under-replicated partitions
            # or by looking for gaps in the metrics data
            
            # Get timestamps in sorted order
            sorted_timestamps = sorted(self.metrics_data['timestamp'].unique())
            
            # Find gaps in the time series that might indicate broker failure
            time_diffs = np.diff(sorted_timestamps) / np.timedelta64(1, 's')
            
            # Identify large gaps (> 10 seconds between consecutive metrics)
            large_gaps = np.where(time_diffs > 10)[0]
            
            if len(large_gaps) > 0:
                # Use the first large gap as the start of recovery
                recovery_start_idx = large_gaps[0]
                recovery_start = sorted_timestamps[recovery_start_idx]
                
                # Assume recovery takes about 2 minutes
                recovery_end = recovery_start + pd.Timedelta(minutes=2)
                
                logger.info(f"Identified recovery period: {recovery_start} to {recovery_end}")
                
                # Extract metrics during recovery period
                self.recovery_metrics = self.metrics_data[
                    (self.metrics_data['timestamp'] >= recovery_start) &
                    (self.metrics_data['timestamp'] <= recovery_end)
                ]
                
                logger.info(f"Extracted {len(self.recovery_metrics)} metrics during recovery")
                
                # Save recovery period info
                recovery_info = {
                    'recovery_start': recovery_start.isoformat(),
                    'recovery_end': recovery_end.isoformat(),
                    'recovery_duration_seconds': (recovery_end - recovery_start).total_seconds()
                }
                
                with open(os.path.join(self.output_dir, "recovery_period.json"), 'w') as f:
                    json.dump(recovery_info, f, indent=2)
                
                return True
            else:
                logger.warning("No clear recovery period identified")
                return False
        
        except Exception as e:
            logger.error(f"Error identifying recovery period: {e}", exc_info=True)
            return False
    
    def calculate_recovery_time(self):
        """Calculate the recovery time metrics."""
        logger.info("Calculating recovery time metrics")
        
        try:
            if self.recovery_metrics is None:
                logger.error("No recovery metrics available")
                return False
            
            # In a real implementation, this would analyze various metrics to determine
            # when the system returned to a stable state
            
            # Calculate recovery time by workload type
            recovery_times = {}
            
            # For each workload type
            for workload_type in self.recovery_metrics['workload_type'].unique():
                # Filter metrics for this workload type
                workload_metrics = self.recovery_metrics[
                    self.recovery_metrics['workload_type'] == workload_type
                ]
                
                # Sort by timestamp
                workload_metrics = workload_metrics.sort_values('timestamp')
                
                # Calculate when metrics returned to normal
                # This is a simplified example - in a real implementation you would
                # look for specific patterns in the metrics
                
                # For example, assume recovery is complete when CPU usage drops below 70%
                if 'cpu_usage' in workload_metrics.columns:
                    recovery_complete = workload_metrics[workload_metrics['cpu_usage'] < 0.7]
                    
                    if not recovery_complete.empty:
                        recovery_time = (recovery_complete.iloc[0]['timestamp'] - 
                                         workload_metrics.iloc[0]['timestamp']).total_seconds()
                    else:
                        # If never drops below threshold, use the full period
                        recovery_time = (workload_metrics.iloc[-1]['timestamp'] - 
                                         workload_metrics.iloc[0]['timestamp']).total_seconds()
                else:
                    # If no CPU usage metric, use the full period
                    recovery_time = (workload_metrics.iloc[-1]['timestamp'] - 
                                     workload_metrics.iloc[0]['timestamp']).total_seconds()
                
                recovery_times[workload_type] = recovery_time
            
            logger.info(f"Recovery times by workload type: {recovery_times}")
            
            # Save recovery times
            with open(os.path.join(self.output_dir, "recovery_times.json"), 'w') as f:
                json.dump(recovery_times, f, indent=2)
            
            return recovery_times
        
        except Exception as e:
            logger.error(f"Error calculating recovery time: {e}", exc_info=True)
            return None
    
    def analyze_resource_usage(self):
        """Analyze resource usage during recovery."""
        logger.info("Analyzing resource usage during recovery")
        
        try:
            if self.recovery_metrics is None:
                logger.error("No recovery metrics available")
                return False
            
            # Calculate resource usage statistics by workload type
            resource_stats = {}
            
            # For each workload type
            for workload_type in self.recovery_metrics['workload_type'].unique():
                # Filter metrics for this workload type
                workload_metrics = self.recovery_metrics[
                    self.recovery_metrics['workload_type'] == workload_type
                ]
                
                # Calculate statistics for CPU and memory usage
                cpu_stats = {
                    'mean': workload_metrics['cpu_usage'].mean() if 'cpu_usage' in workload_metrics.columns else 0,
                    'max': workload_metrics['cpu_usage'].max() if 'cpu_usage' in workload_metrics.columns else 0,
                    'min': workload_metrics['cpu_usage'].min() if 'cpu_usage' in workload_metrics.columns else 0
                }
                
                memory_stats = {
                    'mean': workload_metrics['memory_usage'].mean() if 'memory_usage' in workload_metrics.columns else 0,
                    'max': workload_metrics['memory_usage'].max() if 'memory_usage' in workload_metrics.columns else 0,
                    'min': workload_metrics['memory_usage'].min() if 'memory_usage' in workload_metrics.columns else 0
                }
                
                resource_stats[workload_type] = {
                    'cpu': cpu_stats,
                    'memory': memory_stats
                }
            
            logger.info(f"Resource usage statistics calculated")
            
            # Save resource statistics
            with open(os.path.join(self.output_dir, "resource_stats.json"), 'w') as f:
                json.dump(resource_stats, f, indent=2)
            
            return resource_stats
        
        except Exception as e:
            logger.error(f"Error analyzing resource usage: {e}", exc_info=True)
            return None
    
    def perform_anova_analysis(self):
        """Perform ANOVA analysis to compare recovery strategies."""
        logger.info("Performing ANOVA analysis for recovery comparison")
        
        try:
            if self.recovery_metrics is None:
                logger.error("No recovery metrics available")
                return False
            
            # Group data by selected strategy
            strategies = self.classification_data['selected_strategy'].unique()
            
            # Create a dictionary to store ANOVA results
            anova_results = {}
            
            # Analyze recovery metrics by strategy
            for metric in ['cpu_usage', 'memory_usage']:
                if metric not in self.recovery_metrics.columns:
                    continue
                
                # Create lists to hold metric values for each strategy
                strategy_values = {}
                
                # For each classification timestamp, find the closest recovery metric
                for _, row in self.classification_data.iterrows():
                    strategy = row['selected_strategy']
                    timestamp = row['timestamp']
                    
                    # Find the closest metric by timestamp
                    closest_idx = (self.recovery_metrics['timestamp'] - timestamp).abs().idxmin()
                    closest_metric = self.recovery_metrics.loc[closest_idx]
                    
                    # Add to the appropriate strategy list
                    if strategy not in strategy_values:
                        strategy_values[strategy] = []
                    
                    strategy_values[strategy].append(closest_metric[metric])
                
                # Perform one-way ANOVA if we have at least two strategies with data
                valid_strategies = [s for s in strategy_values if len(strategy_values[s]) > 0]
                
                if len(valid_strategies) >= 2:
                    # Create lists for ANOVA
                    anova_data = [strategy_values[s] for s in valid_strategies]
                    
                    # Run ANOVA
                    f_val, p_val = stats.f_oneway(*anova_data)
                    
                    # Store results
                    anova_results[metric] = {
                        'F_value': float(f_val),
                        'p_value': float(p_val),
                        'significant': p_val < 0.05
                    }
            
            logger.info(f"ANOVA results: {anova_results}")
            
            # Save ANOVA results
            with open(os.path.join(self.output_dir, "anova_results.json"), 'w') as f:
                json.dump(anova_results, f, indent=2)
            
            return anova_results
        
        except Exception as e:
            logger.error(f"Error performing ANOVA analysis: {e}", exc_info=True)
            return None
    
    def create_box_plots(self):
        """Create box plots for recovery metrics by workload type and strategy."""
        logger.info("Creating box plots for recovery metrics")
        
        try:
            if self.recovery_metrics is None:
                logger.error("No recovery metrics available")
                return False
            
            # For each relevant metric
            for metric in ['cpu_usage', 'memory_usage']:
                if metric not in self.recovery_metrics.columns:
                    continue
                
                # Create box plot by workload type
                plt.figure(figsize=(10, 6))
                sns.boxplot(x='workload_type', y=metric, data=self.recovery_metrics)
                plt.title(f'{metric} During Recovery by Workload Type')
                plt.tight_layout()
                plt.savefig(os.path.join(self.output_dir, f"boxplot_{metric}_by_workload.png"), dpi=300)
                plt.close()
                
                # Merge classification data with recovery metrics
                # This is a simplified approach - in a real implementation you would
                # need to handle the time alignment more carefully
                
                # For each classification timestamp, find the closest recovery metric
                merged_data = []
                
                for _, row in self.classification_data.iterrows():
                    strategy = row['selected_strategy']
                    timestamp = row['timestamp']
                    
                    # Find the closest metric by timestamp
                    closest_idx = (self.recovery_metrics['timestamp'] - timestamp).abs().idxmin()
                    closest_metric = self.recovery_metrics.loc[closest_idx]
                    
                    merged_data.append({
                        'timestamp': timestamp,
                        'strategy': strategy,
                        metric: closest_metric[metric],
                        'workload_type': closest_metric['workload_type']
                    })
                
                # Create DataFrame from merged data
                merged_df = pd.DataFrame(merged_data)
                
                # Create box plot by strategy
                plt.figure(figsize=(10, 6))
                sns.boxplot(x='strategy', y=metric, data=merged_df)
                plt.title(f'{metric} During Recovery by Strategy')
                plt.tight_layout()
                plt.savefig(os.path.join(self.output_dir, f"boxplot_{metric}_by_strategy.png"), dpi=300)
                plt.close()
                
                # Create box plot by strategy and workload type
                plt.figure(figsize=(12, 6))
                sns.boxplot(x='strategy', y=metric, hue='workload_type', data=merged_df)
                plt.title(f'{metric} During Recovery by Strategy and Workload Type')
                plt.tight_layout()
                plt.savefig(os.path.join(self.output_dir, f"boxplot_{metric}_by_strategy_workload.png"), dpi=300)
                plt.close()
            
            logger.info("Box plots created")
            return True
        
        except Exception as e:
            logger.error(f"Error creating box plots: {e}", exc_info=True)
            return False
    
    def run_analysis_pipeline(self):
        """Run the complete recovery analysis pipeline."""
        logger.info("Starting recovery analysis pipeline")
        
        # Step 1: Load the data
        if not self.load_data():
            return False
        
        # Step 2: Identify recovery period
        if not self.identify_recovery_period():
            return False
        
        # Step 3: Calculate recovery time
        recovery_times = self.calculate_recovery_time()
        if recovery_times is None:
            return False
        
        # Step 4: Analyze resource usage
        resource_stats = self.analyze_resource_usage()
        if resource_stats is None:
            return False
        
        # Step 5: Perform ANOVA analysis
        anova_results = self.perform_anova_analysis()
        if anova_results is None:
            return False
        
        # Step 6: Create box plots
        if not self.create_box_plots():
            return False
        
        logger.info("Recovery analysis pipeline completed successfully")
        logger.info(f"Output files saved to {self.output_dir}")
        
        return True


def main():
    parser = argparse.ArgumentParser(description="Analyze Kafka Recovery Performance")
    parser.add_argument("--log-dir", default="experiment_results", 
                       help="Directory containing experiment log files")
    parser.add_argument("--output-dir", default="recovery_analysis", 
                       help="Directory to save analysis output")
    
    args = parser.parse_args()
    
    analyzer = RecoveryAnalyzer(
        log_dir=args.log_dir,
        output_dir=args.output_dir
    )
    
    success = analyzer.run_analysis_pipeline()
    
    if success:
        print(f"Analysis completed successfully. Results saved to {args.output_dir}")
    else:
        print("Analysis failed. Check the logs for details.")


if __name__ == "__main__":
    main()