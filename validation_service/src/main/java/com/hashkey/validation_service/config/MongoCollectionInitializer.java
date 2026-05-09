package com.hashkey.validation_service.config;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.data.domain.Sort;
import org.springframework.data.mongodb.core.MongoTemplate;
import org.springframework.data.mongodb.core.index.Index;
import org.springframework.stereotype.Component;

@Component
public class MongoCollectionInitializer implements ApplicationRunner {

    private static final Logger logger = LoggerFactory.getLogger(MongoCollectionInitializer.class);

    private final MongoTemplate mongoTemplate;

    public MongoCollectionInitializer(MongoTemplate mongoTemplate) {
        this.mongoTemplate = mongoTemplate;
    }

    @Override
    public void run(ApplicationArguments args) {
        ensureCollection("dlq_department_records");
        ensureCollection("unvalidated_department_data");
        ensureCollection("valid_department_records");
        ensureCollection("valid_events");
        ensureCollection("dlq_events");

        ensureUniqueSparseIndex("dlq_department_records", "record_hash");
        ensureUniqueSparseIndex("valid_department_records", "record_hash");
        ensureUniqueSparseIndex("dlq_events", "event_hash");
        ensureUniqueSparseIndex("valid_events", "event_hash");
        ensureUniqueSparseIndex("dlq_events", "internal_event_id");
        ensureUniqueSparseIndex("valid_events", "internal_event_id");
    }

    private void ensureCollection(String collectionName) {
        if (!mongoTemplate.collectionExists(collectionName)) {
            mongoTemplate.createCollection(collectionName);
            logger.info("Created MongoDB collection: {}", collectionName);
            return;
        }

        logger.info("MongoDB collection already exists: {}", collectionName);
    }

    private void ensureUniqueSparseIndex(String collectionName, String fieldName) {
        mongoTemplate.indexOps(collectionName).ensureIndex(
                new Index()
                        .on(fieldName, Sort.Direction.ASC)
                        .unique()
                        .sparse()
                        .named("idx_" + collectionName + "_" + fieldName + "_unique"));
        logger.info("Ensured MongoDB index on {}.{}", collectionName, fieldName);
    }
}
