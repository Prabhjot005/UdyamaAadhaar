package com.hashkey.validation_service.kafka;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonAnyGetter;
import com.fasterxml.jackson.annotation.JsonAnySetter;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;
import java.util.HashMap;
import java.util.Map;

@Data
@NoArgsConstructor
@AllArgsConstructor
@JsonIgnoreProperties(ignoreUnknown = false)
public class KafkaMessage {

    private String name;
    private String address;
    private String pincode;
    private String gstin;
    private String panNumber;
    private String departmentRecordId;
    private String departmentName;
    private String sourceName;
    private Map<String, Object> additionalProperties = new HashMap<>();

    @JsonAnySetter
    public void addAdditionalProperty(String key, Object value) {
        additionalProperties.put(key, value);
    }

    @JsonAnyGetter
    public Map<String, Object> getAdditionalProperties() {
        return additionalProperties;
    }
}
