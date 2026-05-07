package com.hashkey.validation_service.mongodb.document;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;
import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.mapping.Document;
import org.springframework.data.mongodb.core.mapping.Field;
import java.time.LocalDateTime;
import java.util.Map;

@Document(collection = "valid_department_records")
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class ValidDepartmentRecord {

    @Id
    private String id;

    @Field("department_record_id")
    private String departmentRecordId;

    @Field("name")
    private String name;

    @Field("address")
    private String address;

    @Field("pincode")
    private String pincode;

    @Field("gstin")
    private String gstin;

    @Field("pan_number")
    private String panNumber;

    @Field("department_name")
    private String departmentName;

    @Field("source_name")
    private String sourceName;

    @Field("additional_properties")
    private Map<String, Object> additionalProperties;

    @Field("created_at")
    private LocalDateTime createdAt;

    @Field("updated_at")
    private LocalDateTime updatedAt;

    @Field("kafka_topic")
    private String kafkaTopic;
}
