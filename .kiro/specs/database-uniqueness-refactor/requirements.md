# Requirements Document

## Introduction

本文档定义了数据库唯一性判断逻辑重构的需求。当前系统使用 email 字段作为唯一约束，导致当名称和网址不同但 email 相同时，数据被错误地覆盖。重构后，系统将基于名称（name）和网址（website）的联合判断来确定数据唯一性，并引入唯一编号字段确保数据存储的唯一性。

## Glossary

- **Business_Record_System**: 商家记录管理系统，负责存储和管理商家数据
- **Unique_ID**: 系统自动生成的唯一编号字段，用于标识每条记录
- **Name_Website_Combination**: 名称和网址字段的组合，用于判断数据是否重复
- **Duplicate_Record**: 名称和网址字段值完全相同的记录
- **Distinct_Record**: 名称或网址字段值至少有一个不同的记录

## Requirements

### Requirement 1

**User Story:** As a data administrator, I want the system to identify records as duplicates only when both name and website are identical, so that records with different names or websites are correctly stored as separate entries.

#### Acceptance Criteria

1. WHEN a new record is inserted with name and website values that both match an existing record THEN the Business_Record_System SHALL identify the record as a duplicate
2. WHEN a new record is inserted with a different name value compared to all existing records THEN the Business_Record_System SHALL store the record as a distinct entry
3. WHEN a new record is inserted with a different website value compared to all existing records THEN the Business_Record_System SHALL store the record as a distinct entry
4. WHEN a new record is inserted with both name and website values different from all existing records THEN the Business_Record_System SHALL store the record as a distinct entry

### Requirement 2

**User Story:** As a system administrator, I want each record to have a unique identifier generated automatically, so that I can reliably reference and manage individual records.

#### Acceptance Criteria

1. WHEN a new record is created THEN the Business_Record_System SHALL generate a unique Unique_ID value for the record
2. WHEN multiple records are created simultaneously THEN the Business_Record_System SHALL assign distinct Unique_ID values to each record
3. WHEN querying records THEN the Business_Record_System SHALL return the Unique_ID field for each record

### Requirement 3

**User Story:** As a database administrator, I want the database indexes to be optimized for the new uniqueness logic, so that queries perform efficiently and uniqueness constraints are properly enforced.

#### Acceptance Criteria

1. WHEN the database is initialized THEN the Business_Record_System SHALL create a composite unique index on name and website fields
2. WHEN the database is initialized THEN the Business_Record_System SHALL remove the existing unique constraint on the email field
3. WHEN the database is initialized THEN the Business_Record_System SHALL create a unique index on the Unique_ID field

### Requirement 4

**User Story:** As a data operator, I want the system to validate data before insertion and provide clear feedback on conflicts, so that I can understand and resolve data issues.

#### Acceptance Criteria

1. WHEN a duplicate record (same name and website) is detected before insertion THEN the Business_Record_System SHALL return a validation error with a descriptive message
2. WHEN an index conflict occurs during insertion THEN the Business_Record_System SHALL handle the error gracefully and provide user-readable feedback
3. WHEN validation fails THEN the Business_Record_System SHALL preserve the original data state without partial modifications

### Requirement 5

**User Story:** As a quality assurance engineer, I want comprehensive tests for the uniqueness logic, so that I can verify the system correctly identifies duplicate and distinct records.

#### Acceptance Criteria

1. WHEN testing normal data insertion THEN the test suite SHALL verify that records with unique name-website combinations are stored successfully
2. WHEN testing duplicate detection THEN the test suite SHALL verify that records with identical name and website values are identified as duplicates
3. WHEN testing edge cases THEN the test suite SHALL verify handling of null values, empty strings, and special characters in name and website fields
4. WHEN testing concurrent insertions THEN the test suite SHALL verify that the uniqueness constraint is enforced correctly under concurrent access
