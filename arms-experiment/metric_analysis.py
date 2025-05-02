import pandas as pd
import numpy as np
from sklearn.feature_selection import mutual_info_classif
from scipy.stats import spearmanr
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.model_selection import cross_val_score, StratifiedKFold
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import make_scorer, f1_score, accuracy_score, confusion_matrix, classification_report
import os
import time

# Set random seed for reproducibility
np.random.seed(42)

def run_feature_selection_pipeline(csv_path, output_dir='output', threshold=0.8):
    """
    Execute the two-stage feature selection pipeline on Kafka workload dataset.
    
    Args:
        csv_path: Path to the CSV dataset
        output_dir: Directory to save output files
        threshold: Threshold for feature selection (default: 1.2)
    
    Returns:
        Dictionary containing selected features and performance metrics
    """
    start_time = time.time()
    
    # Create output directory if it doesn't exist
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    print(f"Running two-stage feature selection pipeline on {csv_path}")
    print(f"Using selection threshold: {threshold}")
    
    # Step 1: Load and preprocess data
    print("\nStep 1: Loading and preprocessing data...")
    df = pd.read_csv(csv_path)
    print(f"Dataset shape: {df.shape}")
    print(f"Class distribution: \n{df['workload_type'].value_counts()}")
    
    # Separate features and target
    X = df.drop(['workload_type', 'timestamp'], axis=1)
    y = df['workload_type']
    feature_names = X.columns.tolist()
    
    print(f"Number of features: {len(feature_names)}")
    
    # Check for any missing values
    if X.isnull().sum().sum() > 0:
        print("Filling missing values with column means")
        X = X.fillna(X.mean())
    
    # Step 2: Spearman's Rank Correlation Analysis
    print("\nStep 2: Computing Spearman's Rank Correlation coefficients...")
    spearman_corrs = {}
    for column in feature_names:
        correlation, p_value = spearmanr(X[column], y)
        spearman_corrs[column] = abs(correlation)  # Take absolute value
    
    # Normalize Spearman correlations
    max_spearman = max(spearman_corrs.values())
    normalized_spearman = {k: v / max_spearman for k, v in spearman_corrs.items()}
    
    # Sort and display results
    spearman_results = pd.DataFrame({
        'Feature': list(spearman_corrs.keys()),
        'Absolute Spearman Correlation': list(spearman_corrs.values()),
        'Normalized Spearman': [normalized_spearman[feature] for feature in spearman_corrs.keys()]
    }).sort_values('Absolute Spearman Correlation', ascending=False)
    
    print("Top 5 features by Spearman correlation:")
    print(spearman_results.head(5))
    
    # Save Spearman results
    spearman_results.to_csv(f"{output_dir}/spearman_correlation_results.csv", index=False)
    
    # Step 3: Mutual Information Analysis
    print("\nStep 3: Computing Mutual Information scores...")
    mi_scores = mutual_info_classif(X, y, random_state=42)
    mi_scores_dict = {feature: score for feature, score in zip(feature_names, mi_scores)}
    
    # Normalize MI scores
    max_mi = max(mi_scores)
    normalized_mi = {k: v / max_mi for k, v in mi_scores_dict.items()}
    
    # Sort and display results
    mi_results = pd.DataFrame({
        'Feature': list(mi_scores_dict.keys()),
        'MI Score': list(mi_scores_dict.values()),
        'Normalized MI Score': [normalized_mi[feature] for feature in mi_scores_dict.keys()]
    }).sort_values('MI Score', ascending=False)
    
    print("Top 5 features by Mutual Information:")
    print(mi_results.head(5))
    
    # Save MI results
    mi_results.to_csv(f"{output_dir}/mutual_information_results.csv", index=False)
    
    # Step 4: Calculate Aggregated Importance Scores
    print("\nStep 4: Calculating aggregated importance scores...")
    aggregated_scores = {}
    for feature in feature_names:
        aggregated_scores[feature] = normalized_spearman[feature] + normalized_mi[feature]
    
    # Sort and display results
    aggregated_results = pd.DataFrame({
        'Feature': list(aggregated_scores.keys()),
        'Spearman Correlation': [spearman_corrs[feature] for feature in aggregated_scores.keys()],
        'Normalized Spearman': [normalized_spearman[feature] for feature in aggregated_scores.keys()],
        'MI Score': [mi_scores_dict[feature] for feature in aggregated_scores.keys()],
        'Normalized MI': [normalized_mi[feature] for feature in aggregated_scores.keys()],
        'Aggregated Score': list(aggregated_scores.values())
    }).sort_values('Aggregated Score', ascending=False)
    
    print("Top 5 features by Aggregated Score:")
    print(aggregated_results.head(5))
    
    # Save aggregated results
    aggregated_results.to_csv(f"{output_dir}/aggregated_feature_importance.csv", index=False)
    
    # Select features with aggregated scores exceeding threshold
    selected_features = [feature for feature, score in aggregated_scores.items() if score > threshold]
    
    print(f"\nSelected Features (threshold {threshold}): {len(selected_features)}")
    print(selected_features)
    
    # Step 5: Visualize Feature Importance
    print("\nStep 5: Visualizing feature importance...")
    plt.figure(figsize=(12, 8))
    sns.barplot(x='Aggregated Score', y='Feature', data=aggregated_results)
    plt.axvline(x=threshold, color='red', linestyle='--', label=f'Selection Threshold ({threshold})')
    plt.title('Feature Importance Scores')
    plt.legend()
    plt.tight_layout()
    plt.savefig(f"{output_dir}/feature_importance.png")
    
    # Visualize correlation matrix for selected features
    if len(selected_features) > 1:  # Only create heatmap if we have multiple features
        plt.figure(figsize=(12, 10))
        correlation_matrix = X[selected_features].corr()
        sns.heatmap(correlation_matrix, annot=True, cmap='coolwarm', fmt=".2f")
        plt.title('Correlation Matrix of Selected Features')
        plt.tight_layout()
        plt.savefig(f"{output_dir}/correlation_matrix.png")
    
    # Step 6: Validate Feature Selection with Cross-Validation
    print("\nStep 6: Validating feature selection with cross-validation...")
    
    # Function to evaluate model with different feature subsets
    def evaluate_feature_set(X, y, features, cv=5):
        if len(features) == 0:
            return {
                'accuracy_mean': 0,
                'accuracy_std': 0,
                'f1_mean': 0,
                'f1_std': 0,
                'n_features': 0
            }
        
        X_subset = X[features]
        
        # Initialize model
        model = RandomForestClassifier(random_state=42)
        
        # Define metrics
        accuracy = cross_val_score(model, X_subset, y, cv=StratifiedKFold(cv), scoring='accuracy')
        f1 = cross_val_score(model, X_subset, y, cv=StratifiedKFold(cv), 
                            scoring=make_scorer(f1_score, average='macro'))
        
        return {
            'accuracy_mean': accuracy.mean(),
            'accuracy_std': accuracy.std(),
            'f1_mean': f1.mean(),
            'f1_std': f1.std(),
            'n_features': len(features)
        }
    
    # Test different thresholds to validate the chosen threshold
    thresholds = [0.8, 1.0, 1.2, 1.4, 1.6, 1.8]
    threshold_results = []
    
    for t in thresholds:
        selected = [feature for feature, score in aggregated_scores.items() if score > t]
        results = evaluate_feature_set(X, y, selected)
        results['threshold'] = t
        results['features'] = ', '.join(selected) if selected else 'None'
        threshold_results.append(results)
    
    # Display results
    threshold_df = pd.DataFrame(threshold_results)
    print("\nPerformance across different thresholds:")
    print(threshold_df[['threshold', 'n_features', 'accuracy_mean', 'f1_mean']])
    
    # Save threshold evaluation results
    threshold_df.to_csv(f"{output_dir}/threshold_evaluation.csv", index=False)
    
    # Step 7: Plot performance across thresholds
    print("\nStep 7: Plotting performance across thresholds...")
    plt.figure(figsize=(10, 6))
    plt.plot(threshold_df['threshold'], threshold_df['accuracy_mean'], 'o-', label='Accuracy')
    plt.plot(threshold_df['threshold'], threshold_df['f1_mean'], 's-', label='F1 Score')
    plt.axvline(x=threshold, color='red', linestyle='--', label=f'Selected Threshold ({threshold})')
    plt.xlabel('Threshold')
    plt.ylabel('Score')
    plt.title('Model Performance vs. Feature Selection Threshold')
    plt.legend()
    plt.grid(True)
    plt.savefig(f"{output_dir}/threshold_performance.png")
    
    # Step 8: Final Model Evaluation with Selected Features
    print("\nStep 8: Final model evaluation with selected features...")
    if selected_features:
        X_selected = X[selected_features]
        
        # Train final model
        final_model = RandomForestClassifier(random_state=42)
        
        # Perform cross-validation
        cv = StratifiedKFold(5, shuffle=True, random_state=42)
        cv_results = cross_val_score(final_model, X_selected, y, cv=cv, scoring='accuracy')
        
        print(f"Cross-validation accuracy: {cv_results.mean():.4f} ± {cv_results.std():.4f}")
        
        # Train on full dataset to get feature importances
        final_model.fit(X_selected, y)
        feature_importance = pd.DataFrame({
            'Feature': selected_features,
            'Importance': final_model.feature_importances_
        }).sort_values('Importance', ascending=False)
        
        print("\nRandom Forest Feature Importance:")
        print(feature_importance)
        
        # Save feature importance
        feature_importance.to_csv(f"{output_dir}/rf_feature_importance.csv", index=False)
        
        # Plot feature importance
        plt.figure(figsize=(10, 6))
        sns.barplot(x='Importance', y='Feature', data=feature_importance)
        plt.title('Random Forest Feature Importance')
        plt.tight_layout()
        plt.savefig(f"{output_dir}/rf_feature_importance.png")
    else:
        print("No features selected with the current threshold.")
    
    # Step 9: Compare with all features
    print("\nStep 9: Comparing selected features with all features...")
    all_features_results = evaluate_feature_set(X, y, feature_names)
    selected_features_results = evaluate_feature_set(X, y, selected_features) if selected_features else {'accuracy_mean': 0, 'f1_mean': 0, 'n_features': 0}
    
    comparison = pd.DataFrame([
        {'Feature Set': 'All Features', 'Features': len(feature_names), 'Accuracy': all_features_results['accuracy_mean'], 'F1 Score': all_features_results['f1_mean']},
        {'Feature Set': 'Selected Features', 'Features': len(selected_features), 'Accuracy': selected_features_results['accuracy_mean'], 'F1 Score': selected_features_results['f1_mean']}
    ])
    
    print(comparison)
    comparison.to_csv(f"{output_dir}/feature_set_comparison.csv", index=False)
    
    # Step 10: Summary Report
    elapsed_time = time.time() - start_time
    
    summary = {
        'total_features': len(feature_names),
        'selected_features': len(selected_features),
        'selected_feature_names': selected_features,
        'threshold_used': threshold,
        'accuracy_selected': selected_features_results['accuracy_mean'],
        'f1_score_selected': selected_features_results['f1_mean'],
        'accuracy_all': all_features_results['accuracy_mean'],
        'f1_score_all': all_features_results['f1_mean'],
        'processing_time_seconds': elapsed_time
    }
    
    # Save summary to file
    with open(f"{output_dir}/feature_selection_summary.txt", 'w') as f:
        f.write("Kafka Workload Feature Selection Summary\n")
        f.write("=======================================\n\n")
        f.write(f"Total features available: {summary['total_features']}\n")
        f.write(f"Selected features: {summary['selected_features']}\n")
        f.write(f"Selection threshold: {summary['threshold_used']}\n\n")
        f.write("Selected feature names:\n")
        for feature in summary['selected_feature_names']:
            f.write(f"- {feature}\n")
        f.write("\nPerformance Comparison:\n")
        f.write(f"All features ({summary['total_features']}): Accuracy={summary['accuracy_all']:.4f}, F1={summary['f1_score_all']:.4f}\n")
        f.write(f"Selected features ({summary['selected_features']}): Accuracy={summary['accuracy_selected']:.4f}, F1={summary['f1_score_selected']:.4f}\n\n")
        f.write(f"Processing time: {summary['processing_time_seconds']:.2f} seconds\n")
    
    print(f"\nFeature selection complete. Results saved to {output_dir}/")
    print(f"Processing time: {elapsed_time:.2f} seconds")
    
    return summary

if __name__ == "__main__":
    # Execute the pipeline
    csv_path = "/Users/nwaoghorpraise/Documents/ARMS PROJECT/arms-experiment/datasets/balanced_kafka_dataset_3000.csv"
    summary = run_feature_selection_pipeline(csv_path, output_dir="kafka_feature_selection_output")
    
    print("\nSelected Features:")
    for feature in summary['selected_feature_names']:
        print(f"- {feature}")