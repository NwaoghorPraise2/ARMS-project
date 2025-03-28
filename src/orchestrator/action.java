package org.arms.orchestrator.actions;

import org.apache.kafka.clients.admin.*;
import org.apache.kafka.common.TopicPartition;
import org.apache.kafka.common.Node;
import org.apache.kafka.common.config.ConfigResource;
import org.apache.kafka.common.KafkaFuture;
import org.arms.common.models.RecoveryStrategy;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.*;
import java.util.concurrent.ExecutionException;
import java.util.stream.Collectors;

/**
 * Provides recovery actions that can be executed on a Kafka cluster.
 */
public class RecoveryActions {
    private static final Logger logger = LoggerFactory.getLogger(RecoveryActions.class);
    private final AdminClient adminClient;
    
    /**
     * Initializes recovery actions with Kafka admin client.
     * 
     * @param bootstrapServers Kafka bootstrap servers
     */
    public RecoveryActions(String bootstrapServers) {
        Properties props = new Properties();
        props.put(AdminClientConfig.BOOTSTRAP_SERVERS_CONFIG, bootstrapServers);
        this.adminClient = AdminClient.create(props);
        logger.info("Initialized RecoveryActions with bootstrap servers: {}", bootstrapServers);
    }
    
    /**
     * Apply a recovery strategy to the cluster.
     * 
     * @param strategy The recovery strategy to apply
     * @param affectedTopics List of topics affected by the failure
     * @param failedBrokers List of failed broker IDs
     * @return true if successful, false otherwise
     */
    public boolean applyRecoveryStrategy(RecoveryStrategy strategy, List<String> affectedTopics, 
                                        List<Integer> failedBrokers) {
        logger.info("Applying recovery strategy: {}", strategy.getName());
        
        try {
            // Step 1: Configure broker settings according to strategy
            configureBrokerSettings(strategy);
            
            // Step 2: Handle partition reassignment based on strategy
            handlePartitionReassignment(strategy, affectedTopics, failedBrokers);
            
            // Step 3: Configure client-side settings (producers/consumers)
            configureClientSettings(strategy, affectedTopics);
            
            // Step 4: Perform post-recovery validation if required
            if (strategy.isValidationEnabled()) {
                performValidation(affectedTopics);
            }
            
            logger.info("Successfully applied recovery strategy: {}", strategy.getName());
            return true;
        } catch (Exception e) {
            logger.error("Error applying recovery strategy: {}", e.getMessage(), e);
            return false;
        }
    }
    
    /**
     * Configure broker settings according to the recovery strategy.
     * 
     * @param strategy The recovery strategy
     * @throws ExecutionException If configuration fails
     * @throws InterruptedException If operation is interrupted
     */
    private void configureBrokerSettings(RecoveryStrategy strategy) 
            throws ExecutionException, InterruptedException {
        logger.info("Configuring broker settings");
        
        // Get all brokers to configure
        Collection<Node> nodes = adminClient.describeCluster().nodes().get();
        
        // Convert RecoveryStrategy to Kafka broker configurations
        Map<String, String> configs = convertStrategyToBrokerConfigs(strategy);
        
        // Apply configurations to each broker
        for (Node node : nodes) {
            ConfigResource resource = new ConfigResource(ConfigResource.Type.BROKER, String.valueOf(node.id()));
            
            // Create configuration entries
            Collection<ConfigEntry> entries = configs.entrySet().stream()
                .map(e -> new ConfigEntry(e.getKey(), e.getValue()))
                .collect(Collectors.toList());
            
            Config config = new Config(entries);
            
            // Apply configuration changes
            adminClient.alterConfigs(Collections.singletonMap(resource, config)).all().get();
            logger.info("Applied configuration to broker {}", node.id());
        }
    }
    
    /**
     * Convert recovery strategy to Kafka broker configurations.
     * 
     * @param strategy The recovery strategy
     * @return Map of configuration keys and values
     */
    private Map<String, String> convertStrategyToBrokerConfigs(RecoveryStrategy strategy) {
        Map<String, String> configs = new HashMap<>();
        
        // Convert consistency level to configs
        switch (strategy.getConsistencyLevel()) {
            case STRICT:
                configs.put("unclean.leader.election.enable", "false");
                break;
            case STRONG:
                configs.put("unclean.leader.election.enable", "false");
                break;
            case EVENTUAL:
                configs.put("unclean.leader.election.enable", "true");
                break;
        }
        
        // Set min.insync.replicas based on consistency
        configs.put("min.insync.replicas", String.valueOf(
            Math.max(1, strategy.getMaxReplicasToRestore() / 2 + 1)));
        
        // Set throttling if enabled
        if (strategy.isThrottlingEnabled()) {
            configs.put("leader.replication.throttled.rate", "10485760"); // 10MB/s
            configs.put("follower.replication.throttled.rate", "10485760"); // 10MB/s
        } else {
            configs.put("leader.replication.throttled.rate", "");
            configs.put("follower.replication.throttled.rate", "");
        }
        
        // Add additional parameters if present
        if (strategy.getAdditionalParams() != null) {
            configs.putAll(strategy.getAdditionalParams());
        }
        
        return configs;
    }
    
