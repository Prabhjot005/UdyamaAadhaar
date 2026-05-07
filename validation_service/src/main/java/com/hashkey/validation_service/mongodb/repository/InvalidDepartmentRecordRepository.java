package com.hashkey.validation_service.mongodb.repository;

import com.hashkey.validation_service.mongodb.document.InvalidDepartmentRecord;
import org.springframework.data.mongodb.repository.MongoRepository;
import org.springframework.stereotype.Repository;

@Repository
public interface InvalidDepartmentRecordRepository extends MongoRepository<InvalidDepartmentRecord, String> {

    boolean existsByRecordHash(String recordHash);
}
