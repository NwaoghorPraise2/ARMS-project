import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import statsmodels.api as sm
from statsmodels.formula.api import ols
from statsmodels.stats.multicomp import pairwise_tukeyhsd
import scipy.stats as stats

# Set the style for plots
plt.style.use('ggplot')
sns.set(font_scale=1.2)
sns.set_style("whitegrid")

# Function to load the data
def load_data(file_path):
    """Load the CSV data and prepare it for analysis"""
    df = pd.read_csv(file_path)
    
    # Rename for clarity in research question
    df['configuration'] = df['config_source'].replace({
        'default': 'baseline',
        'buffer': 'ARMS'
    })
    
    # Convert CPU usage to percentage (multiply by 100)
    df['cpu_usage_percent'] = df['cpu_usage_percent'] * 100
    
    # Add a combined strategy/workload column for easier analysis
    df['workload_strategy'] = df['workload_type'].apply(
        lambda x: 'batch' if x == 'BATCH_DATA_INTENSIVE' else 'real-time'
    )
    
    return df

# Function to perform ANOVA analysis
def run_anova_analysis(df):
    """Run two-way ANOVA for recovery time, CPU usage, and memory usage"""
    results = {}
    
    # Variables to analyze
    variables = [
        ('recovery_time_seconds', 'Recovery Time (seconds)'),
        ('cpu_usage_percent', 'CPU Usage (%)'),
        ('memory_usage_percent', 'Memory Usage (%)')
    ]
    
    for var, label in variables:
        # Formula: dependent ~ factor1 + factor2 + factor1:factor2 (interaction)
        formula = f"{var} ~ C(configuration) + C(workload_strategy) + C(configuration):C(workload_strategy)"
        model = ols(formula, data=df).fit()
        anova_table = sm.stats.anova_lm(model, typ=2)
        
        # Store results
        results[var] = {
            'anova': anova_table,
            'label': label,
            'model': model
        }
        
        # Print ANOVA results
        print(f"\n--- ANOVA Results for {label} ---")
        print(anova_table)
        
        # Post-hoc Tukey test for all pairwise comparisons
        # Create a combined group variable
        df['group'] = df['configuration'] + '_' + df['workload_strategy']
        tukey = pairwise_tukeyhsd(df[var], df['group'], alpha=0.05)
        print("\n--- Tukey HSD Post-hoc Test ---")
        print(tukey)
    
    return results

# Function to create individual box plots
def create_separate_boxplots(df, results):
    """Create separate box plots for each variable by configuration and workload"""
    
    # Variables to analyze
    variables = [
        ('recovery_time_seconds', 'Recovery Time (seconds)'),
        ('cpu_usage_percent', 'CPU Usage (%)'),
        ('memory_usage_percent', 'Memory Usage (%)')
    ]
    
    for var, label in variables:
        # Create a new figure for each plot
        plt.figure(figsize=(10, 6))
        
        # Create the box plot
        ax = sns.boxplot(
            x='configuration', 
            y=var, 
            hue='workload_strategy',
            data=df, 
            palette=['blue', 'red']
        )
        
        # Add individual data points for better visualization
        sns.stripplot(
            x='configuration', 
            y=var,
            hue='workload_strategy',
            data=df,
            palette=['darkblue', 'darkred'],
            alpha=0.3,
            dodge=True,
            size=4,
            jitter=True
        )
        
        # Set labels and title
        plt.title(f'Impact of ARMS Framework on {label}', fontsize=14)
        plt.xlabel('Configuration', fontsize=12)
        plt.ylabel(label, fontsize=12)
        
        # Add significance indicators if p < 0.05
        anova_result = results[var]['anova']
        p_value = anova_result.loc['C(configuration)', 'PR(>F)']
        
        if p_value < 0.05:
            # Add asterisk to indicate significance
            max_val = df[var].max() * 1.05
            plt.text(0.5, max_val, '* p < 0.05', ha='center')
        
        # Legend adjustment
        handles, labels = ax.get_legend_handles_labels()
        plt.legend(handles[:2], labels[:2], title='Workload Type', loc='best')
        
        # Adjust layout
        plt.tight_layout()
        
        # Save the figure
        filename = f'kafka_{var}_analysis.png'
        plt.savefig(filename, dpi=300, bbox_inches='tight')
        print(f"Saved {filename}")
        plt.close()

