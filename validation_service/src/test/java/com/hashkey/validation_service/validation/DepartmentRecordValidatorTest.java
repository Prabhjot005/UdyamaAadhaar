package com.hashkey.validation_service.validation;

import com.hashkey.validation_service.kafka.KafkaMessage;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.DisplayName;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import static org.junit.jupiter.api.Assertions.*;

@SpringBootTest
@DisplayName("Department Record Validator Tests")
public class DepartmentRecordValidatorTest {

    @Autowired
    private DepartmentRecordValidator validator;

    private KafkaMessage validMessage;

    @BeforeEach
    public void setUp() {
        validMessage = new KafkaMessage();
        validMessage.setName("John Doe");
        validMessage.setAddress("123 Main Street, New York, NY 10001");
        validMessage.setPincode("100001");
        validMessage.setGstin("27AAPDU0055K1ZO");
        validMessage.setPanNumber("ABCDE1234F");
        validMessage.setDepartmentRecordId("DEPT123");
        validMessage.setDepartmentName("Finance Department");
    }

    @Test
    @DisplayName("Should validate a complete and valid department record")
    public void testValidateDepartmentRecord_ValidRecord() {
        ValidationResult result = validator.validateDepartmentRecord(validMessage);
        assertTrue(result.isValid(), "Valid record should pass validation");
    }

    @Test
    @DisplayName("Should fail when message is null")
    public void testValidateDepartmentRecord_NullMessage() {
        ValidationResult result = validator.validateDepartmentRecord(null);
        assertFalse(result.isValid());
        assertTrue(result.getErrors().stream()
                .anyMatch(e -> e.getField().equals("message")));
    }

    @Test
    @DisplayName("Should validate name - empty name is allowed")
    public void testValidateName_Empty() {
        ValidationResult result = ValidationResult.valid();
        validator.validateName("", result);
        assertTrue(result.isValid());
    }

    @Test
    @DisplayName("Should validate name - null name is allowed")
    public void testValidateName_Null() {
        ValidationResult result = ValidationResult.valid();
        validator.validateName(null, result);
        assertTrue(result.isValid());
    }

    @Test
    @DisplayName("Should validate name - too short")
    public void testValidateName_TooShort() {
        ValidationResult result = ValidationResult.valid();
        validator.validateName("A", result);
        assertFalse(result.isValid());
        assertTrue(result.getErrors().stream()
                .anyMatch(e -> e.getMessage().contains("at least 2 characters")));
    }

    @Test
    @DisplayName("Should validate name - too long")
    public void testValidateName_TooLong() {
        ValidationResult result = ValidationResult.valid();
        String longName = "A".repeat(101);
        validator.validateName(longName, result);
        assertFalse(result.isValid());
        assertTrue(result.getErrors().stream()
                .anyMatch(e -> e.getMessage().contains("not exceed 100 characters")));
    }

    @Test
    @DisplayName("Should validate name - invalid characters")
    public void testValidateName_InvalidCharacters() {
        ValidationResult result = ValidationResult.valid();
        validator.validateName("John@123", result);
        assertFalse(result.isValid());
        assertTrue(result.getErrors().stream()
                .anyMatch(e -> e.getMessage().contains("invalid characters")));
    }

    @Test
    @DisplayName("Should validate name - valid names")
    public void testValidateName_ValidNames() {
        ValidationResult result = ValidationResult.valid();
        validator.validateName("John Doe", result);
        assertTrue(result.isValid());

        result = ValidationResult.valid();
        validator.validateName("Mary O'Connor", result);
        assertTrue(result.isValid());

        result = ValidationResult.valid();
        validator.validateName("Jean-Pierre", result);
        assertTrue(result.isValid());
    }

    @Test
    @DisplayName("Should validate address - empty address is allowed")
    public void testValidateAddress_Empty() {
        ValidationResult result = ValidationResult.valid();
        validator.validateAddress("", result);
        assertTrue(result.isValid());
    }

    @Test
    @DisplayName("Should validate address - too short")
    public void testValidateAddress_TooShort() {
        ValidationResult result = ValidationResult.valid();
        validator.validateAddress("123", result);
        assertFalse(result.isValid());
        assertTrue(result.getErrors().stream()
                .anyMatch(e -> e.getMessage().contains("at least 5 characters")));
    }

    @Test
    @DisplayName("Should validate address - too long")
    public void testValidateAddress_TooLong() {
        ValidationResult result = ValidationResult.valid();
        String longAddress = "A".repeat(501);
        validator.validateAddress(longAddress, result);
        assertFalse(result.isValid());
        assertTrue(result.getErrors().stream()
                .anyMatch(e -> e.getMessage().contains("not exceed 500 characters")));
    }

    @Test
    @DisplayName("Should validate address - valid address")
    public void testValidateAddress_Valid() {
        ValidationResult result = ValidationResult.valid();
        validator.validateAddress("123 Main Street, New York, NY 10001", result);
        assertTrue(result.isValid());
    }

    @Test
    @DisplayName("Should validate pincode - empty pincode is allowed")
    public void testValidatePincode_Empty() {
        ValidationResult result = ValidationResult.valid();
        validator.validatePincode("", result);
        assertTrue(result.isValid());
    }

    @Test
    @DisplayName("Should validate pincode - invalid format (not 6 digits)")
    public void testValidatePincode_InvalidFormat() {
        ValidationResult result = ValidationResult.valid();
        validator.validatePincode("12345", result);
        assertFalse(result.isValid());
        assertTrue(result.getErrors().stream()
                .anyMatch(e -> e.getMessage().contains("exactly 6 digits")));
    }

