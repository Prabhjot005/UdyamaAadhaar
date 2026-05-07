package com.hashkey.validation_service.kafka;

import com.hashkey.validation_service.validation.DepartmentRecordValidator;
import com.hashkey.validation_service.validation.ValidationResult;
import com.hashkey.validation_service.validation.ValidationException;
import com.hashkey.validation_service.mongodb.document.ValidDepartmentRecord;
import com.hashkey.validation_service.mongodb.service.DepartmentRecordService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.messaging.handler.annotation.Header;
import org.springframework.kafka.support.KafkaHeaders;
import org.springframework.stereotype.Service;

@Service
public class KafkaSubscriberService {

    private static final Logger logger = LoggerFactory.getLogger(KafkaSubscriberService.class);

    @Autowired
    private DepartmentRecordValidator departmentRecordValidator;

    @Autowired
    private DepartmentRecordService departmentRecordService;

    @Autowired
    private KafkaPublisherService kafkaPublisherService;

    @Value("${app.kafka.topic.validDepartmentRecords}")
    private String validDepartmentRecordsTopic;

    @KafkaListener(topics = "${app.kafka.topic}", groupId = "${spring.kafka.consumer.group-id}")
    public void listen(KafkaMessage message, @Header(KafkaHeaders.RECEIVED_TOPIC) String topic) {
        // Handle null messages from deserialization errors
        if (message == null) {
            logger.warn("Received null message from Kafka topic {}. Skipping this record.", topic);
            return;
        }

        try {
            logger.info("Received message from Kafka topic {}: {}", topic, message);
            // TODO: add validation logic for name, address, pincode, city, GSTIN, PAN
            // Number, departmentRecordId
        } catch (Exception e) {
            logger.error("Error processing message from topic {}: {}", topic, message, e);
            // Continue processing instead of crashing
        }
    }

    @KafkaListener(topics = "${app.kafka.topic.departmentRecords}", groupId = "${spring.kafka.consumer.group-id}")
    public void listenDepartmentRecords(KafkaMessage message, @Header(KafkaHeaders.RECEIVED_TOPIC) String topic) {
        if (message == null) {
            logger.warn("Received message from Kafka topic {}. Skipping this null record.", topic);
        } else {
            logger.info("Received message from Kafka topic {}: {}", topic, message);
            processDepartmentRecord(message, topic);
        }
    }

    private void processDepartmentRecord(KafkaMessage message, String topic) {
        // TODO Auto-generated method stub

        try {
            // Validate the department record
            ValidationResult validationResult = departmentRecordValidator.validateDepartmentRecord(message);

            if (!validationResult.isValid()) {
                logger.warn("Department record validation failed: {}", validationResult.getErrors());

                departmentRecordService.saveInvalidatedRecord(message, topic, validationResult.getErrors());
                return ;
                //throw new ValidationException("Department record validation failed", validationResult.getErrors());
            }

            logger.info("Department record validation passed. Saving to MongoDB...");

            ValidDepartmentRecord savedRecord = departmentRecordService.saveValidatedRecord(message, topic);
            logger.info("Department record successfully saved to MongoDB");

            kafkaPublisherService.publish(validDepartmentRecordsTopic,
                    ValidatedDepartmentRecordMessage.from(savedRecord));
            logger.info("Validated department record published to Kafka topic {} with MongoDB ID: {}",
                    validDepartmentRecordsTopic, savedRecord.getId());

        } catch (ValidationException ve) {
            logger.error("Validation error processing department record from topic {}: {}", topic, ve.getMessage());
        } catch (Exception e) {
            logger.error("Error processing department record from topic {}: {}", topic, message, e);
        }

        //throw new UnsupportedOperationException("Unimplemented method 'processDepartmentRecord'");
    }

    @KafkaListener(topics = "${app.kafka.topic.events}", groupId = "${spring.kafka.consumer.group-id}")
    public void listenEvents(KafkaMessage message, @Header(KafkaHeaders.RECEIVED_TOPIC) String topic) {
        if (message == null) {
            logger.warn("Received null message from Kafka topic {}. Skipping this record.", topic);
            return;
        }

        try {
            logger.info("Received event from Kafka topic {}: {}", topic, message);
            // TODO: add validation logic for events
        } catch (Exception e) {
            logger.error("Error processing event from topic {}: {}", topic, message, e);
        }
    }
}
