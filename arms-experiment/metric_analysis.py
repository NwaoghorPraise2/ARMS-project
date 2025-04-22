#!/usr/bin/env python3

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
from sklearn.feature_selection import mutual_info_classif
import argparse
import os
import logging
import json

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("metric_analysis.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("metric_analysis")

class MetricAnalyzer:
    def __init__(self, metrics_file, output_dir="analysis_output"):
        """Initialize with the metrics CSV file and output directory."""
        self.metrics_file = metrics_file
        self.output_dir = output_dir
        self.data = None
        self.selected_metrics = []
        
        # Create output directory if it doesn't exist
        os.makedirs(self.output_dir, exist_ok=True)
    
    def load_data(self):
        """Load the metrics data from CSV."""
        logger.info(f"Loading metrics data from {self.metrics_file}")
        
        try:
            self.data = pd.read_csv(self.metrics_file)
            
            # Convert timestamp to datetime
            self.data['timestamp'] = pd.to_datetime(self.data['timestamp'])
            
            # Convert workload_type to binary target (0 for real_time, 1 for batch)
            self.data['workload_binary'] = self.data['workload_type'].apply(
                lambda x: 1 if x == 'batch' else 0
            )
            
            logger.info(f"Loaded {len(self.data)} rows of data")
            logger.info(f"Metrics available: {list(self.data.columns)}")
            
            return True
        
        except Exception as e:
            logger.error(f"Error loading data: {e}", exc_info=True)
            return False
    
    def preprocess_data(self):
        """Preprocess the data for analysis."""
        logger.info("Preprocessing data")
        
        if self.data is None:
            logger.error("No data loaded to preprocess")
            return False
        
        try:
            # Remove any rows with missing values
            self.data = self.data.dropna()
            
            # Remove any duplicate rows
            self.data = self.data.drop_duplicates()
            
            # Convert timestamp to numerical features that might be useful
            self.data['hour_of_day'] = self.data['timestamp'].dt.hour
            
            # Remove non-metric columns for correlation analysis
            self.numerical_data = self.data.drop(
                columns=['timestamp', 'workload_type']
            )
            
            logger.info("Data preprocessing complete")
            logger.info(f"Processed data shape: {self.numerical_data.shape}")
            
            return True
        
        except Exception as e:
            logger.error(f"Error preprocessing data: {e}", exc_info=True)
            return False
    
    def perform_correlation_analysis(self):
        """Perform correlation analysis between metrics and workload type."""
        logger.info("Performing correlation analysis")
        
        if self.numerical_data is None:
            logger.error("No preprocessed data available")
            return None
        
        try:
            # Calculate Spearman rank correlation (better for non-linear relationships)
            correlation_matrix = self.numerical_data.corr(method='spearman')
            
            # Get correlations with workload_binary
            workload_correlations = correlation_matrix['workload_binary'].drop('workload_binary')
            
            # Sort by absolute correlation values
            sorted_correlations = workload_correlations.abs().sort_values(ascending=False)
            
            logger.info("Top correlations with workload type:")
            for metric, corr in sorted_correlations.items():
                direction = "+" if workload_correlations[metric] > 0 else "-"
                logger.info(f"{metric}: {direction}{corr:.4f}")
            
            # Save correlation matrix to CSV
            correlation_matrix.to_csv(f"{self.output_dir}/correlation_matrix.csv")
            
            # Create correlation heatmap
            plt.figure(figsize=(12, 10))
            sns.heatmap(correlation_matrix, annot=True, cmap='coolwarm', fmt='.2f')
            plt.title('Correlation Matrix of Metrics')
            plt.tight_layout()
            plt.savefig(f"{self.output_dir}/correlation_heatmap.png", dpi=300)
            plt.close()
            
            # Create sorted correlation bar chart
            plt.figure(figsize=(10, 8))
            workload_correlations.abs().sort_values().plot(kind='barh')
            plt.title('Absolute Correlation with Workload Type')
            plt.xlabel('Spearman Correlation Coefficient')
            plt.tight_layout()
            plt.savefig(f"{self.output_dir}/correlation_bars.png", dpi=300)
            plt.close()
            
            return workload_correlations
        
        except Exception as e:
            logger.error(f"Error in correlation analysis: {e}", exc_info=True)
            return None
    
    def calculate_mutual_information(self):
        """Calculate mutual information between metrics and workload type."""
        logger.info("Calculating mutual information")
        
        if self.numerical_data is None:
            logger.error("No preprocessed data available")
            return None
        
        try:
            # Prepare data for mutual information calculation
            X = self.numerical_data.drop(columns=['workload_binary'])
            y = self.numerical_data['workload_binary']
            
            # Calculate mutual information
            mi_scores = mutual_info_classif(X, y, random_state=42)
            
            # Create DataFrame with metric names and MI scores
            mi_df = pd.DataFrame({
                'metric': X.columns,
                'mutual_info': mi_scores
            })
            
            # Sort by MI scores
            mi_df = mi_df.sort_values('mutual_info', ascending=False)
            
            logger.info("Top mutual information scores:")
            for _, row in mi_df.iterrows():
                logger.info(f"{row['metric']}: {row['mutual_info']:.4f}")
            
            # Save MI scores to CSV
            mi_df.to_csv(f"{self.output_dir}/mutual_info_scores.csv", index=False)
            
            # Create MI bar chart
            plt.figure(figsize=(10, 8))
            plt.barh(mi_df['metric'], mi_df['mutual_info'])
            plt.title('Mutual Information with Workload Type')
            plt.xlabel('Mutual Information')
            plt.tight_layout()
            plt.savefig(f"{self.output_dir}/mutual_info_bars.png", dpi=300)
            plt.close()
            
            return mi_df
        
        except Exception as e:
            logger.error(f"Error calculating mutual information: {e}", exc_info=True)
            return None
    
    def select_metrics(self, correlation_results, mi_results, threshold=1.2):
        """Select the most relevant metrics based on combined correlation and MI scores."""
        logger.info(f"Selecting metrics with combined score threshold of {threshold}")
        
        if correlation_results is None or mi_results is None:
            logger.error("Missing correlation or mutual information results")
            return False
        
        try:
            # Normalize MI scores to 0-1 range
            mi_results['normalized_mi'] = mi_results['mutual_info'] / mi_results['mutual_info'].max()
            
            # Create a lookup dictionary for MI scores
            mi_lookup = mi_results.set_index('metric')['normalized_mi'].to_dict()
            
            # Calculate combined score (abs(correlation) + normalized_mi)
            metric_scores = []
            for metric in correlation_results.index:
                if metric in mi_lookup:
                    abs_corr = abs(correlation_results[metric])
                    norm_mi = mi_lookup[metric]
                    combined_score = abs_corr + norm_mi
                    
                    metric_scores.append({
                        'metric': metric,
                        'abs_correlation': abs_corr,
                        'normalized_mi': norm_mi,
                        'combined_score': combined_score
                    })
            
            # Convert to DataFrame and sort by combined score
            score_df = pd.DataFrame(metric_scores)
            score_df = score_df.sort_values('combined_score', ascending=False)
            
            # Apply threshold to select metrics
            selected_metrics = score_df[score_df['combined_score'] > threshold]
            
            logger.info(f"Selected {len(selected_metrics)} metrics:")
            for _, row in selected_metrics.iterrows():
                logger.info(f"{row['metric']}: combined_score={row['combined_score']:.4f} "
                          f"(corr={row['abs_correlation']:.4f}, mi={row['normalized_mi']:.4f})")
            
            # Save selected metrics to CSV
            score_df.to_csv(f"{self.output_dir}/metric_scores.csv", index=False)
            selected_metrics.to_csv(f"{self.output_dir}/selected_metrics.csv", index=False)
            
            # Create combined score bar chart
            plt.figure(figsize=(10, 8))
            plt.barh(score_df['metric'], score_df['combined_score'])
            plt.axvline(x=threshold, color='red', linestyle='--', label=f'Threshold ({threshold})')
            plt.title('Combined Metric Scores (abs(correlation) + normalized_mi)')
            plt.xlabel('Combined Score')
            plt.legend()
            plt.tight_layout()
            plt.savefig(f"{self.output_dir}/combined_scores.png", dpi=300)
            plt.close()
            
            # Store selected metrics
            self.selected_metrics = selected_metrics['metric'].tolist()
            
            # Save selected metrics to JSON
            with open(f"{self.output_dir}/selected_metrics.json", 'w') as f:
                json.dump(self.selected_metrics, f, indent=2)
            
            return True
        
        except Exception as e:
            logger.error(f"Error selecting metrics: {e}", exc_info=True)
            return False
    
    def create_distribution_plots(self):
        """Create distribution plots for selected metrics by workload type."""
        logger.info("Creating distribution plots for selected metrics")
        
        if self.data is None or not self.selected_metrics:
            logger.error("No data or selected metrics available")
            return False
        
        try:
            # Create a figure for each selected metric
            for metric in self.selected_metrics:
                plt.figure(figsize=(10, 6))
                
                # Create boxplot for the metric by workload type
                sns.boxplot(x='workload_type', y=metric, data=self.data)
                plt.title(f'Distribution of {metric} by Workload Type')
                plt.tight_layout()
                plt.savefig(f"{self.output_dir}/boxplot_{metric}.png", dpi=300)
                plt.close()
                
                # Create KDE plot for the metric by workload type
                plt.figure(figsize=(10, 6))
                for workload in self.data['workload_type'].unique():
                    subset = self.data[self.data['workload_type'] == workload]
                    sns.kdeplot(subset[metric], label=workload)
                
                plt.title(f'Density Distribution of {metric} by Workload Type')
                plt.xlabel(metric)
                plt.ylabel('Density')
                plt.legend()
                plt.tight_layout()
                plt.savefig(f"{self.output_dir}/kde_{metric}.png", dpi=300)
                plt.close()
            
            logger.info(f"Created distribution plots for {len(self.selected_metrics)} metrics")
            return True
        
        except Exception as e:
            logger.error(f"Error creating distribution plots: {e}", exc_info=True)
            return False
    
    def create_time_series_plots(self):
        """Create time series plots for selected metrics."""
        logger.info("Creating time series plots for selected metrics")
        
        if self.data is None or not self.selected_metrics:
            logger.error("No data or selected metrics available")
            return False
        
        try:
            # Create a time series plot for each selected metric
            for metric in self.selected_metrics:
                plt.figure(figsize=(12, 6))
                
                # Group by timestamp and workload type, calculating mean
                grouped = self.data.groupby(['timestamp', 'workload_type'])[metric].mean().unstack()
                
                # Plot time series for each workload type
                for workload in grouped.columns:
                    plt.plot(grouped.index, grouped[workload], label=workload)
                
                plt.title(f'Time Series of {metric} by Workload Type')
                plt.xlabel('Time')
                plt.ylabel(metric)
                plt.legend()
                plt.grid(True)
                plt.tight_layout()
                plt.savefig(f"{self.output_dir}/timeseries_{metric}.png", dpi=300)
                plt.close()
            
            logger.info(f"Created time series plots for {len(self.selected_metrics)} metrics")
            return True
        
        except Exception as e:
            logger.error(f"Error creating time series plots: {e}", exc_info=True)
            return False
    
    def generate_training_dataset(self):
        """Generate a training dataset using only the selected metrics."""
        logger.info("Generating training dataset with selected metrics")
        
        if self.data is None or not self.selected_metrics:
            logger.error("No data or selected metrics available")
            return False
        
        try:
            # Include workload_type and selected metrics
            columns_to_keep = ['workload_type'] + self.selected_metrics
            training_data = self.data[columns_to_keep].copy()
            
            # Save the training dataset to CSV
            training_data.to_csv(f"{self.output_dir}/training_dataset.csv", index=False)
            
            logger.info(f"Created training dataset with {len(training_data)} samples and {len(self.selected_metrics)} features")
            logger.info(f"Class distribution: {training_data['workload_type'].value_counts().to_dict()}")
            
            return True
        
        except Exception as e:
            logger.error(f"Error generating training dataset: {e}", exc_info=True)
            return False
    
    def perform_anova(self):
        """Perform ANOVA test for each metric to check statistical significance."""
        logger.info("Performing ANOVA tests for statistical significance")
        
        if self.data is None:
            logger.error("No data available")
            return False
        
        try:
            # Create a dictionary to store ANOVA results
            anova_results = {}
            
            # Exclude non-numeric columns
            numeric_columns = self.data.select_dtypes(include=['number']).columns
            
            # Test each numeric column (excluding workload_binary)
            for column in numeric_columns:
                if column != 'workload_binary':
                    # Get data for each workload type
                    real_time_data = self.data[self.data['workload_type'] == 'real_time'][column]
                    batch_data = self.data[self.data['workload_type'] == 'batch'][column]
                    
                    # Perform one-way ANOVA
                    f_val, p_val = stats.f_oneway(real_time_data, batch_data)
                    
                    # Store results
                    anova_results[column] = {
                        'F_value': f_val,
                        'p_value': p_val,
                        'significant': p_val < 0.05
                    }
            
            # Convert results to DataFrame
            anova_df = pd.DataFrame.from_dict(anova_results, orient='index')
            
            # Sort by p-value
            anova_df = anova_df.sort_values('p_value')
            
            logger.info("ANOVA test results:")
            for metric, row in anova_df.iterrows():
                sig_flag = "✓" if row['significant'] else "✗"
                logger.info(f"{metric}: F={row['F_value']:.4f}, p={row['p_value']:.6f}, significant={sig_flag}")
            
            # Save ANOVA results to CSV
            anova_df.to_csv(f"{self.output_dir}/anova_results.csv")
            
            # Create bar chart of p-values
            plt.figure(figsize=(10, 8))
            plt.barh(anova_df.index, -np.log10(anova_df['p_value']))
            plt.axvline(x=-np.log10(0.05), color='red', linestyle='--', label='p=0.05')
            plt.title('Statistical Significance: -log10(p-value)')
            plt.xlabel('-log10(p-value)')
            plt.legend()
            plt.tight_layout()
            plt.savefig(f"{self.output_dir}/anova_significance.png", dpi=300)
            plt.close()
            
            return anova_df
        
        except Exception as e:
            logger.error(f"Error performing ANOVA tests: {e}", exc_info=True)
            return None
    
    def run_analysis_pipeline(self):
        """Run the complete metric analysis pipeline."""
        logger.info("Starting metric analysis pipeline")
        
        # Step 1: Load the metrics data
        if not self.load_data():
            return False
        
        # Step 2: Preprocess the data
        if not self.preprocess_data():
            return False
        
        # Step 3: Perform correlation analysis
        correlation_results = self.perform_correlation_analysis()
        if correlation_results is None:
            return False
        
        # Step 4: Calculate mutual information
        mi_results = self.calculate_mutual_information()
        if mi_results is None:
            return False
        
        # Step 5: Perform ANOVA tests
        anova_results = self.perform_anova()
        if anova_results is None:
            return False
        
        # Step 6: Select metrics
        if not self.select_metrics(correlation_results, mi_results):
            return False
        
        # Step 7: Create distribution plots
        if not self.create_distribution_plots():
            return False
        
        # Step 8: Create time series plots
        if not self.create_time_series_plots():
            return False
        
        # Step 9: Generate training dataset
        if not self.generate_training_dataset():
            return False
        
        logger.info("Metric analysis pipeline completed successfully")
        logger.info(f"Selected metrics: {self.selected_metrics}")
        logger.info(f"Output files saved to {self.output_dir}")
        
        return True


def main():
    parser = argparse.ArgumentParser(description="Kafka Metrics Analysis")
    parser.add_argument("--metrics-file", default="workload_metrics.csv", 
                        help="CSV file containing collected metrics")
    parser.add_argument("--output-dir", default="analysis_output", 
                        help="Directory to save analysis output")
    parser.add_argument("--threshold", type=float, default=1.2, 
                        help="Threshold for combined score in metric selection")
    
    args = parser.parse_args()
    
    analyzer = MetricAnalyzer(
        metrics_file=args.metrics_file,
        output_dir=args.output_dir
    )
    
    success = analyzer.run_analysis_pipeline()
    
    if success:
        print(f"Analysis completed successfully. Results saved to {args.output_dir}")
    else:
        print("Analysis failed. Check the logs for details.")


if __name__ == "__main__":
    main()