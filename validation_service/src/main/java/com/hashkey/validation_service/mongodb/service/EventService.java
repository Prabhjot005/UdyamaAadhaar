package com.hashkey.validation_service.mongodb.service;

import com.hashkey.validation_service.kafka.KafkaMessage;
import com.hashkey.validation_service.mongodb.document.InvalidDepartmentRecordReason;
import com.hashkey.validation_service.mongodb.document.InvalidEvent;
import com.hashkey.validation_service.mongodb.document.ValidEvent;
import com.hashkey.validation_service.mongodb.repository.EventRepository;
import com.hashkey.validation_service.mongodb.repository.InvalidEventRepository;
import com.hashkey.validation_service.validation.ValidationError;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.stream.Collectors;

@Service
public class EventService {

    private static final Logger logger = LoggerFactory.getLogger(EventService.class);

    private final EventRepository eventRepository;
    private final InvalidEventRepository invalidEventRepository;

    public EventService(EventRepository eventRepository, InvalidEventRepository invalidEventRepository) {
        this.eventRepository = eventRepository;
        this.invalidEventRepository = invalidEventRepository;
    }

    public ValidEvent saveValidatedEvent(KafkaMessage kafkaMessage, String topic, String eventHash) {
        try {
            LocalDateTime now = LocalDateTime.now();
            ValidEvent event = ValidEvent.builder()
                    .eventHash(eventHash)
                    .internalEventId(generateInternalEventId())
                    .eventType(kafkaMessage.getEventType())
                    .gstin(kafkaMessage.getGstin())
                    .pan(resolvePan(kafkaMessage))
                    .ubid(kafkaMessage.getUbid())
                    .departmentRecordId(kafkaMessage.getDepartmentRecordId())
                    .sourceName(kafkaMessage.getSourceName())
                    .name(kafkaMessage.getName())
                    .additionalProperties(additionalPropertiesWithEventDetails(kafkaMessage))
                    .createdAt(now)
                    .updatedAt(now)
                    .kafkaTopic(topic)
                    .build();

            ValidEvent savedEvent = eventRepository.save(event);
            logger.info("Successfully saved validated event to MongoDB with ID: {}", savedEvent.getId());
            return savedEvent;
        } catch (Exception e) {
            logger.error("Error saving validated event to MongoDB: {}", kafkaMessage, e);
            throw new RuntimeException("Failed to save event to MongoDB", e);
        }
    }

    public InvalidEvent saveInvalidatedEvent(KafkaMessage kafkaMessage, String topic, String eventHash,
            List<ValidationError> errors) {
        try {
            LocalDateTime now = LocalDateTime.now();
            InvalidEvent event = InvalidEvent.builder()
                    .eventHash(eventHash)
                    .internalEventId(generateInternalEventId())
                    .eventType(kafkaMessage.getEventType())
                    .gstin(kafkaMessage.getGstin())
                    .pan(resolvePan(kafkaMessage))
                    .ubid(kafkaMessage.getUbid())
                    .departmentRecordId(kafkaMessage.getDepartmentRecordId())
                    .sourceName(kafkaMessage.getSourceName())
                    .name(kafkaMessage.getName())
                    .additionalProperties(additionalPropertiesWithEventDetails(kafkaMessage))
                    .invalidReasons(toInvalidReasons(errors))
                    .createdAt(now)
                    .updatedAt(now)
                    .kafkaTopic(topic)
                    .build();

            InvalidEvent savedEvent = invalidEventRepository.save(event);
            logger.info("Successfully saved invalid event to MongoDB DLQ with ID: {}", savedEvent.getId());
            return savedEvent;
        } catch (Exception e) {
            logger.error("Error saving invalid event to MongoDB DLQ: {}", kafkaMessage, e);
            throw new RuntimeException("Failed to save invalid event to MongoDB DLQ", e);
        }
    }

    public boolean existsByEventHash(String eventHash) {
        return eventRepository.existsByEventHash(eventHash)
                || invalidEventRepository.existsByEventHash(eventHash);
    }

    private String resolvePan(KafkaMessage kafkaMessage) {
        if (kafkaMessage.getPan() != null && !kafkaMessage.getPan().trim().isEmpty()) {
            return kafkaMessage.getPan();
        }

        return kafkaMessage.getPanNumber();
    }

    private Map<String, Object> additionalPropertiesWithEventDetails(KafkaMessage kafkaMessage) {
        Map<String, Object> properties = new HashMap<>(kafkaMessage.getAdditionalProperties());
        if (kafkaMessage.getEventTypeDetails() != null && !kafkaMessage.getEventTypeDetails().isEmpty()) {
            properties.put("eventTypeDetails", kafkaMessage.getEventTypeDetails());
        }
        return properties;
    }

    private String generateInternalEventId() {
        return "EVT-" + UUID.randomUUID().toString().replace("-", "").substring(0, 12).toUpperCase();
    }

    private List<InvalidDepartmentRecordReason> toInvalidReasons(List<ValidationError> errors) {
        return errors.stream()
                .map(error -> InvalidDepartmentRecordReason.builder()
                        .code(error.getCode())
                        .field(error.getField())
                        .message(error.getMessage())
                        .build())
                .collect(Collectors.toList());
    }
}