    /**
     * Handle partition reassignment based on the recovery strategy.
     * 
     * @param strategy The recovery strategy
     * @param affectedTopics List of topics affected by the failure
     * @param failedBrokers List of failed broker IDs
     * @throws ExecutionException If reassignment fails
     * @throws InterruptedException If operation is interrupted
     */
    private void handlePartitionReassignment(RecoveryStrategy strategy, List<String> affectedTopics, 
                                           List<Integer> failedBrokers) 
            throws ExecutionException, InterruptedException {
        logger.info("Handling partition reassignment for {} affected topics", affectedTopics.size());
        
        // Get current cluster state
        Collection<Node> availableBrokers = adminClient.describeCluster().nodes().get();
        Set<Integer> availableBrokerIds = availableBrokers.stream()
            .map(Node::id)
            .filter(id -> !failedBrokers.contains(id))
            .collect(Collectors.toSet());
        
        if (availableBrokerIds.isEmpty()) {
            throw new IllegalStateException("No available brokers for reassignment");
        }
        
        // Process each affected topic
        for (String topic : affectedTopics) {
            // Get topic description to identify partitions
            TopicDescription topicDesc = adminClient.describeTopics(Collections.singletonList(topic))
                .values().get(topic).get();
            
            // Create reassignment plan
            Map<TopicPartition, Optional<NewPartitionReassignment>> reassignments = new HashMap<>();
            
            for (TopicPartitionInfo partitionInfo : topicDesc.partitions()) {
                int partitionId = partitionInfo.partition();
                
                // Check if partition is affected by broker failure
                boolean partitionAffected = partitionInfo.replicas().stream()
                    .anyMatch(node -> failedBrokers.contains(node.id()));
                
                if (partitionAffected) {
                    // Create new assignment based on strategy
                    List<Integer> newAssignment = createNewAssignment(
                        strategy, partitionInfo, availableBrokerIds, failedBrokers);
                    
                    TopicPartition tp = new TopicPartition(topic, partitionId);
                    reassignments.put(tp, Optional.of(new NewPartitionReassignment(newAssignment)));
                    
                    logger.info("Planned reassignment for {}-{}: {}", topic, partitionId, newAssignment);
                }
            }
            
            // Execute the reassignment
            if (!reassignments.isEmpty()) {
                adminClient.alterPartitionReassignments(reassignments).all().get();
                logger.info("Submitted reassignment plan for topic {}", topic);
            }
        }
    }
    
    /**
     * Create a new broker assignment for a partition based on the recovery strategy.
     * 
     * @param strategy The recovery strategy
     * @param partitionInfo Current partition information
     * @param availableBrokerIds Set of available broker IDs
     * @param failedBrokers List of failed broker IDs
     * @return List of broker IDs for new assignment
     */
    private List<Integer> createNewAssignment(RecoveryStrategy strategy, 
                                            TopicPartitionInfo partitionInfo,
                                            Set<Integer> availableBrokerIds,
                                            List<Integer> failedBrokers) {
        // Get current replicas excluding failed brokers
        List<Integer> currentReplicas = partitionInfo.replicas().stream()
            .map(Node::id)
            .filter(id -> !failedBrokers.contains(id))
            .collect(Collectors.toList());
        
        // Choose replacement brokers
        int replicasNeeded = strategy.getMaxReplicasToRestore() - currentReplicas.size();
        replicasNeeded = Math.max(0, replicasNeeded);
        
        // Different reassignment strategies
        List<Integer> newReplicas = new ArrayList<>(currentReplicas);
        List<Integer> candidateBrokers = new ArrayList<>(availableBrokerIds);
        candidateBrokers.removeAll(currentReplicas);
        
        switch (strategy.getPartitionReassignmentStrategy()) {
            case FASTEST_REPLICA_FIRST:
                // In a real implementation, we would use metrics to determine the "fastest" brokers
                // For now, just use the lowest IDs as a proxy
                candidateBrokers.sort(Comparator.naturalOrder());
                break;
                
            case BALANCED:
                // In a real implementation, we would use broker load to balance assignments
                // For now, shuffle to approximate balancing
                Collections.shuffle(candidateBrokers);
                break;
                
            case MINIMAL:
                // Only add the minimum necessary replicas
                replicasNeeded = Math.min(replicasNeeded, 1);
                break;
        }
        
        // Add new brokers up to the required replica count
        for (int i = 0; i < replicasNeeded && i < candidateBrokers.size(); i++) {
            newReplicas.add(candidateBrokers.get(i));
        }
        
        return newReplicas;
    }
    
