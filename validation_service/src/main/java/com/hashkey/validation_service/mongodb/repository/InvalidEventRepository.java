package com.hashkey.validation_service.mongodb.repository;

import com.hashkey.validation_service.mongodb.document.InvalidEvent;
import org.springframework.data.mongodb.repository.MongoRepository;
import org.springframework.stereotype.Repository;

@Repository
public interface InvalidEventRepository extends MongoRepository<InvalidEvent, String> {

    boolean existsByEventHash(String eventHash);
}
