package org.arms.orchestrator;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.apache.kafka.clients.consumer.Consumer;
import org.apache.kafka.clients.consumer.ConsumerConfig;
import org.apache.kafka.clients.consumer.ConsumerRecords;
import org.apache.kafka.clients.consumer.KafkaConsumer;
import org.apache.kafka.clients.producer.KafkaProducer;
import org.apache.kafka.clients.producer.Producer;
import org.apache.kafka.clients.producer.ProducerConfig;
import org.apache.kafka.clients.producer.ProducerRecord;
import org.apache.kafka.common.serialization.StringDeserializer;
import org.apache.kafka.common.serialization.StringSerializer;
import org.arms.common.models.*;
import org.arms.orchestrator.actions.RecoveryActions;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.time.Duration;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * Orchestrates the recovery process by applying selected strategies
 * to the Kafka cluster.
 */
public class RecoveryOrchestrator implements AutoCloseable {
    private static final Logger logger = LoggerFactory.getLogger(RecoveryOrchestrator.class);
    private static final String STRATEGIES_TOPIC = "arms-strategies";
    private static final String RECOVERY_METRICS_TOPIC = "arms-recovery-metrics";
    private static final String FAILURE_EVENTS_TOPIC = "arms-failure-events";
    
    private final String bootstrapServers;
    private final Consumer<String, String> consumer;
    private final Producer<String, String> producer;
    private final RecoveryActions recoveryActions;
    private final ObjectMapper objectMapper;
    private final AtomicBoolean running;
    
    // Track active recoveries
    private final Map<String, RecoveryState> activeRecoveries;
    
    /**
     * State of a recovery operation.
     */
    private static class RecoveryState {
        private final RecoveryStrategy strategy;
        private final List<String> affectedTopics;
        private final List<Integer> failedBrokers;
        private final long startTime;
        private long completionTime;
        private boolean completed;
        private boolean successful;
        
        public RecoveryState(RecoveryStrategy strategy, List<String> affectedTopics, 
                           List<Integer> failedBrokers) {
            this.strategy = strategy;
            this.affectedTopics = affectedTopics;
            this.failedBrokers = failedBrokers;
            this.startTime = System.currentTimeMillis();
            this.completionTime = 0;
            this.completed = false;
            this.successful = false;
        }
        
        public void complete(boolean successful) {
            this.completed = true;
            this.successful = successful;
            this.completionTime = System.currentTimeMillis();
        }
        
        public long getDurationMs() {
            if (!completed) {
                return System.currentTimeMillis() - startTime;
            }
            return completionTime - startTime;
        }
    }
    
    /**
     * Initialize the recovery orchestrator.
     * 
     * @param bootstrapServers Kafka bootstrap servers
     */
    public RecoveryOrchestrator(String bootstrapServers) {
        this.bootstrapServers = bootstrapServers;
        this.objectMapper = new ObjectMapper();
        this.running = new AtomicBoolean(false);
        this.activeRecoveries = new ConcurrentHashMap<>();
        
        // Set up Kafka consumer
        Properties consumerProps = new Properties();
        consumerProps.put(ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG, bootstrapServers);
        consumerProps.put(ConsumerConfig.GROUP_ID_CONFIG, "arms-orchestrator");
        consumerProps.put(ConsumerConfig.AUTO_OFFSET_RESET_CONFIG, "latest");
        consumerProps.put(ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class.getName());
        consumerProps.put(ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class.getName());
        this.consumer = new KafkaConsumer<>(consumerProps);
        
        // Set up Kafka producer
        Properties producerProps = new Properties();
        producerProps.put(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG, bootstrapServers);
        producerProps.put(ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG, StringSerializer.class.getName());
        producerProps.put(ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG, StringSerializer.class.getName());
        this.producer = new KafkaProducer<>(producerProps);
        
        // Set up recovery actions
        this.recoveryActions = new RecoveryActions(bootstrapServers);
        
        logger.info("Recovery orchestrator initialized with bootstrap servers: {}", bootstrapServers);
    }
    
    /**
     * Start the recovery orchestrator service.
     */
    public void start() {
        if (running.compareAndSet(false, true)) {
            logger.info("Starting recovery orchestrator");
            
            // Subscribe to topics
            consumer.subscribe(Arrays.asList(STRATEGIES_TOPIC, FAILURE_EVENTS_TOPIC));
            
            // Start main processing loop
            Thread processingThread = new Thread(this::processMessages);
            processingThread.setName("recovery-orchestrator-thread");
            processingThread.setDaemon(true);
            processingThread.start();
        }
    }
    
