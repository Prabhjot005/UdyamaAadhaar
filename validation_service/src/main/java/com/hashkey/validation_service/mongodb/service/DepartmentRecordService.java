package com.hashkey.validation_service.mongodb.service;

import com.hashkey.validation_service.kafka.KafkaMessage;
import com.hashkey.validation_service.mongodb.document.InvalidDepartmentRecord;
import com.hashkey.validation_service.mongodb.document.InvalidDepartmentRecordReason;
import com.hashkey.validation_service.mongodb.document.ValidDepartmentRecord;
import com.hashkey.validation_service.mongodb.repository.DepartmentRecordRepository;
import com.hashkey.validation_service.mongodb.repository.InvalidDepartmentRecordRepository;
import com.hashkey.validation_service.validation.ValidationError;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;
import java.util.stream.Collectors;

@Service
public class DepartmentRecordService {

    private static final Logger logger = LoggerFactory.getLogger(DepartmentRecordService.class);

    @Autowired
    private DepartmentRecordRepository departmentRecordRepository;

    @Autowired
    private InvalidDepartmentRecordRepository invalidDepartmentRecordRepository;

    /**
     * Save a validated department record to MongoDB
     *
     * @param kafkaMessage the Kafka message containing department record data
     * @param topic        the Kafka topic from which the message was received
     * @param recordHash   deterministic hash of the incoming department record
     * @return saved ValidDepartmentRecord
     */
    public ValidDepartmentRecord saveValidatedRecord(KafkaMessage kafkaMessage, String topic, String recordHash) {
        try {
            ValidDepartmentRecord record = ValidDepartmentRecord.builder()
                    .recordHash(recordHash)
                    .departmentRecordId(kafkaMessage.getDepartmentRecordId())
                    .name(kafkaMessage.getName())
                    .address(kafkaMessage.getAddress())
                    .pincode(kafkaMessage.getPincode())
                    .gstin(kafkaMessage.getGstin())
                    .panNumber(kafkaMessage.getPanNumber())
                    .departmentName(kafkaMessage.getDepartmentName())
                    .sourceName(kafkaMessage.getSourceName())
                    .additionalProperties(kafkaMessage.getAdditionalProperties())
                    .createdAt(LocalDateTime.now())
                    .updatedAt(LocalDateTime.now())
                    .kafkaTopic(topic)
                    .build();

            ValidDepartmentRecord savedRecord = departmentRecordRepository.save(record);
            logger.info("Successfully saved validated department record to MongoDB with ID: {}", savedRecord.getId());
            return savedRecord;

        } catch (Exception e) {
            logger.error("Error saving validated department record to MongoDB: {}", kafkaMessage, e);
            throw new RuntimeException("Failed to save department record to MongoDB", e);
        }
    }

    /**
     * Save an invalid department record to MongoDB DLQ collection
     *
     * @param kafkaMessage the Kafka message containing department record data
     * @param topic        the Kafka topic from which the message was received
     * @param recordHash   deterministic hash of the incoming department record
     * @param errors       validation errors explaining why the record is invalid
     * @return saved InvalidDepartmentRecord
     */
    public InvalidDepartmentRecord saveInvalidatedRecord(KafkaMessage kafkaMessage, String topic, String recordHash,
            List<ValidationError> errors) {
        try {
            LocalDateTime now = LocalDateTime.now();
            InvalidDepartmentRecord record = InvalidDepartmentRecord.builder()
                    .recordHash(recordHash)
                    .departmentRecordId(kafkaMessage.getDepartmentRecordId())
                    .name(kafkaMessage.getName())
                    .address(kafkaMessage.getAddress())
                    .pincode(kafkaMessage.getPincode())
                    .gstin(kafkaMessage.getGstin())
                    .panNumber(kafkaMessage.getPanNumber())
                    .departmentName(kafkaMessage.getDepartmentName())
                    .sourceName(kafkaMessage.getSourceName())
                    .additionalProperties(kafkaMessage.getAdditionalProperties())
                    .invalidReasons(toInvalidReasons(errors))
                    .createdAt(now)
                    .updatedAt(now)
                    .kafkaTopic(topic)
                    .build();

            InvalidDepartmentRecord savedRecord = invalidDepartmentRecordRepository.save(record);
            logger.info("Successfully saved invalid department record to MongoDB DLQ with ID: {}", savedRecord.getId());
            return savedRecord;

        } catch (Exception e) {
            logger.error("Error saving invalid department record to MongoDB DLQ: {}", kafkaMessage, e);
            throw new RuntimeException("Failed to save invalid department record to MongoDB DLQ", e);
        }
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

    public boolean existsByRecordHash(String recordHash) {
        return departmentRecordRepository.existsByRecordHash(recordHash)
                || invalidDepartmentRecordRepository.existsByRecordHash(recordHash);
    }

    /**
     * Find department record by ID
     */
    public Optional<ValidDepartmentRecord> findById(String id) {
        return departmentRecordRepository.findById(id);
    }

    /**
     * Find department record by departmentRecordId
     */
    public Optional<ValidDepartmentRecord> findByDepartmentRecordId(String departmentRecordId) {
        return departmentRecordRepository.findByDepartmentRecordId(departmentRecordId);
    }

    /**
     * Find all valid records
     */
    public List<ValidDepartmentRecord> findAllValidRecords() {
        return departmentRecordRepository.findAll();
    }

    /**
     * Find records by department name
     */
    public List<ValidDepartmentRecord> findByDepartmentName(String departmentName) {
        return departmentRecordRepository.findByDepartmentName(departmentName);
    }

    /**
     * Find records by source name
     */
    public List<ValidDepartmentRecord> findBySourceName(String sourceName) {
        return departmentRecordRepository.findBySourceName(sourceName);
    }

    /**
     * Find record by GSTIN
     */
    public Optional<ValidDepartmentRecord> findByGstin(String gstin) {
        return departmentRecordRepository.findByGstin(gstin);
    }

    /**
     * Find record by PAN
     */
    public Optional<ValidDepartmentRecord> findByPanNumber(String panNumber) {
        return departmentRecordRepository.findByPanNumber(panNumber);
    }

    /**
     * Get all department records
     */
    public List<ValidDepartmentRecord> findAll() {
        return departmentRecordRepository.findAll();
    }

    /**
     * Delete a record by ID
     */
    public void deleteById(String id) {
        departmentRecordRepository.deleteById(id);
        logger.info("Successfully deleted department record with ID: {}", id);
    }

    /**
     * Count total records
     */
    public long countTotalRecords() {
        return departmentRecordRepository.count() + invalidDepartmentRecordRepository.count();
    }

    /**
     * Count valid records
     */
    public long countValidRecords() {
        return departmentRecordRepository.count();
    }

    /**
     * Count invalid records
     */
    public long countInvalidRecords() {
        return invalidDepartmentRecordRepository.count();
    }
}
