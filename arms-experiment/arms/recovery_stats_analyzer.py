#!/usr/bin/env python3

import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import argparse
from datetime import datetime

def analyze_recovery_stats(csv_path, output_dir="./reports"):
    """
    Analyze Kafka recovery statistics from CSV file and generate visualizations
    
    Args:
        csv_path: Path to recovery stats CSV file
        output_dir: Directory to save analysis reports and visualizations
    """
    # Check if file exists
    if not os.path.exists(csv_path):
        print(f"Error: File {csv_path} does not exist")
        return
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Read CSV into pandas DataFrame
    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        print(f"Error reading CSV file: {e}")
        return
    
    if len(df) == 0:
        print("No recovery data found in CSV file")
        return
    
    # Convert timestamp to datetime
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Generate timestamp for this report
    report_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Set the style for plots
    sns.set(style="darkgrid")
    
    # Print basic statistics
    print("\n===== Recovery Statistics Summary =====")
    print(f"Total recoveries recorded: {len(df)}")
    print(f"Time period: {df['timestamp'].min()} to {df['timestamp'].max()}")
    print(f"Successful recoveries: {df[df['result'] == 'success'].shape[0]} ({df[df['result'] == 'success'].shape[0]/len(df)*100:.1f}%)")
    
    # Average recovery time by strategy
    print("\n--- Average Recovery Time by Strategy ---")
    strategy_stats = df.groupby('strategy')['recovery_time_seconds'].agg(['count', 'mean', 'min', 'max', 'std']).round(2)
    print(strategy_stats)
    
    # Average resource usage by strategy
    print("\n--- Average Resource Usage by Strategy ---")
    resource_stats = df.groupby('strategy')[['cpu_usage_percent', 'memory_usage_percent']].mean().round(2)
    print(resource_stats)
    
    # Average recovery time by workload type
    print("\n--- Average Recovery Time by Workload Type ---")
    workload_stats = df.groupby('workload_type')['recovery_time_seconds'].agg(['count', 'mean', 'min', 'max', 'std']).round(2)
    print(workload_stats)
    
    # Success rate by strategy
    print("\n--- Success Rate by Strategy ---")
    success_stats = df.groupby('strategy')['result'].apply(lambda x: (x == 'success').mean() * 100).round(2)
    print(success_stats)
    
    # Create visualizations
    try:
        # 1. Recovery time by strategy
        plt.figure(figsize=(12, 8))
        ax = sns.boxplot(x='strategy', y='recovery_time_seconds', hue='result', data=df, palette='Set2')
        plt.title('Recovery Time by Strategy and Result', fontsize=14)
        plt.xlabel('Strategy', fontsize=12)
        plt.ylabel('Recovery Time (seconds)', fontsize=12)
        plt.tight_layout()
        plt.savefig(f"{output_dir}/recovery_time_by_strategy_{report_time}.png")
        
        # 2. Recovery time by workload type
        plt.figure(figsize=(12, 8))
        ax = sns.boxplot(x='workload_type', y='recovery_time_seconds', hue='result', data=df, palette='Set3')
        plt.title('Recovery Time by Workload Type and Result', fontsize=14)
        plt.xlabel('Workload Type', fontsize=12)
        plt.ylabel('Recovery Time (seconds)', fontsize=12)
        plt.tight_layout()
        plt.savefig(f"{output_dir}/recovery_time_by_workload_{report_time}.png")
        
        # 3. Resource usage by strategy
        plt.figure(figsize=(14, 8))
        resource_data = df.melt(id_vars=['strategy'], 
                               value_vars=['cpu_usage_percent', 'memory_usage_percent'],
                               var_name='Resource', value_name='Usage (%)')
        ax = sns.barplot(x='strategy', y='Usage (%)', hue='Resource', data=resource_data, palette='Blues')
        plt.title('Resource Usage by Strategy', fontsize=14)
        plt.xlabel('Strategy', fontsize=12)
        plt.ylabel('Usage (%)', fontsize=12)
        plt.tight_layout()
        plt.savefig(f"{output_dir}/resource_usage_by_strategy_{report_time}.png")
        
        # 4. Success rate by strategy
        plt.figure(figsize=(12, 8))
        success_data = df.groupby('strategy')['result'].apply(lambda x: (x == 'success').mean() * 100).reset_index()
        success_data.columns = ['Strategy', 'Success Rate (%)']
        ax = sns.barplot(x='Strategy', y='Success Rate (%)', data=success_data, palette='RdYlGn')
        plt.title('Success Rate by Strategy', fontsize=14)
        plt.xlabel('Strategy', fontsize=12)
        plt.ylabel('Success Rate (%)', fontsize=12)
        ax.set_ylim(0, 100)
        for p in ax.patches:
            ax.annotate(f"{p.get_height():.1f}%", 
                      (p.get_x() + p.get_width() / 2., p.get_height()), 
                      ha = 'center', va = 'bottom', fontsize=12)
        plt.tight_layout()
        plt.savefig(f"{output_dir}/success_rate_by_strategy_{report_time}.png")
        
        # 5. Partition health improvement
        plt.figure(figsize=(14, 10))
        
        # Calculate differences in partition health
        df['under_replicated_change'] = df['under_replicated_after'] - df['under_replicated_before']
        df['offline_change'] = df['offline_after'] - df['offline_before']
        
        # Create a figure with two subplots
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 12))
        
        # First subplot: Under-replicated partitions
        sns.boxplot(x='strategy', y='under_replicated_change', hue='result', data=df, palette='Set1', ax=ax1)
        ax1.set_title('Change in Under-Replicated Partitions by Strategy', fontsize=14)
        ax1.set_xlabel('Strategy', fontsize=12)
        ax1.set_ylabel('Change (negative is better)', fontsize=12)
        ax1.axhline(y=0, color='gray', linestyle='--')
        
        # Second subplot: Offline partitions
        sns.boxplot(x='strategy', y='offline_change', hue='result', data=df, palette='Set1', ax=ax2)
        ax2.set_title('Change in Offline Partitions by Strategy', fontsize=14)
        ax2.set_xlabel('Strategy', fontsize=12)
        ax2.set_ylabel('Change (negative is better)', fontsize=12)
        ax2.axhline(y=0, color='gray', linestyle='--')
        
        plt.tight_layout()
        plt.savefig(f"{output_dir}/partition_health_improvement_{report_time}.png")
        
        # 6. Recovery time trend over time
        plt.figure(figsize=(14, 8))
        ax = sns.scatterplot(x='timestamp', y='recovery_time_seconds', hue='strategy', style='result', s=100, data=df)
        plt.title('Recovery Time Trend Over Time', fontsize=14)
        plt.xlabel('Time', fontsize=12)
        plt.ylabel('Recovery Time (seconds)', fontsize=12)
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(f"{output_dir}/recovery_time_trend_{report_time}.png")
        
        # 7. Correlation heatmap
        plt.figure(figsize=(12, 10))
        numeric_cols = ['recovery_time_seconds', 'cpu_usage_percent', 'memory_usage_percent', 
                       'under_replicated_before', 'under_replicated_after', 
                       'offline_before', 'offline_after']
        corr = df[numeric_cols].corr()
        mask = np.triu(np.ones_like(corr, dtype=bool))
        sns.heatmap(corr, mask=mask, annot=True, fmt=".2f", cmap="coolwarm", square=True, linewidths=.5)
        plt.title('Correlation Between Recovery Metrics', fontsize=14)
        plt.tight_layout()
        plt.savefig(f"{output_dir}/correlation_heatmap_{report_time}.png")
        
        # 8. Generate HTML report
        html_report = f"""
        <html>
        <head>
            <title>Kafka Recovery Analysis Report - {report_time}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                h1, h2, h3 {{ color: #333366; }}
                table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
                tr:nth-child(even) {{ background-color: #f9f9f9; }}
                img {{ max-width: 100%; height: auto; margin: 20px 0; }}
                .summary {{ background-color: #f8f8f8; padding: 15px; border-radius: 5px; }}
            </style>
        </head>
        <body>
            <h1>Kafka Recovery Analysis Report</h1>
            <p>Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
            
            <div class="summary">
                <h2>Summary</h2>
                <p>Total recoveries recorded: {len(df)}</p>
                <p>Time period: {df['timestamp'].min()} to {df['timestamp'].max()}</p>
                <p>Successful recoveries: {df[df['result'] == 'success'].shape[0]} ({df[df['result'] == 'success'].shape[0]/len(df)*100:.1f}%)</p>
            </div>
            
            <h2>Recovery Time Statistics by Strategy</h2>
            <table>
                <tr>
                    <th>Strategy</th>
                    <th>Count</th>
                    <th>Mean (s)</th>
                    <th>Min (s)</th>
                    <th>Max (s)</th>
                    <th>Std Dev</th>
                </tr>
                {strategy_stats.reset_index().to_html(index=False, header=False, columns=['strategy', 'count', 'mean', 'min', 'max', 'std'], 
                                                     formatters={'mean': '{:.2f}'.format, 'min': '{:.2f}'.format, 
                                                               'max': '{:.2f}'.format, 'std': '{:.2f}'.format})}
            </table>
            
            <h2>Resource Usage by Strategy</h2>
            <table>
                <tr>
                    <th>Strategy</th>
                    <th>CPU Usage (%)</th>
                    <th>Memory Usage (%)</th>
                </tr>
                {resource_stats.reset_index().to_html(index=False, header=False)}
            </table>
            
            <h2>Success Rate by Strategy</h2>
            <table>
                <tr>
                    <th>Strategy</th>
                    <th>Success Rate (%)</th>
                </tr>
                {success_stats.reset_index().to_html(index=False, header=False)}
            </table>
            
            <h2>Visualizations</h2>
            
            <h3>Recovery Time by Strategy</h3>
            <img src="recovery_time_by_strategy_{report_time}.png" alt="Recovery Time by Strategy">
            
            <h3>Recovery Time by Workload Type</h3>
            <img src="recovery_time_by_workload_{report_time}.png" alt="Recovery Time by Workload Type">
            
            <h3>Resource Usage by Strategy</h3>
            <img src="resource_usage_by_strategy_{report_time}.png" alt="Resource Usage by Strategy">
            
            <h3>Success Rate by Strategy</h3>
            <img src="success_rate_by_strategy_{report_time}.png" alt="Success Rate by Strategy">
            
            <h3>Partition Health Improvement</h3>
            <img src="partition_health_improvement_{report_time}.png" alt="Partition Health Improvement">
            
            <h3>Recovery Time Trend</h3>
            <img src="recovery_time_trend_{report_time}.png" alt="Recovery Time Trend">
            
            <h3>Correlation Between Metrics</h3>
            <img src="correlation_heatmap_{report_time}.png" alt="Correlation Heatmap">
        </body>
        </html>
        """
        
        with open(f"{output_dir}/recovery_analysis_report_{report_time}.html", "w") as f:
            f.write(html_report)
        
        print("\nVisualization and report saved in: " + output_dir)
        print("\nGenerated files:")
        print(f"- recovery_time_by_strategy_{report_time}.png")
        print(f"- recovery_time_by_workload_{report_time}.png")
        print(f"- resource_usage_by_strategy_{report_time}.png")
        print(f"- success_rate_by_strategy_{report_time}.png")
        print(f"- partition_health_improvement_{report_time}.png")
        print(f"- recovery_time_trend_{report_time}.png")
        print(f"- correlation_heatmap_{report_time}.png")
        print(f"- recovery_analysis_report_{report_time}.html")
    
    except Exception as e:
        print(f"Error creating visualizations: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze Kafka recovery statistics")
    parser.add_argument('--csv', default='/app/data/recovery_stats.csv',
                        help='Path to recovery stats CSV file')
    parser.add_argument('--output', default='/app/data/reports',
                        help='Directory to save analysis reports and visualizations')
    
    args = parser.parse_args()
    analyze_recovery_stats(args.csv, args.output)