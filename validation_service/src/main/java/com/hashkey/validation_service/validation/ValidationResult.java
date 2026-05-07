package com.hashkey.validation_service.validation;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;
import java.util.ArrayList;
import java.util.List;

@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class ValidationResult {
    private boolean valid;
    private List<ValidationError> errors;

    public static ValidationResult valid() {
        return ValidationResult.builder()
                .valid(true)
                .errors(new ArrayList<>())
                .build();
    }

    public static ValidationResult invalid(List<ValidationError> errors) {
        return ValidationResult.builder()
                .valid(false)
                .errors(errors)
                .build();
    }

    public void addError(String field, String message) {
        addError("INVALID_RECORD", field, message);
    }

    public void addError(String code, String field, String message) {
        if (this.errors == null) {
            this.errors = new ArrayList<>();
        }
        this.errors.add(new ValidationError(code, field, message));
        this.valid = false;
    }

    public void addError(ValidationError error) {
        if (this.errors == null) {
            this.errors = new ArrayList<>();
        }
        this.errors.add(error);
        this.valid = false;
    }

    public boolean isValid() {
        return valid && (errors == null || errors.isEmpty());
    }
}
