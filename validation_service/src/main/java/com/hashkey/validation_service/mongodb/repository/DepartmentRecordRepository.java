package com.hashkey.validation_service.mongodb.repository;

import com.hashkey.validation_service.mongodb.document.ValidDepartmentRecord;
import org.springframework.data.mongodb.repository.MongoRepository;
import org.springframework.stereotype.Repository;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;

@Repository
public interface DepartmentRecordRepository extends MongoRepository<ValidDepartmentRecord, String> {

    boolean existsByRecordHash(String recordHash);

    /**
     * Find department record by departmentRecordId
     */
    Optional<ValidDepartmentRecord> findByDepartmentRecordId(String departmentRecordId);

    /**
     * Find all records created between two timestamps
     */
    List<ValidDepartmentRecord> findByCreatedAtBetween(LocalDateTime startDate, LocalDateTime endDate);

    /**
     * Find records by department name
     */
    List<ValidDepartmentRecord> findByDepartmentName(String departmentName);

    /**
     * Find records by source name
     */
    List<ValidDepartmentRecord> findBySourceName(String sourceName);

    /**
     * Find records by GSTIN
     */
    Optional<ValidDepartmentRecord> findByGstin(String gstin);

    /**
     * Find records by PAN
     */
    Optional<ValidDepartmentRecord> findByPanNumber(String panNumber);

    /**
     * Find records created after a specific date
     */
    List<ValidDepartmentRecord> findByCreatedAtAfter(LocalDateTime createdAt);
}