    /**
     * Stop the recovery orchestrator service.
     */
    public void stop() {
        if (running.compareAndSet(true, false)) {
            logger.info("Stopping recovery orchestrator");
        }
    }
    
    /**
     * Main message processing loop.
     */
    private void processMessages() {
        try {
            while (running.get()) {
                ConsumerRecords<String, String> records = consumer.poll(Duration.ofMillis(100));
                
                records.forEach(record -> {
                    try {
                        // Process message based on topic
                        switch (record.topic()) {
                            case STRATEGIES_TOPIC:
                                processStrategyMessage(record.value());
                                break;
                                
                            case FAILURE_EVENTS_TOPIC:
                                processFailureEvent(record.value());
                                break;
                                
                            default:
                                logger.warn("Received message from unexpected topic: {}", record.topic());
                        }
                    } catch (Exception e) {
                        logger.error("Error processing message: {}", e.getMessage(), e);
                    }
                });
                
                // Check timeouts for active recoveries
                checkRecoveryTimeouts();
            }
        } catch (Exception e) {
            logger.error("Error in processing loop: {}", e.getMessage(), e);
        } finally {
            logger.info("Exiting processing loop");
        }
    }
    
    /**
     * Process a strategy message from the strategy selector.
     * 
     * @param message The JSON strategy message
     */
    private void processStrategyMessage(String message) {
        try {
            // Parse message
            Map<String, Object> messageData = objectMapper.readValue(message, Map.class);
            
            // Extract strategy from message
            Map<String, Object> strategyData = (Map<String, Object>) messageData.get("strategy");
            
            // Only process if we have an active failure event that needs this strategy
            String recoveryId = (String) messageData.getOrDefault("recovery_id", null);
            if (recoveryId != null && activeRecoveries.containsKey(recoveryId)) {
                RecoveryState state = activeRecoveries.get(recoveryId);
                
                // Convert to RecoveryStrategy and update the state
                RecoveryStrategy strategy = convertToRecoveryStrategy(strategyData);
                
                // Apply the strategy
                applyRecoveryStrategy(recoveryId, strategy, state.affectedTopics, state.failedBrokers);
            } else {
                logger.info("Received strategy without active recovery, storing for future failures");
                // In a full implementation, we might store this for future use
            }
        } catch (Exception e) {
            logger.error("Error processing strategy message: {}", e.getMessage(), e);
        }
    }
    
    /**
     * Process a failure event message.
     * 
     * @param message The JSON failure event message
     */
    private void processFailureEvent(String message) {
        try {
            // Parse message
            Map<String, Object> failureEvent = objectMapper.readValue(message, Map.class);
            
            // Extract failure details
            String recoveryId = (String) failureEvent.get("recovery_id");
            List<String> affectedTopics = (List<String>) failureEvent.get("affected_topics");
            List<Integer> failedBrokers = (List<Integer>) failureEvent.get("failed_brokers");
            
            logger.info("Processing failure event {}: {} brokers, {} topics affected", 
                       recoveryId, failedBrokers.size(), affectedTopics.size());
            
            // Create recovery state and track it
            RecoveryStrategy defaultStrategy = RecoveryStrategy.createDefaultConservativeStrategy();
            RecoveryState state = new RecoveryState(defaultStrategy, affectedTopics, failedBrokers);
            activeRecoveries.put(recoveryId, state);
            
            // Initially apply a conservative strategy while waiting for the selector's decision
            logger.info("Applying initial conservative recovery strategy");
            applyRecoveryStrategy(recoveryId, defaultStrategy, affectedTopics, failedBrokers);
        } catch (Exception e) {
            logger.error("Error processing failure event: {}", e.getMessage(), e);
        }
    }
    
