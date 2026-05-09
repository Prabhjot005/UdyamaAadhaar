package com.hashkey.validation_service.validation;

import com.hashkey.validation_service.kafka.KafkaMessage;
import org.springframework.stereotype.Service;

@Service
public class EventValidator {

    private final DepartmentRecordValidator departmentRecordValidator;

    public EventValidator(DepartmentRecordValidator departmentRecordValidator) {
        this.departmentRecordValidator = departmentRecordValidator;
    }

    public ValidationResult validateEvent(KafkaMessage message) {
        ValidationResult result = ValidationResult.valid();

        if (message == null) {
            result.addError(InvalidReasonCode.INVALID_MESSAGE, "message", "Event message is null");
            return result;
        }

        if (isBlank(message.getEventType())) {
            result.addError(InvalidReasonCode.MISSING_EVENT_TYPE, "eventType", "Event type is required");
        } else {
            validateEventType(message.getEventType(), result);
        }

        boolean hasGstin = !isBlank(message.getGstin());
        boolean hasPan = !isBlank(resolvePan(message));
        boolean hasUbid = !isBlank(message.getUbid());
        boolean hasDepartmentRecordId = !isBlank(message.getDepartmentRecordId());
        boolean hasSourceOrName = !isBlank(message.getSourceName()) || !isBlank(message.getName());

        if (!hasGstin && !hasPan && !hasUbid && !(hasDepartmentRecordId && hasSourceOrName)) {
            result.addError(
                    InvalidReasonCode.MISSING_EVENT_IDENTITY,
                    "identity",
                    "Event must include GSTIN, PAN, UBID, or departmentRecordId with sourceName or name");
            return result;
        }

        if (hasGstin) {
            departmentRecordValidator.validateGstin(message.getGstin(), result);
        }

        if (hasPan) {
            departmentRecordValidator.validatePanNumber(resolvePan(message), result);
        }

        if (hasUbid) {
            validateUbid(message.getUbid(), result);
        }

        if (hasDepartmentRecordId) {
            departmentRecordValidator.validateDepartmentRecordId(message.getDepartmentRecordId(), result);
        }

        if (!isBlank(message.getName())) {
            departmentRecordValidator.validateName(message.getName(), result);
        }

        return result;
    }

    private String resolvePan(KafkaMessage message) {
        return !isBlank(message.getPan()) ? message.getPan() : message.getPanNumber();
    }

    private void validateEventType(String eventType, ValidationResult result) {
        String value = eventType.trim();

        if (value.length() > 100) {
            result.addError(InvalidReasonCode.INVALID_EVENT_TYPE, "eventType", "Event type must not exceed 100 characters");
        }
    }

    private void validateUbid(String ubid, ValidationResult result) {
        String value = ubid.trim();

        if (value.length() > 64) {
            result.addError(InvalidReasonCode.INVALID_UBID, "ubid", "UBID must not exceed 64 characters");
        }
    }

    private boolean isBlank(String value) {
        return value == null || value.trim().isEmpty();
    }
}
