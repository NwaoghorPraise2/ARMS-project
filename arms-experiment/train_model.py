# Import necessary libraries
import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.preprocessing import StandardScaler
import matplotlib.pyplot as plt
import seaborn as sns
import joblib
import time

# Start timing
start_time = time.time()

print("Training Logistic Regression Model for Kafka Workload Classification")
print("-" * 60)

# Load the dataset
print("Loading dataset...")
df = pd.read_csv('balanced_kafka_dataset_3000.csv')
print(f"Dataset shape: {df.shape}")
print(f"Class distribution:\n{df['workload_type'].value_counts()}")

# Select the top features identified by feature selection
selected_features = [
    'request_rate_variance',
    'node_disk_write_bytes_total',
    'message_rate_variance',
    'node_memory_MemAvailable_bytes'
]

print(f"\nSelected features: {selected_features}")

# Create the feature matrix and target vector
X = df[selected_features]
y = df['workload_type']

# Split into training and test sets (80% train, 20% test)
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

print(f"Training set shape: {X_train.shape}")
print(f"Test set shape: {X_test.shape}")

# Standardize features (important for logistic regression)
print("\nStandardizing features...")
scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)

# Train the Logistic Regression model
print("\nTraining Logistic Regression model...")
train_start = time.time()
model = LogisticRegression(random_state=42, max_iter=1000)
model.fit(X_train_scaled, y_train)
train_time = time.time() - train_start
print(f"Training completed in {train_time:.4f} seconds")

# Evaluate the model
print("\nEvaluating model performance...")
inference_start = time.time()
y_pred = model.predict(X_test_scaled)
inference_time = time.time() - inference_start
inference_per_sample = inference_time / len(X_test)

# Calculate metrics
accuracy = accuracy_score(y_test, y_pred)
conf_matrix = confusion_matrix(y_test, y_pred)

print(f"Accuracy: {accuracy:.4f}")
print(f"Inference time: {inference_time:.6f} seconds total")
print(f"Inference time per sample: {inference_per_sample*1000:.6f} ms")
print("\nClassification Report:")
print(classification_report(y_test, y_pred))

print("\nConfusion Matrix:")
print(conf_matrix)

# Perform cross-validation
print("\nPerforming 5-fold cross-validation...")
cv_scores = cross_val_score(model, scaler.transform(X), y, cv=5)
print(f"Cross-validation accuracy: {cv_scores.mean():.4f} ± {cv_scores.std():.4f}")

# Model coefficients
print("\nModel Coefficients:")
coef_df = pd.DataFrame({
    'Feature': selected_features,
    'Coefficient': model.coef_[0]
})
print(coef_df.sort_values('Coefficient', ascending=False))

# Save the model and scaler
print("\nSaving model and scaler...")
joblib.dump(model, 'kafka_logistic_regression_model.pkl')
joblib.dump(scaler, 'kafka_feature_scaler.pkl')
print("Model saved as 'kafka_logistic_regression_model.pkl'")
print("Scaler saved as 'kafka_feature_scaler.pkl'")

# Visualize results
print("\nGenerating visualizations...")

# 1. Confusion Matrix Heatmap
plt.figure(figsize=(8, 6))
sns.heatmap(conf_matrix, annot=True, fmt='d', cmap='Blues',
            xticklabels=['Type 0', 'Type 1'],
            yticklabels=['Type 0', 'Type 1'])
plt.xlabel('Predicted Label')
plt.ylabel('True Label')
plt.title('Confusion Matrix')
plt.tight_layout()
plt.savefig('confusion_matrix.png')

# 2. Feature Importance (Coefficients)
plt.figure(figsize=(10, 6))
coef_df = coef_df.sort_values('Coefficient', ascending=True)
sns.barplot(x='Coefficient', y='Feature', data=coef_df)
plt.title('Feature Importance (Logistic Regression Coefficients)')
plt.tight_layout()
plt.savefig('feature_importance.png')

# 3. Cross-validation results
plt.figure(figsize=(8, 6))
sns.barplot(x=range(1, 6), y=cv_scores)
plt.axhline(y=cv_scores.mean(), color='r', linestyle='--', label=f'Mean: {cv_scores.mean():.4f}')
plt.xlabel('Fold')
plt.ylabel('Accuracy')
plt.title('5-Fold Cross-Validation Results')
plt.ylim(0.8, 1.0)
plt.legend()
plt.tight_layout()
plt.savefig('cross_validation.png')

# Calculate total runtime
total_time = time.time() - start_time
print(f"\nTotal script runtime: {total_time:.2f} seconds")
print("\nTraining complete! Model is ready for deployment.")