    /**
     * Configure client-side settings for the affected topics.
     * 
     * @param strategy The recovery strategy
     * @param affectedTopics List of topics affected by the failure
     * @throws ExecutionException If configuration fails
     * @throws InterruptedException If operation is interrupted
     */
    private void configureClientSettings(RecoveryStrategy strategy, List<String> affectedTopics) 
            throws ExecutionException, InterruptedException {
        logger.info("Configuring client settings for {} topics", affectedTopics.size());
        
        // Convert RecoveryStrategy to topic configurations
        Map<String, String> topicConfigs = convertStrategyToTopicConfigs(strategy);
        
        // Apply configurations to each topic
        for (String topic : affectedTopics) {
            ConfigResource resource = new ConfigResource(ConfigResource.Type.TOPIC, topic);
            
            // Create configuration entries
            Collection<ConfigEntry> entries = topicConfigs.entrySet().stream()
                .map(e -> new ConfigEntry(e.getKey(), e.getValue()))
                .collect(Collectors.toList());
            
            Config config = new Config(entries);
            
            // Apply configuration changes
            adminClient.alterConfigs(Collections.singletonMap(resource, config)).all().get();
            logger.info("Applied client configurations to topic {}", topic);
        }
    }
    
    /**
     * Convert recovery strategy to topic configurations.
     * 
     * @param strategy The recovery strategy
     * @return Map of configuration keys and values
     */
    private Map<String, String> convertStrategyToTopicConfigs(RecoveryStrategy strategy) {
        Map<String, String> configs = new HashMap<>();
        
        // Set producer acks based on acknowledgement policy
        switch (strategy.getAcknowledgementPolicy()) {
            case LEADER_ONLY:
                configs.put("producer.acks", "1");
                break;
            case QUORUM:
                configs.put("producer.acks", "-1");
                break;
            case ALL_REPLICAS:
                configs.put("producer.acks", "all");
                break;
        }
        
        // Set consumer configuration based on rebalance strategy
        switch (strategy.getConsumerRebalanceStrategy()) {
            case EAGER:
                configs.put("consumer.partition.assignment.strategy", 
                          "org.apache.kafka.clients.consumer.RoundRobinAssignor");
                break;
            case STICKY:
                configs.put("consumer.partition.assignment.strategy", 
                          "org.apache.kafka.clients.consumer.StickyAssignor");
                break;
            case COOPERATIVE:
                configs.put("consumer.partition.assignment.strategy", 
                          "org.apache.kafka.clients.consumer.CooperativeStickyAssignor");
                break;
            case RANGE:
            default:
                configs.put("consumer.partition.assignment.strategy", 
                          "org.apache.kafka.clients.consumer.RangeAssignor");
                break;
        }
        
        return configs;
    }
    
    /**
     * Perform validation checks on the topics after recovery.
     * 
     * @param topics List of topics to validate
     * @throws ExecutionException If validation fails
     * @throws InterruptedException If operation is interrupted
     */
    private void performValidation(List<String> topics) 
            throws ExecutionException, InterruptedException {
        logger.info("Performing post-recovery validation");
        
        boolean allValid = true;
        
        // Validate topic availability and configuration
        for (String topic : topics) {
            try {
                // Check topic exists
                TopicDescription topicDesc = adminClient.describeTopics(Collections.singletonList(topic))
                    .values().get(topic).get();
                
                // Check partition leader assignment
                for (TopicPartitionInfo partitionInfo : topicDesc.partitions()) {
                    if (partitionInfo.leader() == null) {
                        logger.error("Validation failed: No leader for {}-{}", 
                                   topic, partitionInfo.partition());
                        allValid = false;
                    }
                }
                
                // Check minimum ISR
                ConfigResource resource = new ConfigResource(ConfigResource.Type.TOPIC, topic);
                Config config = adminClient.describeConfigs(Collections.singleton(resource))
                    .values().get(resource).get();
                
                // Get min.insync.replicas config value
                String minIsr = config.entries().stream()
                    .filter(entry -> entry.name().equals("min.insync.replicas"))
                    .map(ConfigEntry::value)
                    .findFirst()
                    .orElse("1");
                
                // Verify each partition has at least minIsr replicas in sync
                for (TopicPartitionInfo partitionInfo : topicDesc.partitions()) {
                    if (partitionInfo.isr().size() < Integer.parseInt(minIsr)) {
                        logger.error("Validation failed: Insufficient ISR for {}-{}, has {} needs {}", 
                                   topic, partitionInfo.partition(), 
                                   partitionInfo.isr().size(), minIsr);
                        allValid = false;
                    }
                }
                
                logger.info("Validation passed for topic {}", topic);
            } catch (Exception e) {
                logger.error("Validation failed for topic {}: {}", topic, e.getMessage());
                allValid = false;
            }
        }
        
        if (!allValid) {
            throw new IllegalStateException("Validation failed for one or more topics");
        }
    }
    
    /**
     * Clean up resources.
     */
    public void close() {
        try {
            if (adminClient != null) {
                adminClient.close();
                logger.info("RecoveryActions closed");
            }
        } catch (Exception e) {
            logger.error("Error closing RecoveryActions", e);
        }
    }
}