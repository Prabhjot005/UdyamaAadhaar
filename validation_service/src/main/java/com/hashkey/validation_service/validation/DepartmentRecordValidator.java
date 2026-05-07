package com.hashkey.validation_service.validation;

import com.hashkey.validation_service.kafka.KafkaMessage;
import org.springframework.stereotype.Service;
import java.util.regex.Pattern;

@Service
public class DepartmentRecordValidator {

    // Constants for validation patterns
    private static final Pattern PINCODE_PATTERN = Pattern.compile("^[0-9]{6}$");
    private static final Pattern GSTIN_PATTERN = Pattern
            .compile("^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$");
    private static final Pattern PAN_PATTERN = Pattern.compile("^[A-Z]{5}[0-9]{4}[A-Z]{1}$");
    private static final Pattern NAME_PATTERN = Pattern.compile("^[a-zA-Z\\s'-]{2,100}$");
    private static final Pattern ADDRESS_MIN_LENGTH = Pattern.compile("^.{5,500}$");

    /**
     * Validates a complete department record from Kafka message
     *
     * @param message the KafkaMessage containing department record data
     * @return ValidationResult with validation status and errors
     */
    public ValidationResult validateDepartmentRecord(KafkaMessage message) {
        ValidationResult result = ValidationResult.valid();

        if (message == null) {
            result.addError(InvalidReasonCode.INVALID_MESSAGE, "message", "Department record message is null");
            return result;
        }

        // At least one identity field is required
        validateAtLeastOneIdentityField(message, result);

        // Validate name if provided
        if (message.getName() != null && !message.getName().trim().isEmpty()) {
            validateName(message.getName(), result);
        }

        // Validate address (required field)
        validateAddress(message.getAddress(), result);

        // Validate pincode if provided
        if (message.getPincode() != null && !message.getPincode().trim().isEmpty()) {
            validatePincode(message.getPincode(), result);
        }

        // Validate GSTIN if provided
        if (message.getGstin() != null && !message.getGstin().trim().isEmpty()) {
            validateGstin(message.getGstin(), result);
        }

        // Validate PAN number if provided
        if (message.getPanNumber() != null && !message.getPanNumber().trim().isEmpty()) {
            validatePanNumber(message.getPanNumber(), result);
        }

        // Validate department record ID (required field)
        validateDepartmentRecordId(message.getDepartmentRecordId(), result);

        // Validate department name if provided
        if (message.getDepartmentName() != null && !message.getDepartmentName().trim().isEmpty()) {
            validateDepartmentName(message.getDepartmentName(), result);
        }

        return result;
    }

    /**
     * Validates the name field
     * - Must not be null or empty
     * - Must be between 2-100 characters
     * - Can contain letters, spaces, hyphens, and apostrophes
     *
     * @param name   the name to validate
     * @param result the validation result to add errors to
     */
    public void validateName(String name, ValidationResult result) {
        if (name == null || name.trim().isEmpty()) {
            result.addError(InvalidReasonCode.INVALID_NAME, "name", "Name is required and cannot be empty");
            return;
        }

        if (name.trim().length() < 2) {
            result.addError(InvalidReasonCode.INVALID_NAME, "name", "Name must be at least 2 characters long");
            return;
        }

        if (name.trim().length() > 100) {
            result.addError(InvalidReasonCode.INVALID_NAME, "name", "Name must not exceed 100 characters");
            return;
        }

        if (!NAME_PATTERN.matcher(name.trim()).matches()) {
            result.addError(InvalidReasonCode.INVALID_NAME, "name",
                    "Name contains invalid characters. Only letters, spaces, hyphens, and apostrophes are allowed");
        }
    }

    /**
     * Validates that the record has at least one identity value.
     *
     * @param message the Kafka message to validate
     * @param result  the validation result to add errors to
     */
    public void validateAtLeastOneIdentityField(KafkaMessage message, ValidationResult result) {
        if (isBlank(message.getName()) && isBlank(message.getPanNumber()) && isBlank(message.getGstin())) {
            result.addError(InvalidReasonCode.MISSING_IDENTITY, "identity",
                    "At least one of name, PAN number, or GSTIN is required");
        }
    }

    private boolean isBlank(String value) {
        return value == null || value.trim().isEmpty();
    }

    /**
     * Validates the address field
     * - Must not be null or empty
     * - Must be between 5-500 characters
     *
     * @param address the address to validate
     * @param result  the validation result to add errors to
     */
    public void validateAddress(String address, ValidationResult result) {
        if (address == null || address.trim().isEmpty()) {
            result.addError(InvalidReasonCode.INVALID_ADDRESS, "address", "Address is required and cannot be empty");
            return;
        }

        if (!ADDRESS_MIN_LENGTH.matcher(address.trim()).matches()) {
            result.addError(InvalidReasonCode.INVALID_ADDRESS, "address", "Address contains invalid format");
        }
    }

