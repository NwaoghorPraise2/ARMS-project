# Adaptive Recovery Management System (ARMS)

## Optimising Recovery in AI Workload Pipeline Message Brokering Systems Using Machine Learning: Adaptive Strategies for Time and Resource Efficiency

### Problem

- Static recovery configurations for diverse workloads
- One-size-fits-all approach ignores workload differences
- Inefficient resource usage for non-critical tasks

### Research Questions

- RQ1: What are the operational dimensions of AI workloads in message brokering systems?
- RQ1.1: What are the distinct reliability expectations for different workload types based
  on the operational dimensions?
- RQ2: What are the key real-time metrics that most effectively indicate workload
  classification in an AI message broking system?
- RQ3: How accurately can a machine learning model classify incoming AI workloads based
  on real-time system metrics in an AI message broking system?
- RQ4: How can rule-based systems translate machine learning classification outcomes into
  optimal recovery decisions in an AI message broking system?
- RQ5: To what extent does the ARMS framework improve recovery time and resource efficiency in Apache Kafka compared to static configurations?

### System Architecture

- **Metric Collector**: Gathers system telemetry from Kafka brokers via Prometheus
- **Workload Classifier**: Logistic Regression model (96.17% accuracy) with 5 key features
- **Strategy Selector**: Rule-based mapping with 90% confidence threshold
- **Recovery Strategies**:
  - QUICK_REBALANCE (real-time workloads)
  - RESOURCE_OPTIMIZED (batch workloads)
  - CONTROLLED_GRADUAL (default/low confidence)

### Key Findings

- 6.14s mean reduction in recovery time for real-time workloads (p < 0.001)
- Neutral impact on batch workload recovery (mean difference: -0.11s, p = 0.9986)
- 15% memory usage increase across all configurations
- Selective CPU efficiency improvement for real-time workloads (3.05% reduction)
- Classification accuracy of 96.17% with minimal inference latency (0.08ms)

### Technical Challenges

1. **Metric Volatility**: Solved with hybrid feature selection pipeline
2. **Classification Overhead**: Shifted from Random Forest to Logistic Regression
3. **Kafka Rebalancing Latency**: Implemented workload-specific parameter tuning
4. **Memory-Latency Trade-off**: Quantified cost of adaptive intelligence

### Research Contributions

- Integration of workload classification with recovery mechanisms
- Empirical validation of adaptive recovery in message brokering systems
- Resource-performance trade-off model for adaptive middleware
- Framework for self-optimizing infrastructure components
- Operational implementation patterns for workload-aware resilience

### Future Work

- Reinforcement learning for continuous strategy refinement
- Expanded taxonomy beyond binary workload classification
- Cross-platform implementation for alternative message brokers
- Proactive failure prediction integration
- Multi-cluster resilience coordination for geo-distributed deployments

---

_Nwaoghor Praise Chukunweiken – University of Hertfordshire – MSc Software Engineering – April 2025_
