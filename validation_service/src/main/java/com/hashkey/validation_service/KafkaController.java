package com.hashkey.validation_service;

import com.hashkey.validation_service.kafka.KafkaMessage;
import com.hashkey.validation_service.kafka.KafkaPublisherService;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/kafka")
public class KafkaController {

    private final KafkaPublisherService publisherService;
    @Value("${app.kafka.topic}")
    private String topic;

    public KafkaController(KafkaPublisherService publisherService) {
        this.publisherService = publisherService;
    }

    @PostMapping("/publish")
    public ResponseEntity<String> publishMessage(@RequestBody KafkaMessage message) {
        publisherService.publish(topic, message);
        return ResponseEntity.ok("Message published to Kafka topic");
    }
}
