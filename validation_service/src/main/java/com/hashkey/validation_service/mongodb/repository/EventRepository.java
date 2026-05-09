package com.hashkey.validation_service.mongodb.repository;

import com.hashkey.validation_service.mongodb.document.ValidEvent;
import org.springframework.data.mongodb.repository.MongoRepository;
import org.springframework.stereotype.Repository;

@Repository
public interface EventRepository extends MongoRepository<ValidEvent, String> {

    boolean existsByEventHash(String eventHash);
}
