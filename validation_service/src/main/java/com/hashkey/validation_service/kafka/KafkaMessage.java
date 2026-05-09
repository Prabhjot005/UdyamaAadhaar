package com.hashkey.validation_service.kafka;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonAnyGetter;
import com.fasterxml.jackson.annotation.JsonAnySetter;
import com.fasterxml.jackson.annotation.JsonProperty;
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
    private String pan;
    private String panNumber;
    private String ubid;
    private String eventType;
    private Map<String, Object> eventTypeDetails = new HashMap<>();
    private String departmentRecordId;
    private String departmentName;
    private String sourceName;
    private Map<String, Object> additionalProperties = new HashMap<>();

    @JsonProperty("eventType")
    @SuppressWarnings("unchecked")
    public void setEventType(Object value) {
        if (value instanceof Map<?, ?> eventTypeMap) {
            eventTypeDetails = (Map<String, Object>) eventTypeMap;
            Object code = eventTypeMap.get("code");
            if (code == null) {
                code = eventTypeMap.get("eventCode");
            }
            if (code == null) {
                code = eventTypeMap.get("name");
            }
            eventType = code != null ? String.valueOf(code) : null;
            return;
        }

        eventType = value != null ? String.valueOf(value) : null;
        eventTypeDetails = new HashMap<>();
    }

    @JsonAnySetter
    public void addAdditionalProperty(String key, Object value) {
        additionalProperties.put(key, value);
    }

    @JsonAnyGetter
    public Map<String, Object> getAdditionalProperties() {
        return additionalProperties;
    }
}