    /**
     * Apply a recovery strategy to the Kafka cluster.
     * 
     * @param recoveryId ID of the recovery operation
     * @param strategy Recovery strategy to apply
     * @param affectedTopics List of topics affected by the failure
     * @param failedBrokers List of failed broker IDs
     */
    private void applyRecoveryStrategy(String recoveryId, RecoveryStrategy strategy, 
                                     List<String> affectedTopics, List<Integer> failedBrokers) {
        RecoveryState state = activeRecoveries.get(recoveryId);
        if (state == null) {
            logger.warn("Recovery state not found for ID: {}", recoveryId);
            return;
        }
        
        logger.info("Applying recovery strategy {} for recovery {}", 
                  strategy.getName(), recoveryId);
        
        try {
            // Record metrics before recovery starts
            RecoveryMetrics preRecoveryMetrics = collectRecoveryMetrics(recoveryId, state, false);
            publishRecoveryMetrics(preRecoveryMetrics);
            
            // Apply the strategy
            boolean success = recoveryActions.applyRecoveryStrategy(strategy, affectedTopics, failedBrokers);
            
            // Update recovery state
            state.complete(success);
            
            // Record and publish metrics after recovery
            RecoveryMetrics postRecoveryMetrics = collectRecoveryMetrics(recoveryId, state, true);
            publishRecoveryMetrics(postRecoveryMetrics);
            
            logger.info("Recovery {} {}: duration {}ms", 
                      recoveryId, success ? "succeeded" : "failed", state.getDurationMs());
            
            // If successful, we can remove it from active recoveries
            if (success) {
                activeRecoveries.remove(recoveryId);
            }
        } catch (Exception e) {
            logger.error("Error applying recovery strategy: {}", e.getMessage(), e);
            
            // Mark as failed
            state.complete(false);
            
            // Publish failure metrics
            RecoveryMetrics failureMetrics = collectRecoveryMetrics(recoveryId, state, true);
            publishRecoveryMetrics(failureMetrics);
        }
    }
    
    /**
     * Check for timeouts in active recoveries.
     */
    private void checkRecoveryTimeouts() {
        long now = System.currentTimeMillis();
        
        // Check each active recovery
        Iterator<Map.Entry<String, RecoveryState>> it = activeRecoveries.entrySet().iterator();
        while (it.hasNext()) {
            Map.Entry<String, RecoveryState> entry = it.next();
            RecoveryState state = entry.getValue();
            
            // Check if recovery has been running too long (5 minutes)
            if (!state.completed && (now - state.startTime) > 300000) {
                logger.warn("Recovery {} timed out after {}ms", entry.getKey(), state.getDurationMs());
                
                // Mark as failed due to timeout
                state.complete(false);
                
                // Publish timeout metrics
                RecoveryMetrics timeoutMetrics = collectRecoveryMetrics(entry.getKey(), state, true);
                publishRecoveryMetrics(timeoutMetrics);
                
                // Remove from active recoveries
                it.remove();
            }
        }
    }
    
    /**
     * Collect recovery metrics from the current state.
     * 
     * @param recoveryId ID of the recovery operation
     * @param state Current recovery state
     * @param isComplete Whether recovery is complete
     * @return RecoveryMetrics object
     */
    private RecoveryMetrics collectRecoveryMetrics(String recoveryId, RecoveryState state, boolean isComplete) {
        RecoveryMetrics metrics = new RecoveryMetrics();
        
        // Basic information
        metrics.setRecoveryId(recoveryId);
        metrics.setStrategyName(state.strategy.getName());
        metrics.setTimestamp(System.currentTimeMillis());
        
        // Time metrics
        metrics.setStartTime(state.startTime);
        
        if (isComplete) {
            metrics.setCompletionTime(state.completionTime);
            metrics.setSuccessful(state.successful);
        } else {
            metrics.setCompletionTime(0);
            metrics.setSuccessful(false);
        }
        
        // In a full implementation, we would collect actual metrics from the Kafka cluster
        // For this example, we'll use simplistic metrics
        metrics.setTimeToFirstMessage(isComplete ? state.getDurationMs() / 2 : 0);
        metrics.setTimeToFullRecovery(isComplete ? state.getDurationMs() : 0);
        metrics.setMessageLossRate(isComplete ? (state.successful ? 0.0 : 5.0) : 0.0);
        
        // Resource metrics - in a real implementation, these would be collected from the system
        metrics.setCpuUtilization(75.0);
        metrics.setMemoryUtilization(60.0);
        metrics.setDiskIo(45.0);


        // metrics.// ... continuing from where we left off in collectRecoveryMetrics method
    
        // Resource metrics - in a real implementation, these would be collected from the system

        metrics.setCpuUtilization(75.0);
        metrics.setMemoryUtilization(60.0);
        metrics.setDiskIo(45.0);
        metrics.setNetworkIo(50.0);
        
        return metrics;
    }
    