# Function to print summary statistics
def print_summary_stats(df):
    """Print summary statistics for each group"""
    print("\n--- Summary Statistics ---")
    
    # Group by configuration and workload strategy
    grouped = df.groupby(['configuration', 'workload_strategy'])
    
    # Calculate statistics for each metric
    summary = grouped.agg({
        'recovery_time_seconds': ['mean', 'std', 'min', 'max'],
        'cpu_usage_percent': ['mean', 'std', 'min', 'max'],
        'memory_usage_percent': ['mean', 'std', 'min', 'max']
    })
    
    print(summary)
    
    # Calculate percent differences between baseline and ARMS
    for workload in ['batch', 'real-time']:
        print(f"\n--- Percent Difference (ARMS vs baseline) for {workload} ---")
        
        for metric in ['recovery_time_seconds', 'cpu_usage_percent', 'memory_usage_percent']:
            baseline = summary.loc[('baseline', workload), (metric, 'mean')]
            arms = summary.loc[('ARMS', workload), (metric, 'mean')]
            
            pct_diff = ((arms - baseline) / baseline) * 100
            print(f"{metric}: {pct_diff:.2f}%")
    
    return summary

# Function to create additional comparative visualizations
def create_comparative_visualizations(df):
    """Create additional visualizations to compare baseline vs ARMS"""
    
    # 1. Bar chart of means with error bars
    metrics = [
        ('recovery_time_seconds', 'Recovery Time (seconds)'),
        ('cpu_usage_percent', 'CPU Usage (%)'),
        ('memory_usage_percent', 'Memory Usage (%)')
    ]
    
    for var, label in metrics:
        plt.figure(figsize=(8, 6))
        
        # Calculate means and standard errors
        stats_df = df.groupby(['configuration', 'workload_strategy'])[var].agg(['mean', 'sem']).reset_index()
        
        # Create the bar plot
        ax = sns.barplot(
            x='configuration', 
            y='mean',
            hue='workload_strategy',
            data=stats_df,
            palette=['blue', 'red'],
            alpha=0.7,
            errorbar=('ci', 95)
        )
        
        # Set labels and title
        plt.title(f'Mean {label} Comparison', fontsize=14)
        plt.xlabel('Configuration', fontsize=12)
        plt.ylabel(f'Mean {label}', fontsize=12)
        
        # Add value labels on bars
        for i, p in enumerate(ax.patches):
            height = p.get_height()
            ax.text(p.get_x() + p.get_width()/2.,
                    height + 0.1,
                    f'{height:.2f}',
                    ha="center", fontsize=10)
        
        plt.tight_layout()
        filename = f'kafka_{var}_mean_comparison.png'
        plt.savefig(filename, dpi=300, bbox_inches='tight')
        print(f"Saved {filename}")
        plt.close()

# Main function
def main():
    """Main function to run the analysis"""
    # Load data
    file_path = 'arms-experiment/data/recovery_data_with_header.csv'  # Update with your file path
    try:
        df = load_data(file_path)
    except FileNotFoundError:
        print(f"File not found: {file_path}")
        print("Please ensure the CSV file is in the correct location")
        return
    
    # Print data overview
    print("Data Overview:")
    print(df.head())
    print(f"\nDataset shape: {df.shape}")
    
    # Run ANOVA analysis
    results = run_anova_analysis(df)
    
    # Print summary statistics
    summary = print_summary_stats(df)
    
    # Create separate box plots
    create_separate_boxplots(df, results)
    
    # Create additional comparative visualizations
    create_comparative_visualizations(df)
    
    print("\nAnalysis complete! All visualizations have been saved.")

if __name__ == "__main__":
    main()