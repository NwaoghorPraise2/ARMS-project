package org.arms.orchestrator;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.apache.kafka.clients.admin.AdminClient;
import org.apache.kafka.clients.admin.AdminClientConfig;
import org.apache.kafka.clients.admin.DescribeClusterResult;
import org.apache.kafka.clients.producer.KafkaProducer;
import org.apache.kafka.clients.producer.Producer;
import org.apache.kafka.clients.producer.ProducerConfig;
import org.apache.kafka.clients.producer.ProducerRecord;
import org.apache.kafka.common.Node;
import org.apache.kafka.common.serialization.StringSerializer;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.*;
import java.util.concurrent.ExecutionException;

/**
 * Injects controlled faults into the Kafka cluster for testing recovery.
 */
public class FaultInjector implements AutoCloseable {
    private static final Logger logger = LoggerFactory.getLogger(FaultInjector.class);
    private static final String FAILURE_EVENTS_TOPIC = "arms-failure-events";
    
    private final String bootstrapServers;
    private final AdminClient adminClient;
    private final Producer<String, String> producer;
    private final ObjectMapper objectMapper;
    private final Random random;
    
    /**
     * Initialize the fault injector.
     * 
     * @param bootstrapServers Kafka bootstrap servers
     */
    public FaultInjector(String bootstrapServers) {
        this.bootstrapServers = bootstrapServers;
        this.objectMapper = new ObjectMapper();
        this.random = new Random();
        
        // Set up AdminClient for cluster management
        Properties adminProps = new Properties();
        adminProps.put(AdminClientConfig.BOOTSTRAP_SERVERS_CONFIG, bootstrapServers);
        this.adminClient = AdminClient.create(adminProps);
        
        // Set up Kafka producer for failure events
        Properties producerProps = new Properties();
        producerProps.put(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG, bootstrapServers);
        producerProps.put(ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG, StringSerializer.class.getName());
        producerProps.put(ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG, StringSerializer.class.getName());
        this.producer = new KafkaProducer<>(producerProps);
        
        logger.info("Fault injector initialized with bootstrap servers: {}", bootstrapServers);
    }
    
    /**
     * Inject a single broker failure.
     * 
     * @return ID of the recovery operation
     * @throws ExecutionException If operation fails
     * @throws InterruptedException If operation is interrupted
     */
    public String injectSingleBrokerFailure() throws ExecutionException, InterruptedException {
        // Get cluster information
        DescribeClusterResult clusterInfo = adminClient.describeCluster();
        Collection<Node> nodes = clusterInfo.nodes().get();
        
        if (nodes.size() <= 1) {
            throw new IllegalStateException("Cluster has too few nodes for failure injection");
        }
        
        // Select a random broker to fail
        List<Node> nodeList = new ArrayList<>(nodes);
        Node targetNode = nodeList.get(random.nextInt(nodeList.size()));
        
        logger.info("Injecting failure for broker {}", targetNode.id());
        
        // Get affected topics
        List<String> affectedTopics = getAffectedTopics(Collections.singletonList(targetNode.id()));
        
        // Create and publish failure event
        String recoveryId = "recovery-" + UUID.randomUUID().toString();
        Map<String, Object> failureEvent = new HashMap<>();
        failureEvent.put("recovery_id", recoveryId);
        failureEvent.put("failure_scenario", "single_broker");
        failureEvent.put("failed_brokers", Collections.singletonList(targetNode.id()));
        failureEvent.put("affected_topics", affectedTopics);
        failureEvent.put("timestamp", System.currentTimeMillis());
        
        // In a real implementation, we would actually stop the broker here
        // For this demo, we'll just simulate the failure by publishing the event
        
        publishFailureEvent(recoveryId, failureEvent);
        
        return recoveryId;
    }
    