    /**
     * Publish recovery metrics to Kafka.
     * 
     * @param metrics Recovery metrics to publish
     */
    private void publishRecoveryMetrics(RecoveryMetrics metrics) {
        try {
            String metricsJson = objectMapper.writeValueAsString(metrics);
            ProducerRecord<String, String> record = new ProducerRecord<>(
                RECOVERY_METRICS_TOPIC, metrics.getRecoveryId(), metricsJson);
            
            producer.send(record, (metadata, exception) -> {
                if (exception != null) {
                    logger.error("Error publishing recovery metrics: {}", exception.getMessage(), exception);
                } else {
                    logger.debug("Published recovery metrics for {}", metrics.getRecoveryId());
                }
            });
        } catch (Exception e) {
            logger.error("Error serializing recovery metrics: {}", e.getMessage(), e);
        }
    }
    
    /**
     * Convert a map of strategy data to a RecoveryStrategy object.
     * 
     * @param strategyData Map of strategy data from JSON
     * @return RecoveryStrategy object
     */
    private RecoveryStrategy convertToRecoveryStrategy(Map<String, Object> strategyData) {
        RecoveryStrategy strategy = new RecoveryStrategy();
        
        // Set basic properties
        strategy.setName((String) strategyData.getOrDefault("name", "Unknown Strategy"));
        
        // Set enum values by converting strings to enums
        String consistencyLevel = (String) strategyData.getOrDefault("consistency_level", "STRONG");
        strategy.setConsistencyLevel(ConsistencyLevel.valueOf(consistencyLevel.toUpperCase()));
        
        String acknPolicy = (String) strategyData.getOrDefault("acknowledgement_policy", "QUORUM");
        strategy.setAcknowledgementPolicy(AcknowledgementPolicy.valueOf(acknPolicy.toUpperCase()));
        
        String reassignStrategy = (String) strategyData.getOrDefault("partition_reassignment_strategy", "BALANCED");
        strategy.setPartitionReassignmentStrategy(PartitionReassignmentStrategy.valueOf(reassignStrategy.toUpperCase()));
        
        String syncMode = (String) strategyData.getOrDefault("synchronisation_mode", "BACKGROUND");
        strategy.setSynchronisationMode(SynchronisationMode.valueOf(syncMode.toUpperCase()));
        
        String rebalanceStrategy = (String) strategyData.getOrDefault("consumer_rebalance_strategy", "RANGE");
        strategy.setConsumerRebalanceStrategy(ConsumerRebalanceStrategy.valueOf(rebalanceStrategy.toUpperCase()));
        
        // Set numeric and boolean values
        strategy.setMaxReplicasToRestore(((Number) strategyData.getOrDefault("max_replicas_to_restore", 2)).intValue());
        strategy.setValidationEnabled((Boolean) strategyData.getOrDefault("validation_enabled", false));
        strategy.setThrottlingEnabled((Boolean) strategyData.getOrDefault("throttling_enabled", false));
        
        // Set additional parameters
        strategy.setAdditionalParams((Map<String, String>) strategyData.getOrDefault("additional_params", new HashMap<>()));
        
        return strategy;
    }
    
    @Override
    public void close() {
        stop();
        
        try {
            // Close resources
            if (consumer != null) {
                consumer.close();
            }
            
            if (producer != null) {
                producer.close();
            }
            
            if (recoveryActions != null) {
                recoveryActions.close();
            }
            
            logger.info("Recovery orchestrator closed");
        } catch (Exception e) {
            logger.error("Error closing recovery orchestrator", e);
        }
    }
    
    /**
     * Main method to run the orchestrator as a standalone service.
     */
    public static void main(String[] args) {
        String bootstrapServers = "kafka-1:9092,kafka-2:9092,kafka-3:9092";
        
        // Parse command line arguments
        for (int i = 0; i < args.length; i++) {
            if ("--bootstrap-servers".equals(args[i]) && i < args.length - 1) {
                bootstrapServers = args[i + 1];
                i++;
            }
        }
        
        try (RecoveryOrchestrator orchestrator = new RecoveryOrchestrator(bootstrapServers)) {
            // Start the orchestrator
            orchestrator.start();
            
            // Register shutdown hook
            Runtime.getRuntime().addShutdownHook(new Thread(orchestrator::close));
            
            // Keep the main thread alive
            Thread.currentThread().join();
        } catch (Exception e) {
            logger.error("Error running recovery orchestrator: {}", e.getMessage(), e);
            System.exit(1);
        }
    }
}