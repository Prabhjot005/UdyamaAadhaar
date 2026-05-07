package com.hashkey.validation_service.kafka;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Service;

@Service
public class KafkaPublisherService {

    private static final Logger logger = LoggerFactory.getLogger(KafkaPublisherService.class);

    private final KafkaTemplate<String, Object> kafkaTemplate;

    public KafkaPublisherService(KafkaTemplate<String, Object> kafkaTemplate) {
        this.kafkaTemplate = kafkaTemplate;
    }

    public void publish(String topic, Object message) {
        logger.info("Publishing Kafka message to topic {}: {}", topic, message);
        kafkaTemplate.send(topic, message);
    }
}
