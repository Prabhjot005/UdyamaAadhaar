package com.hashkey.validation_service.controller;

import com.hashkey.validation_service.mongodb.document.ValidDepartmentRecord;
import com.hashkey.validation_service.mongodb.service.DepartmentRecordService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import java.util.List;
import java.util.Optional;
import java.util.HashMap;
import java.util.Map;

@RestController
@RequestMapping("/api/department-records")
public class DepartmentRecordController {

    private static final Logger logger = LoggerFactory.getLogger(DepartmentRecordController.class);

    @Autowired
    private DepartmentRecordService departmentRecordService;

    /**
     * Get all department records
     */
    @GetMapping
    public ResponseEntity<List<ValidDepartmentRecord>> getAllRecords() {
        logger.info("Fetching all department records");
        List<ValidDepartmentRecord> records = departmentRecordService.findAll();
        return ResponseEntity.ok(records);
    }

    /**
     * Get department record by MongoDB ID
     */
    @GetMapping("/{id}")
    public ResponseEntity<?> getRecordById(@PathVariable String id) {
        logger.info("Fetching department record with ID: {}", id);
        Optional<ValidDepartmentRecord> record = departmentRecordService.findById(id);
        if (record.isPresent()) {
            return ResponseEntity.ok(record.get());
        } else {
            Map<String, String> error = new HashMap<>();
            error.put("error", "Record not found");
            return ResponseEntity.status(HttpStatus.NOT_FOUND).body(error);
        }
    }

    /**
     * Get department record by departmentRecordId
     */
    @GetMapping("/by-department-id/{departmentRecordId}")
    public ResponseEntity<?> getRecordByDepartmentId(@PathVariable String departmentRecordId) {
        logger.info("Fetching department record with departmentRecordId: {}", departmentRecordId);
        Optional<ValidDepartmentRecord> record = departmentRecordService.findByDepartmentRecordId(departmentRecordId);
        if (record.isPresent()) {
            return ResponseEntity.ok(record.get());
        } else {
            Map<String, String> error = new HashMap<>();
            error.put("error", "Record not found");
            return ResponseEntity.status(HttpStatus.NOT_FOUND).body(error);
        }
    }

    /**
     * Get all valid records
     */
    @GetMapping("/valid-records")
    public ResponseEntity<List<ValidDepartmentRecord>> getAllValidRecords() {
        logger.info("Fetching all valid department records");
        List<ValidDepartmentRecord> records = departmentRecordService.findAllValidRecords();
        return ResponseEntity.ok(records);
    }

    /**
     * Get records by department name
     */
    @GetMapping("/by-department-name/{departmentName}")
    public ResponseEntity<List<ValidDepartmentRecord>> getRecordsByDepartmentName(@PathVariable String departmentName) {
        logger.info("Fetching records with department name: {}", departmentName);
        List<ValidDepartmentRecord> records = departmentRecordService.findByDepartmentName(departmentName);
        return ResponseEntity.ok(records);
    }

    /**
     * Get records by source name
     */
    @GetMapping("/by-source-name/{sourceName}")
    public ResponseEntity<List<ValidDepartmentRecord>> getRecordsBySourceName(@PathVariable String sourceName) {
        logger.info("Fetching records with source name: {}", sourceName);
        List<ValidDepartmentRecord> records = departmentRecordService.findBySourceName(sourceName);
        return ResponseEntity.ok(records);
    }

    /**
     * Get record by GSTIN
     */
    @GetMapping("/by-gstin/{gstin}")
    public ResponseEntity<?> getRecordByGstin(@PathVariable String gstin) {
        logger.info("Fetching record with GSTIN: {}", gstin);
        Optional<ValidDepartmentRecord> record = departmentRecordService.findByGstin(gstin);
        if (record.isPresent()) {
            return ResponseEntity.ok(record.get());
        } else {
            Map<String, String> error = new HashMap<>();
            error.put("error", "Record not found");
            return ResponseEntity.status(HttpStatus.NOT_FOUND).body(error);
        }
    }

    /**
     * Get record by PAN
     */
    @GetMapping("/by-pan/{panNumber}")
    public ResponseEntity<?> getRecordByPan(@PathVariable String panNumber) {
        logger.info("Fetching record with PAN: {}", panNumber);
        Optional<ValidDepartmentRecord> record = departmentRecordService.findByPanNumber(panNumber);
        if (record.isPresent()) {
            return ResponseEntity.ok(record.get());
        } else {
            Map<String, String> error = new HashMap<>();
            error.put("error", "Record not found");
            return ResponseEntity.status(HttpStatus.NOT_FOUND).body(error);
        }
    }

    /**
     * Get statistics
     */
    @GetMapping("/statistics")
    public ResponseEntity<Map<String, Object>> getStatistics() {
        logger.info("Fetching statistics");
        Map<String, Object> stats = new HashMap<>();
        stats.put("totalRecords", departmentRecordService.countTotalRecords());
        stats.put("validRecords", departmentRecordService.countValidRecords());
        stats.put("invalidRecords", departmentRecordService.countInvalidRecords());
        return ResponseEntity.ok(stats);
    }
}
