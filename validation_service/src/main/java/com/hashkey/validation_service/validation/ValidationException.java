package com.hashkey.validation_service.validation;

import java.util.List;

public class ValidationException extends RuntimeException {
    private List<ValidationError> errors;

    public ValidationException(String message) {
        super(message);
    }

    public ValidationException(String message, List<ValidationError> errors) {
        super(message);
        this.errors = errors;
    }

    public ValidationException(String message, Throwable cause) {
        super(message, cause);
    }

    public List<ValidationError> getErrors() {
        return errors;
    }

    public void setErrors(List<ValidationError> errors) {
        this.errors = errors;
    }
}
