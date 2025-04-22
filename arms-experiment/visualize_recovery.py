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
        logging.FileHandler("recovery_visualization.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("recovery_visualization")

class RecoveryVisualizer:
    def __init__(self, analysis_dir, output_dir="recovery_analysis"):
        """Initialize with analysis directory and output directory."""
        self.analysis_dir = analysis_dir
        self.output_dir = output_dir
        self.recovery_times = None
        self.resource_stats = None
        self.anova_results = None
        
        # Create output directory if it doesn't exist
        os.makedirs(self.output_dir, exist_ok=True)
    
    def load_analysis_results(self):
        """Load the recovery analysis results."""
        logger.info(f"Loading analysis results from {self.analysis_dir}")
        
        try:
            # Load recovery times
            recovery_times_path = os.path.join(self.analysis_dir, "recovery_times.json")
            if os.path.exists(recovery_times_path):
                with open(recovery_times_path, 'r') as f:
                    self.recovery_times = json.load(f)
                logger.info(f"Loaded recovery times")
            
            # Load resource stats
            resource_stats_path = os.path.join(self.analysis_dir, "resource_stats.json")
            if os.path.exists(resource_stats_path):
                with open(resource_stats_path, 'r') as f:
                    self.resource_stats = json.load(f)
                logger.info(f"Loaded resource statistics")
            
            # Load ANOVA results
            anova_results_path = os.path.join(self.analysis_dir, "anova_results.json")
            if os.path.exists(anova_results_path):
                with open(anova_results_path, 'r') as f:
                    self.anova_results = json.load(f)
                logger.info(f"Loaded ANOVA results")
            
            return self.recovery_times is not None and self.resource_stats is not None
        
        except Exception as e:
            logger.error(f"Error loading analysis results: {e}", exc_info=True)
            return False
    
    def create_recovery_time_comparison(self):
        """Create a bar chart comparing recovery times by workload type."""
        logger.info("Creating recovery time comparison chart")
        
        if self.recovery_times is None:
            logger.error("No recovery times available")
            return False
        
        try:
            # Create DataFrame from recovery times
            recovery_df = pd.DataFrame([
                {'workload_type': wt, 'recovery_time': time}
                for wt, time in self.recovery_times.items()
            ])
            
            # Create bar chart
            plt.figure(figsize=(10, 6))
            sns.barplot(x='workload_type', y='recovery_time', data=recovery_df)
            plt.title('Recovery Time by Workload Type')
            plt.ylabel('Recovery Time (seconds)')
            plt.xlabel('Workload Type')
            plt.grid(axis='y', linestyle='--', alpha=0.7)
            plt.tight_layout()
            plt.savefig(os.path.join(self.output_dir, "recovery_time_comparison.png"), dpi=300)
            plt.close()
            
            logger.info("Created recovery time comparison chart")
            return True
        
        except Exception as e:
            logger.error(f"Error creating recovery time comparison: {e}", exc_info=True)
            return False
    
    def create_resource_usage_comparison(self):
        """Create comparison charts for resource usage during recovery."""
        logger.info("Creating resource usage comparison charts")
        
        if self.resource_stats is None:
            logger.error("No resource statistics available")
            return False
        
        try:
            # Create DataFrames for CPU and memory usage
            cpu_data = []
            memory_data = []
            
            for workload_type, stats in self.resource_stats.items():
                cpu_data.append({
                    'workload_type': workload_type,
                    'metric': 'mean',
                    'value': stats['cpu']['mean']
                })
                cpu_data.append({
                    'workload_type': workload_type,
                    'metric': 'max',
                    'value': stats['cpu']['max']
                })
                
                memory_data.append({
                    'workload_type': workload_type,
                    'metric': 'mean',
                    'value': stats['memory']['mean']
                })
                memory_data.append({
                    'workload_type': workload_type,
                    'metric': 'max',
                    'value': stats['memory']['max']
                })
            
            cpu_df = pd.DataFrame(cpu_data)
            memory_df = pd.DataFrame(memory_data)
            
            # Create CPU usage comparison chart
            plt.figure(figsize=(12, 6))
            sns.barplot(x='workload_type', y='value', hue='metric', data=cpu_df)
            plt.title('CPU Usage During Recovery by Workload Type')
            plt.ylabel('CPU Usage')
            plt.xlabel('Workload Type')
            plt.grid(axis='y', linestyle='--', alpha=0.7)
            plt.tight_layout()
            plt.savefig(os.path.join(self.output_dir, "cpu_usage_comparison.png"), dpi=300)
            plt.close()
            
            # Create memory usage comparison chart
            plt.figure(figsize=(12, 6))
            sns.barplot(x='workload_type', y='value', hue='metric', data=memory_df)
            plt.title('Memory Usage During Recovery by Workload Type')
            plt.ylabel('Memory Usage')
            plt.xlabel('Workload Type')
            plt.grid(axis='y', linestyle='--', alpha=0.7)
            plt.tight_layout()
            plt.savefig(os.path.join(self.output_dir, "memory_usage_comparison.png"), dpi=300)
            plt.close()
            
            logger.info("Created resource usage comparison charts")
            return True
        
        except Exception as e:
            logger.error(f"Error creating resource usage comparison: {e}", exc_info=True)
            return False
    
    def create_anova_significance_chart(self):
        """Create chart showing ANOVA significance results."""
        logger.info("Creating ANOVA significance chart")
        
        if self.anova_results is None:
            logger.error("No ANOVA results available")
            return False
        
        try:
            # Create DataFrame from ANOVA results
            anova_data = []
            
            for metric, results in self.anova_results.items():
                anova_data.append({
                    'metric': metric,
                    'p_value': results['p_value'],
                    'significant': results['significant'],
                    'f_value': results['F_value']
                })
            
            anova_df = pd.DataFrame(anova_data)
            
            # Create -log10(p-value) chart
            plt.figure(figsize=(10, 6))
            bars = plt.bar(anova_df['metric'], -np.log10(anova_df['p_value']))
            
            # Color bars based on significance
            for i, significant in enumerate(anova_df['significant']):
                if significant:
                    bars[i].set_color('green')
                else:
                    bars[i].set_color('red')
            
            # Add significance threshold line
            plt.axhline(y=-np.log10(0.05), color='black', linestyle='--', label='p=0.05')
            
            plt.title('Statistical Significance of Recovery Metrics')
            plt.ylabel('-log10(p-value)')
            plt.xlabel('Metric')
            plt.legend()
            plt.grid(axis='y', linestyle='--', alpha=0.7)
            plt.tight_layout()
            plt.savefig(os.path.join(self.output_dir, "anova_significance.png"), dpi=300)
            plt.close()
            
            logger.info("Created ANOVA significance chart")
            return True
        
        except Exception as e:
            logger.error(f"Error creating ANOVA significance chart: {e}", exc_info=True)
            return False
    
    def create_combined_dashboard(self):
        """Create a combined dashboard with all visualizations."""
        logger.info("Creating combined recovery dashboard")
        
        try:
            # Create a figure with subplots
            fig, axs = plt.subplots(2, 2, figsize=(20, 16))
            
            # Recovery Time Comparison (top left)
            if self.recovery_times is not None:
                recovery_df = pd.DataFrame([
                    {'workload_type': wt, 'recovery_time': time}
                    for wt, time in self.recovery_times.items()
                ])
                
                sns.barplot(x='workload_type', y='recovery_time', data=recovery_df, ax=axs[0, 0])
                axs[0, 0].set_title('Recovery Time by Workload Type')
                axs[0, 0].set_ylabel('Recovery Time (seconds)')
                axs[0, 0].set_xlabel('Workload Type')
                axs[0, 0].grid(axis='y', linestyle='--', alpha=0.7)
            
            # CPU Usage Comparison (top right)
            if self.resource_stats is not None:
                cpu_data = []
                
                for workload_type, stats in self.resource_stats.items():
                    cpu_data.append({
                        'workload_type': workload_type,
                        'metric': 'mean',
                        'value': stats['cpu']['mean']
                    })
                    cpu_data.append({
                        'workload_type': workload_type,
                        'metric': 'max',
                        'value': stats['cpu']['max']
                    })
                
                cpu_df = pd.DataFrame(cpu_data)
                
                sns.barplot(x='workload_type', y='value', hue='metric', data=cpu_df, ax=axs[0, 1])
                axs[0, 1].set_title('CPU Usage During Recovery by Workload Type')
                axs[0, 1].set_ylabel('CPU Usage')
                axs[0, 1].set_xlabel('Workload Type')
                axs[0, 1].grid(axis='y', linestyle='--', alpha=0.7)
            
            # Memory Usage Comparison (bottom left)
            if self.resource_stats is not None:
                memory_data = []
                
                for workload_type, stats in self.resource_stats.items():
                    memory_data.append({
                        'workload_type': workload_type,
                        'metric': 'mean',
                        'value': stats['memory']['mean']
                    })
                    memory_data.append({
                        'workload_type': workload_type,
                        'metric': 'max',
                        'value': stats['memory']['max']
                    })
                
                memory_df = pd.DataFrame(memory_data)
                
                sns.barplot(x='workload_type', y='value', hue='metric', data=memory_df, ax=axs[1, 0])
                axs[1, 0].set_title('Memory Usage During Recovery by Workload Type')
                axs[1, 0].set_ylabel('Memory Usage')
                axs[1, 0].set_xlabel('Workload Type')
                axs[1, 0].grid(axis='y', linestyle='--', alpha=0.7)
            
            # ANOVA Significance (bottom right)
            if self.anova_results is not None:
                anova_data = []
                
                for metric, results in self.anova_results.items():
                    anova_data.append({
                        'metric': metric,
                        'p_value': results['p_value'],
                        'significant': results['significant'],
                        'f_value': results['F_value']
                    })
                
                anova_df = pd.DataFrame(anova_data)
                
                bars = axs[1, 1].bar(anova_df['metric'], -np.log10(anova_df['p_value']))
                
                # Color bars based on significance
                for i, significant in enumerate(anova_df['significant']):
                    if significant:
                        bars[i].set_color('green')
                    else:
                        bars[i].set_color('red')
                
                # Add significance threshold line
                axs[1, 1].axhline(y=-np.log10(0.05), color='black', linestyle='--', label='p=0.05')
                
                axs[1, 1].set_title('Statistical Significance of Recovery Metrics')
                axs[1, 1].set_ylabel('-log10(p-value)')
                axs[1, 1].set_xlabel('Metric')
                axs[1, 1].legend()
                axs[1, 1].grid(axis='y', linestyle='--', alpha=0.7)
            
            plt.suptitle('Kafka Recovery Performance Dashboard', fontsize=20)
            plt.tight_layout()
            plt.subplots_adjust(top=0.95)
            plt.savefig(os.path.join(self.output_dir, "recovery_dashboard.png"), dpi=300)
            plt.close()
            
            logger.info("Created combined recovery dashboard")
            return True
        
        except Exception as e:
            logger.error(f"Error creating combined dashboard: {e}", exc_info=True)
            return False
    
    def run_visualization_pipeline(self):
        """Run the complete recovery visualization pipeline."""
        logger.info("Starting recovery visualization pipeline")
        
        # Step 1: Load the analysis results
        if not self.load_analysis_results():
            return False
        
        # Step 2: Create recovery time comparison
        if not self.create_recovery_time_comparison():
            return False
        
        # Step 3: Create resource usage comparison
        if not self.create_resource_usage_comparison():
            return False
        
        # Step 4: Create ANOVA significance chart
        if not self.create_anova_significance_chart():
            return False
        
        # Step 5: Create combined dashboard
        if not self.create_combined_dashboard():
            return False
        
        logger.info("Recovery visualization pipeline completed successfully")
        logger.info(f"Output files saved to {self.output_dir}")
        
        return True


def main():
    parser = argparse.ArgumentParser(description="Visualize Kafka Recovery Performance")
    parser.add_argument("--analysis-dir", default="recovery_analysis", 
                       help="Directory containing recovery analysis results")
    parser.add_argument("--output-dir", default="recovery_analysis", 
                       help="Directory to save visualization output")
    
    args = parser.parse_args()
    
    visualizer = RecoveryVisualizer(
        analysis_dir=args.analysis_dir,
        output_dir=args.output_dir
    )
    
    success = visualizer.run_visualization_pipeline()
    
    if success:
        print(f"Visualization completed successfully. Results saved to {args.output_dir}")
    else:
        print("Visualization failed. Check the logs for details.")


if __name__ == "__main__":
    main()