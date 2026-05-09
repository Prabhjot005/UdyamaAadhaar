package com.hashkey.validation_service.kafka;

import com.hashkey.validation_service.mongodb.document.ValidEvent;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.Map;

@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class ValidatedEventMessage {

    private String eventId;
    private String mongoId;
    private String eventHash;
    private String eventType;
    private String gstin;
    private String pan;
    private String ubid;
    private String departmentRecordId;
    private String sourceName;
    private String name;
    private Map<String, Object> additionalProperties;
    private String createdAt;
    private String updatedAt;
    private String kafkaTopic;

    public static ValidatedEventMessage from(ValidEvent event) {
        return ValidatedEventMessage.builder()
                .eventId(event.getInternalEventId())
                .mongoId(event.getId())
                .eventHash(event.getEventHash())
                .eventType(event.getEventType())
                .gstin(event.getGstin())
                .pan(event.getPan())
                .ubid(event.getUbid())
                .departmentRecordId(event.getDepartmentRecordId())
                .sourceName(event.getSourceName())
                .name(event.getName())
                .additionalProperties(event.getAdditionalProperties())
                .createdAt(event.getCreatedAt() != null ? event.getCreatedAt().toString() : null)
                .updatedAt(event.getUpdatedAt() != null ? event.getUpdatedAt().toString() : null)
                .kafkaTopic(event.getKafkaTopic())
                .build();
    }
}