    @Test
    @DisplayName("Should validate pincode - with letters")
    public void testValidatePincode_WithLetters() {
        ValidationResult result = ValidationResult.valid();
        validator.validatePincode("1234AB", result);
        assertFalse(result.isValid());
    }

    @Test
    @DisplayName("Should validate pincode - valid pincode")
    public void testValidatePincode_Valid() {
        ValidationResult result = ValidationResult.valid();
        validator.validatePincode("110001", result);
        assertTrue(result.isValid());
    }

    @Test
    @DisplayName("Should validate GSTIN - empty GSTIN is allowed")
    public void testValidateGstin_Empty() {
        ValidationResult result = ValidationResult.valid();
        validator.validateGstin("", result);
        assertTrue(result.isValid());
    }

    @Test
    @DisplayName("Should validate GSTIN - invalid length")
    public void testValidateGstin_InvalidLength() {
        ValidationResult result = ValidationResult.valid();
        validator.validateGstin("27AAPDU0055K1Z", result);
        assertFalse(result.isValid());
        assertTrue(result.getErrors().stream()
                .anyMatch(e -> e.getMessage().contains("exactly 15 characters")));
    }

    @Test
    @DisplayName("Should validate GSTIN - invalid format")
    public void testValidateGstin_InvalidFormat() {
        ValidationResult result = ValidationResult.valid();
        validator.validateGstin("12345678901234", result);
        assertFalse(result.isValid());
        assertTrue(result.getErrors().stream()
                .anyMatch(e -> e.getMessage().contains("format is invalid")));
    }

    @Test
    @DisplayName("Should validate GSTIN - valid GSTIN")
    public void testValidateGstin_Valid() {
        ValidationResult result = ValidationResult.valid();
        validator.validateGstin("27AAPDU0055K1ZO", result);
        assertTrue(result.isValid());
    }

    @Test
    @DisplayName("Should validate GSTIN - valid (lowercase input should work)")
    public void testValidateGstin_ValidLowercase() {
        ValidationResult result = ValidationResult.valid();
        validator.validateGstin("27aapdu0055k1zo", result);
        assertTrue(result.isValid());
    }

    @Test
    @DisplayName("Should validate PAN - empty PAN is allowed")
    public void testValidatePan_Empty() {
        ValidationResult result = ValidationResult.valid();
        validator.validatePanNumber("", result);
        assertTrue(result.isValid());
    }

    @Test
    @DisplayName("Should validate PAN - invalid length")
    public void testValidatePan_InvalidLength() {
        ValidationResult result = ValidationResult.valid();
        validator.validatePanNumber("ABCDE123", result);
        assertFalse(result.isValid());
        assertTrue(result.getErrors().stream()
                .anyMatch(e -> e.getMessage().contains("exactly 10 characters")));
    }

    @Test
    @DisplayName("Should validate PAN - invalid format")
    public void testValidatePan_InvalidFormat() {
        ValidationResult result = ValidationResult.valid();
        validator.validatePanNumber("1234567890", result);
        assertFalse(result.isValid());
        assertTrue(result.getErrors().stream()
                .anyMatch(e -> e.getMessage().contains("format is invalid")));
    }

    @Test
    @DisplayName("Should validate PAN - valid PAN")
    public void testValidatePan_Valid() {
        ValidationResult result = ValidationResult.valid();
        validator.validatePanNumber("ABCDE1234F", result);
        assertTrue(result.isValid());
    }

    @Test
    @DisplayName("Should validate PAN - valid (lowercase input should work)")
    public void testValidatePan_ValidLowercase() {
        ValidationResult result = ValidationResult.valid();
        validator.validatePanNumber("abcde1234f", result);
        assertTrue(result.isValid());
    }

    @Test
    @DisplayName("Should validate department record ID - empty ID is allowed")
    public void testValidateDepartmentRecordId_Empty() {
        ValidationResult result = ValidationResult.valid();
        validator.validateDepartmentRecordId("", result);
        assertTrue(result.isValid());
    }

    @Test
    @DisplayName("Should validate department record ID - valid ID")
    public void testValidateDepartmentRecordId_Valid() {
        ValidationResult result = ValidationResult.valid();
        validator.validateDepartmentRecordId("DEPT123", result);
        assertTrue(result.isValid());
    }

    @Test
    @DisplayName("Should validate optional fields - GSTIN and PAN can be null")
    public void testValidateDepartmentRecord_OptionalFields() {
        validMessage.setGstin(null);
        validMessage.setPanNumber(null);
        validMessage.setPincode(null);

        ValidationResult result = validator.validateDepartmentRecord(validMessage);
        assertTrue(result.isValid(), "Record should be valid with optional fields as null");
    }

    @Test
    @DisplayName("Should allow missing fields")
    public void testValidateDepartmentRecord_MissingRequiredFields() {
        validMessage.setName(null);
        validMessage.setAddress(null);
        validMessage.setDepartmentRecordId(null);
        validMessage.setGstin(null);
        validMessage.setPanNumber(null);
        validMessage.setPincode(null);
        validMessage.setDepartmentName(null);

        ValidationResult result = validator.validateDepartmentRecord(validMessage);
        assertTrue(result.isValid());
        assertEquals(0, result.getErrors().size());
    }
}