    /**
     * Validates the pincode field
     * - Must be exactly 6 digits
     * - Valid Indian postal code format
     *
     * @param pincode the pincode to validate
     * @param result  the validation result to add errors to
     */
    public void validatePincode(String pincode, ValidationResult result) {
        if (pincode == null || pincode.trim().isEmpty()) {
            result.addError(InvalidReasonCode.INVALID_PINCODE, "pincode", "Pincode cannot be empty when provided");
            return;
        }

        String pincodeStr = pincode.trim();

        if (!PINCODE_PATTERN.matcher(pincodeStr).matches()) {
            result.addError(InvalidReasonCode.INVALID_PINCODE, "pincode",
                    "Pincode must be exactly 6 digits (valid Indian postal code format)");
        }
    }

    /**
     * Validates the GSTIN field
     * - Must follow GST Identification Number format
     * - Format: 2 digits (state code) + 5 alphabets + 4 digits + 1 letter + 1
     * alphanumeric (not 0) + Z + 1 alphanumeric
     * - Total 15 characters
     *
     * @param gstin  the GSTIN to validate
     * @param result the validation result to add errors to
     */
    public void validateGstin(String gstin, ValidationResult result) {
        if (gstin == null || gstin.trim().isEmpty()) {
            result.addError(InvalidReasonCode.INVALID_GSTIN, "gstin", "GSTIN cannot be empty when provided");
            return;
        }

        String gstinStr = gstin.trim().toUpperCase();

        if (gstinStr.length() != 15) {
            result.addError(InvalidReasonCode.INVALID_GSTIN, "gstin", "GSTIN must be exactly 15 characters long");
            return;
        }

        if (!GSTIN_PATTERN.matcher(gstinStr).matches()) {
            result.addError(InvalidReasonCode.INVALID_GSTIN, "gstin",
                    "GSTIN format is invalid. Expected format: 2 digits + 5 letters + 4 digits + 1 letter + 1 alphanumeric + Z + 1 alphanumeric");
        }
    }

    /**
     * Validates the PAN number field
     * - Must follow PAN (Permanent Account Number) format
     * - Format: 5 alphabets + 4 digits + 1 alphabet
     * - Total 10 characters
     *
     * @param panNumber the PAN number to validate
     * @param result    the validation result to add errors to
     */
    public void validatePanNumber(String panNumber, ValidationResult result) {
        if (panNumber == null || panNumber.trim().isEmpty()) {
            result.addError(InvalidReasonCode.INVALID_PAN_NUMBER, "panNumber",
                    "PAN number cannot be empty when provided");
            return;
        }

        String panStr = panNumber.trim().toUpperCase();

        if (panStr.length() != 10) {
            result.addError(InvalidReasonCode.INVALID_PAN_NUMBER, "panNumber",
                    "PAN number must be exactly 10 characters long");
            return;
        }

        if (!PAN_PATTERN.matcher(panStr).matches()) {
            result.addError(InvalidReasonCode.INVALID_PAN_NUMBER, "panNumber",
                    "PAN format is invalid. Expected format: 5 alphabets + 4 digits + 1 alphabet (e.g., ABCDE1234F)");
        }
    }

    /**
     * Validates the department record ID field
     * - Must not be null or empty
     *
     * @param departmentRecordId the department record ID to validate
     * @param result             the validation result to add errors to
     */
    public void validateDepartmentRecordId(String departmentRecordId, ValidationResult result) {
        if (departmentRecordId == null || departmentRecordId.trim().isEmpty()) {
            result.addError(InvalidReasonCode.INVALID_DEPARTMENT_RECORD_ID, "departmentRecordId",
                    "Department record ID is required and cannot be empty");
        }
    }

    /**
     * Validates the department name field
     * - Must not be null or empty
     * - Must be between 2-100 characters
     *
     * @param departmentName the department name to validate
     * @param result         the validation result to add errors to
     */
    public void validateDepartmentName(String departmentName, ValidationResult result) {
        if (departmentName == null || departmentName.trim().isEmpty()) {
            result.addError(InvalidReasonCode.INVALID_DEPARTMENT_NAME, "departmentName",
                    "Department name cannot be empty when provided");
            return;
        }

        if (departmentName.trim().length() < 2) {
            result.addError(InvalidReasonCode.INVALID_DEPARTMENT_NAME, "departmentName",
                    "Department name must be at least 2 characters long");
            return;
        }

        if (departmentName.trim().length() > 100) {
            result.addError(InvalidReasonCode.INVALID_DEPARTMENT_NAME, "departmentName",
                    "Department name must not exceed 100 characters");
        }
    }
}
