package com.hashkey.validation_service.mongodb.document;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;
import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.index.Indexed;
import org.springframework.data.mongodb.core.mapping.Document;
import org.springframework.data.mongodb.core.mapping.Field;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

@Document(collection = "dlq_events")
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class InvalidEvent {

    @Id
    private String id;

    @Indexed(unique = true, sparse = true)
    @Field("event_hash")
    private String eventHash;

    @Indexed(unique = true, sparse = true)
    @Field("internal_event_id")
    private String internalEventId;

    @Field("event_type")
    private String eventType;

    @Field("gstin")
    private String gstin;

    @Field("pan")
    private String pan;

    @Field("ubid")
    private String ubid;

    @Field("department_record_id")
    private String departmentRecordId;

    @Field("source_name")
    private String sourceName;

    @Field("name")
    private String name;

    @Field("additional_properties")
    private Map<String, Object> additionalProperties;

    @Field("invalid_reasons")
    private List<InvalidDepartmentRecordReason> invalidReasons;

    @Field("created_at")
    private LocalDateTime createdAt;

    @Field("updated_at")
    private LocalDateTime updatedAt;

    @Field("kafka_topic")
    private String kafkaTopic;
}
