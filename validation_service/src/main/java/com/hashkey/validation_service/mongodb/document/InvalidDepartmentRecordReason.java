package com.hashkey.validation_service.mongodb.document;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class InvalidDepartmentRecordReason {

    private String code;
    private String field;
    private String message;
}