    /**
     * Inject multiple broker failures.
     * 
     * @param count Number of brokers to fail (default 2)
     * @return ID of the recovery operation
     * @throws ExecutionException If operation fails
     * @throws InterruptedException If operation is interrupted
     */
    public String injectMultipleBrokerFailure(int count) throws ExecutionException, InterruptedException {
        if (count <= 0) {
            count = 2; // Default to 2 brokers
        }
        
        // Get cluster information
        DescribeClusterResult clusterInfo = adminClient.describeCluster();
        Collection<Node> nodes = clusterInfo.nodes().get();
        
        if (nodes.size() <= count) {
            throw new IllegalStateException("Cluster has too few nodes for multiple failure injection");
        }
        
        // Select random brokers to fail
        List<Node> nodeList = new ArrayList<>(nodes);
        Collections.shuffle(nodeList);
        List<Node> targetsNodes = nodeList.subList(0, Math.min(count, nodeList.size()));
        
        List<Integer> failedBrokerIds = new ArrayList<>();
        for (Node node : targetsNodes) {
            failedBrokerIds.add(node.id());
        }
        
        logger.info("Injecting failures for brokers {}", failedBrokerIds);
        
        // Get affected topics
        List<String> affectedTopics = getAffectedTopics(failedBrokerIds);
        
        // Create and publish failure event
        String recoveryId = "recovery-" + UUID.randomUUID().toString();
        Map<String, Object> failureEvent = new HashMap<>();
        failureEvent.put("recovery_id", recoveryId);
        failureEvent.put("failure_scenario", "multiple_broker");
        failureEvent.put("failed_brokers", failedBrokerIds);
        failureEvent.put("affected_topics", affectedTopics);
        failureEvent.put("timestamp", System.currentTimeMillis());
        
        // In a real implementation, we would actually stop the brokers here
        // For this demo, we'll just simulate the failure by publishing the event
        
        publishFailureEvent(recoveryId, failureEvent);
        
        return recoveryId;
    }
    
    /**
     * Get topics affected by broker failures.
     * 
     * @param failedBrokerIds List of failed broker IDs
     * @return List of affected topic names
     */
    private List<String> getAffectedTopics(List<Integer> failedBrokerIds) throws ExecutionException, InterruptedException {
        Set<String> affectedTopics = new HashSet<>();
        
        // Get all topics
        Set<String> allTopics = adminClient.listTopics().names().get();
        
        // For each topic, check if it's affected by failed brokers
        for (String topic : allTopics) {
            // Skip internal topics
            if (topic.startsWith("__") || topic.startsWith("arms-")) {
                continue;
            }
            
            // Get topic description to identify affected partitions
            adminClient.describeTopics(Collections.singleton(topic)).values().get(topic).get()
                .partitions().forEach(partitionInfo -> {
                    // Check if partition is affected by broker failure
                    boolean affected = partitionInfo.replicas().stream()
                        .anyMatch(node -> failedBrokerIds.contains(node.id()));
                    
                    if (affected) {
                        affectedTopics.add(topic);
                    }
                });
        }
        
        return new ArrayList<>(affectedTopics);
    }
    
    /**
     * Publish a failure event to Kafka.
     * 
     * @param recoveryId ID of the recovery operation
     * @param failureEvent Failure event data
     */
    private void publishFailureEvent(String recoveryId, Map<String, Object> failureEvent) {
        try {
            String eventJson = objectMapper.writeValueAsString(failureEvent);
            ProducerRecord<String, String> record = new ProducerRecord<>(
                FAILURE_EVENTS_TOPIC, recoveryId, eventJson);
            
            producer.send(record, (metadata, exception) -> {
                if (exception != null) {
                    logger.error("Error publishing failure event: {}", exception.getMessage(), exception);
                } else {
                    logger.info("Published failure event for recovery {}", recoveryId);
                }
            });
            
            // Ensure the message is sent
            producer.flush();
        } catch (Exception e) {
            logger.error("Error serializing failure event: {}", e.getMessage(), e);
        }
    }
    
    @Override
    public void close() {
        try {
            // Close resources
            if (adminClient != null) {
                adminClient.close();
            }
            
            if (producer != null) {
                producer.close();
            }
            
            logger.info("Fault injector closed");
        } catch (Exception e) {
            logger.error("Error closing fault injector", e);
        }
    }
    
    /**
     * Main method to run the fault injector as a standalone service.
     */
    public static void main(String[] args) {
        String bootstrapServers = "kafka-1:9092,kafka-2:9092,kafka-3:9092";
        String failureType = "single"; // Default to single broker failure
        
        // Parse command line arguments
        for (int i = 0; i < args.length; i++) {
            if ("--bootstrap-servers".equals(args[i]) && i < args.length - 1) {
                bootstrapServers = args[i + 1];
                i++;
            } else if ("--failure-type".equals(args[i]) && i < args.length - 1) {
                failureType = args[i + 1];
                i++;
            }
        }
        
        try (FaultInjector injector = new FaultInjector(bootstrapServers)) {
            String recoveryId;
            
            // Inject failure based on type
            if ("multiple".equalsIgnoreCase(failureType)) {
                recoveryId = injector.injectMultipleBrokerFailure(2);
            } else {
                recoveryId = injector.injectSingleBrokerFailure();
            }
            
            logger.info("Injected {} broker failure, recovery ID: {}", 
                      failureType, recoveryId);
        } catch (Exception e) {
            logger.error("Error injecting failure: {}", e.getMessage(), e);
            System.exit(1);
        }
    }
}