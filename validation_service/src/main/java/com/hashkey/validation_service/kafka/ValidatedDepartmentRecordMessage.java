package com.hashkey.validation_service.kafka;

import com.hashkey.validation_service.mongodb.document.ValidDepartmentRecord;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;
import java.util.Map;

@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class ValidatedDepartmentRecordMessage {

    private String dataRecordId;
    private String recordHash;
    private String departmentRecordId;
    private String name;
    private String address;
    private String pincode;
    private String gstin;
    private String panNumber;
    private String departmentName;
    private String sourceName;
    private Map<String, Object> additionalProperties;
    private String createdAt;
    private String updatedAt;
    private String kafkaTopic;

    public static ValidatedDepartmentRecordMessage from(ValidDepartmentRecord record) {
        return ValidatedDepartmentRecordMessage.builder()
                .dataRecordId(record.getId())
                .recordHash(record.getRecordHash())
                .departmentRecordId(record.getDepartmentRecordId())
                .name(record.getName())
                .address(record.getAddress())
                .pincode(record.getPincode())
                .gstin(record.getGstin())
                .panNumber(record.getPanNumber())
                .departmentName(record.getDepartmentName())
                .sourceName(record.getSourceName())
                .additionalProperties(record.getAdditionalProperties())
                .createdAt(record.getCreatedAt() != null ? record.getCreatedAt().toString() : null)
                .updatedAt(record.getUpdatedAt() != null ? record.getUpdatedAt().toString() : null)
                .kafkaTopic(record.getKafkaTopic())
                .build();
    }
}
