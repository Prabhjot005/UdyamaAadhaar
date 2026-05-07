# Department Record Validation Service

## Overview
The Department Record Validation Service is a comprehensive validation module designed to validate all fields in department records coming through Kafka messages. It provides robust field-level validation for critical data fields including PINCODE, GSTIN, PAN number, name, and address.

## Components

### 1. DepartmentRecordValidator (Main Service)
Located at: `com.hashkey.validation_service.validation.DepartmentRecordValidator`

**Purpose:** Core validation service with methods to validate individual fields and complete department records.

**Key Methods:**
- `validateDepartmentRecord(KafkaMessage)` - Validates the entire department record
- `validateName(String, ValidationResult)` - Validates name field
- `validateAddress(String, ValidationResult)` - Validates address field
- `validatePincode(String, ValidationResult)` - Validates Indian postal code (6 digits)
- `validateGstin(String, ValidationResult)` - Validates GST Identification Number (15 characters)
- `validatePanNumber(String, ValidationResult)` - Validates Permanent Account Number (10 characters)
- `validateDepartmentRecordId(String, ValidationResult)` - Validates department record ID
- `validateDepartmentName(String, ValidationResult)` - Validates department name

### 2. ValidationResult
Located at: `com.hashkey.validation_service.validation.ValidationResult`

**Purpose:** Container for validation results and errors.

**Features:**
- Stores validation status (valid/invalid)
- Maintains list of validation errors
- Helper methods: `valid()`, `invalid()`, `addError()`, `isValid()`

### 3. ValidationError
Located at: `com.hashkey.validation_service.validation.ValidationError`

**Purpose:** Represents a single validation error.

**Fields:**
- `field` - Name of the field that failed validation
- `message` - Description of the validation failure

### 4. ValidationException
Located at: `com.hashkey.validation_service.validation.ValidationException`

**Purpose:** Custom exception for validation failures.

**Features:**
- Contains list of validation errors
- Used for error handling and propagation

## Validation Rules

### Name Field
- **Required:** Yes
- **Min Length:** 2 characters
- **Max Length:** 100 characters
- **Allowed Characters:** Letters, spaces, hyphens, apostrophes
- **Example:** "John Doe", "Mary O'Connor", "Jean-Pierre"

### Address Field
- **Required:** Yes
- **Min Length:** 5 characters
- **Max Length:** 500 characters
- **Format:** Accepts any printable characters
- **Example:** "123 Main Street, New York, NY 10001"

### Pincode Field
- **Required:** No (optional)
- **Format:** Exactly 6 digits (Indian postal code format)
- **Regex:** `^[0-9]{6}$`
- **Example:** "110001", "400001"

### GSTIN Field
- **Required:** No (optional)
- **Length:** Exactly 15 characters
- **Format:** 
  - 2 digits (state code)
  - 5 alphabets (PAN number part)
  - 4 digits (sequence number)
  - 1 letter (check digit)
  - 1 alphanumeric (not 0) (entity type)
  - Z (constant)
  - 1 alphanumeric (check digit)
- **Regex:** `^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$`
- **Example:** "27AAPDU0055K1ZO"

### PAN Number Field
- **Required:** No (optional)
- **Length:** Exactly 10 characters
- **Format:**
  - 5 alphabets (permanent account number part)
  - 4 digits (sequence number)
  - 1 alphabet (check digit)
- **Regex:** `^[A-Z]{5}[0-9]{4}[A-Z]{1}$`
- **Example:** "ABCDE1234F"

### Department Record ID
- **Required:** Yes
- **Constraints:** Cannot be null or empty

### Department Name
- **Required:** No (optional when provided)
- **Min Length:** 2 characters
- **Max Length:** 100 characters

## Integration with Kafka Subscriber

The `listenDepartmentRecords` method in `KafkaSubscriberService` now:

1. Receives Kafka messages from `departmentRecords` topic
2. Calls `validateDepartmentRecord()` to validate all fields
3. If validation passes:
   - Logs success
   - Processes the record (ready for database insertion, etc.)
4. If validation fails:
   - Logs detailed error information
   - Throws `ValidationException` with error details
   - Errors can be handled and logged to a Dead Letter Queue (DLQ)

## Usage Example

```java
@Service
public class MyService {
    
    @Autowired
    private DepartmentRecordValidator validator;
    
    public void processDepartmentRecord(KafkaMessage message) {
        ValidationResult result = validator.validateDepartmentRecord(message);
        
        if (result.isValid()) {
            // Process the valid record
            saveToDatabase(message);
        } else {
            // Handle validation errors
            for (ValidationError error : result.getErrors()) {
                logger.error("Field: {}, Error: {}", error.getField(), error.getMessage());
            }
        }
    }
}
```

## Testing

Comprehensive unit tests are provided in `DepartmentRecordValidatorTest.java`:

- Tests for valid complete records
- Tests for null/empty field handling
- Tests for format validation (PINCODE, GSTIN, PAN)
- Tests for length constraints
- Tests for character validation
- Tests for optional vs required fields

**Run tests:**
```bash
mvn test -Dtest=DepartmentRecordValidatorTest
```

## Error Handling

The validation service handles errors gracefully:

1. **Null Messages:** Logged with warning, skipped
2. **Validation Failures:** Detailed error messages with field names
3. **Processing Errors:** Logged without crashing the service
4. **Future Enhancement:** Errors can be sent to DLQ for manual review

## Future Enhancements

1. Add validation for additional fields (city, state, etc.)
2. Add database lookup validation (e.g., verify department exists)
3. Add cross-field validation logic
4. Implement Dead Letter Queue (DLQ) for failed validations
5. Add metrics/monitoring for validation success/failure rates
6. Support for custom validation rules

## Configuration

The validation service uses environment variables from `application.properties`:

```properties
app.kafka.topic.departmentRecords=department-records
spring.kafka.consumer.group-id=validation-service-group
```

## Dependencies

- Spring Boot
- Spring Kafka
- Lombok
- JUnit 5 (for testing)
