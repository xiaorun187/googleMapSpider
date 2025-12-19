# Design Document: Database Uniqueness Refactor

## Overview

本设计文档描述了数据库唯一性判断逻辑的重构方案。核心变更是将唯一性判断从基于 email 字段改为基于 name 和 website 字段的联合判断，同时引入自动生成的唯一编号字段（unique_id）。

### 主要变更

1. 移除 email 字段的 UNIQUE 约束
2. 添加 unique_id 字段并创建唯一索引
3. 创建 (name, website) 复合唯一索引
4. 重构数据插入逻辑，支持新的唯一性判断
5. 更新 DataDeduplicator 组件的去重逻辑

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Application Layer                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │   app.py    │  │  scraper.py │  │  csv_importer.py    │  │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘  │
│         │                │                     │             │
│         └────────────────┼─────────────────────┘             │
│                          ▼                                   │
│  ┌───────────────────────────────────────────────────────┐  │
│  │              DataDeduplicator (Updated)                │  │
│  │  - check_duplicate_by_name_website()                  │  │
│  │  - validate_before_insert()                           │  │
│  └───────────────────────────────────────────────────────┘  │
│                          │                                   │
│                          ▼                                   │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                    db.py (Updated)                     │  │
│  │  - save_business_data_to_db()                         │  │
│  │  - validate_uniqueness()                              │  │
│  │  - generate_unique_id()                               │  │
│  └───────────────────────────────────────────────────────┘  │
│                          │                                   │
└──────────────────────────┼───────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    Database Layer                            │
│  ┌───────────────────────────────────────────────────────┐  │
│  │              business_records Table                    │  │
│  │  - id (PRIMARY KEY)                                   │  │
│  │  - unique_id (UNIQUE INDEX) ← NEW                     │  │
│  │  - name                                               │  │
│  │  - website                                            │  │
│  │  - email (no longer UNIQUE)                           │  │
│  │  - ... other fields                                   │  │
│  │                                                       │  │
│  │  Indexes:                                             │  │
│  │  - idx_unique_id (UNIQUE)                             │  │
│  │  - idx_name_website (UNIQUE COMPOSITE)                │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## Components and Interfaces

### 1. Database Schema Changes (db.py)

#### 新增字段
```python
unique_id TEXT UNIQUE  # UUID 格式的唯一标识符
```

#### 索引变更
- 移除: `email TEXT UNIQUE` 约束
- 新增: `CREATE UNIQUE INDEX idx_unique_id ON business_records(unique_id)`
- 新增: `CREATE UNIQUE INDEX idx_name_website ON business_records(name, website)`

#### 新增函数

```python
def generate_unique_id() -> str:
    """生成 UUID 格式的唯一标识符"""
    
def validate_uniqueness(name: str, website: str, exclude_id: int = None) -> ValidationResult:
    """
    验证 name + website 组合的唯一性
    
    Returns:
        ValidationResult: 包含 is_valid, error_message, existing_record
    """

def check_duplicate_exists(name: str, website: str) -> Optional[dict]:
    """检查是否存在相同 name + website 的记录"""
```

### 2. DataDeduplicator Updates (utils/data_deduplicator.py)

#### 接口变更

```python
def check_duplicate(
    self, 
    record: BusinessRecord, 
    existing_records: List[BusinessRecord]
) -> Optional[BusinessRecord]:
    """
    检查是否存在重复记录
    变更: 基于 name + website 判断，而非 email
    """

def is_duplicate_by_name_website(
    self,
    name: str,
    website: str,
    existing_records: List[BusinessRecord]
) -> bool:
    """新增: 基于 name + website 检查重复"""
```

### 3. BusinessRecord Model Updates (models/business_record.py)

#### 新增字段
```python
unique_id: Optional[str] = None  # UUID 格式的唯一标识符
```

#### 接口变更
```python
def __eq__(self, other) -> bool:
    """变更: 基于 name + website 判断相等性"""

def __hash__(self) -> int:
    """变更: 基于 name + website 计算哈希值"""
```

### 4. ValidationResult 数据类

```python
@dataclass
class ValidationResult:
    """验证结果"""
    is_valid: bool
    error_message: Optional[str] = None
    existing_record: Optional[dict] = None
```

## Data Models

### business_records 表结构（更新后）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | 自增主键 |
| unique_id | TEXT | UNIQUE, NOT NULL | UUID 唯一标识符 |
| name | TEXT | - | 商家名称 |
| website | TEXT | - | 商家网站 |
| email | TEXT | - | 邮箱（移除 UNIQUE） |
| phones | TEXT | - | 电话号码 |
| facebook | TEXT | - | Facebook 链接 |
| twitter | TEXT | - | Twitter 链接 |
| instagram | TEXT | - | Instagram 链接 |
| linkedin | TEXT | - | LinkedIn 链接 |
| whatsapp | TEXT | - | WhatsApp 链接 |
| youtube | TEXT | - | YouTube 链接 |
| city | TEXT | - | 城市 |
| product | TEXT | - | 商品/关键词 |
| send_count | INTEGER | DEFAULT 0 | 发送次数 |
| updated_at | TEXT | DEFAULT CURRENT_TIMESTAMP | 更新时间 |
| created_at | TEXT | DEFAULT CURRENT_TIMESTAMP | 创建时间 |

### 索引结构

| 索引名 | 字段 | 类型 | 说明 |
|--------|------|------|------|
| idx_unique_id | unique_id | UNIQUE | 唯一标识符索引 |
| idx_name_website | (name, website) | UNIQUE | 复合唯一索引 |
| idx_business_email | email | INDEX | 邮箱查询索引 |
| idx_business_city | city | INDEX | 城市查询索引 |
| idx_business_product | product | INDEX | 商品查询索引 |
| idx_business_updated | updated_at | INDEX | 更新时间索引 |

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Duplicate Detection by Name and Website

*For any* two business records, if both the name and website fields are identical, the system SHALL identify them as duplicates and prevent the second record from being inserted.

**Validates: Requirements 1.1**

### Property 2: Distinct Records with Different Name

*For any* two business records with different name values (regardless of website value), the system SHALL store both records as distinct entries.

**Validates: Requirements 1.2, 1.4**

### Property 3: Distinct Records with Different Website

*For any* two business records with different website values (regardless of name value), the system SHALL store both records as distinct entries.

**Validates: Requirements 1.3, 1.4**

### Property 4: Unique ID Generation

*For any* set of business records created (including concurrent creation), each record SHALL have a distinct unique_id value that is never duplicated.

**Validates: Requirements 2.1, 2.2**

### Property 5: Unique ID Presence in Query Results

*For any* query that returns business records, each record in the result SHALL include a non-null unique_id field.

**Validates: Requirements 2.3**

### Property 6: Duplicate Insertion Error Handling

*For any* attempt to insert a duplicate record (same name and website), the system SHALL return a validation error with a descriptive message and preserve the original data state without partial modifications.

**Validates: Requirements 4.1, 4.2, 4.3**

### Property 7: BusinessRecord Round-Trip with Unique ID

*For any* BusinessRecord object with a unique_id, serializing to JSON/dict and deserializing SHALL produce an equivalent object with the same unique_id.

**Validates: Requirements 2.3** (extends existing Property 11)

## Error Handling

### 错误类型

1. **DuplicateRecordError**: 当尝试插入重复记录（相同 name + website）时抛出
   - 错误消息: "Record with name '{name}' and website '{website}' already exists"
   - 包含现有记录的 ID 和 unique_id

2. **UniqueIdConflictError**: 当 unique_id 冲突时抛出（理论上不应发生）
   - 错误消息: "Unique ID conflict detected, regenerating..."
   - 自动重试生成新的 unique_id

3. **ValidationError**: 当数据验证失败时抛出
   - 包含具体的验证失败原因

### 错误处理策略

```python
try:
    # 1. 验证唯一性
    validation = validate_uniqueness(name, website)
    if not validation.is_valid:
        return {
            'success': False,
            'error': validation.error_message,
            'existing_record': validation.existing_record
        }
    
    # 2. 生成 unique_id
    unique_id = generate_unique_id()
    
    # 3. 插入记录
    cursor.execute(insert_sql, params)
    connection.commit()
    
except sqlite3.IntegrityError as e:
    connection.rollback()
    if 'UNIQUE constraint failed: business_records.name, business_records.website' in str(e):
        return {'success': False, 'error': 'Duplicate record detected'}
    raise
```

## Testing Strategy

### 测试框架

- **单元测试**: pytest
- **属性测试**: hypothesis (已在项目中使用)

### 测试类型

#### 1. 属性测试 (Property-Based Tests)

使用 Hypothesis 库，每个属性测试运行至少 100 次迭代。

测试文件: `tests/test_database_uniqueness.py`

属性测试覆盖:
- Property 1: 重复检测（相同 name + website）
- Property 2: 不同 name 存储为不同记录
- Property 3: 不同 website 存储为不同记录
- Property 4: unique_id 唯一性
- Property 5: 查询结果包含 unique_id
- Property 6: 重复插入错误处理
- Property 7: BusinessRecord 序列化往返

#### 2. 单元测试

测试文件: `tests/test_database_uniqueness.py`

覆盖场景:
- 数据库初始化和索引创建
- 边界条件（null 值、空字符串、特殊字符）
- 并发插入测试

### 测试数据生成器

```python
@st.composite
def business_record_with_name_website(draw):
    """生成带有 name 和 website 的商家记录"""
    name = draw(st.text(min_size=1, max_size=50))
    website = draw(st.one_of(
        st.none(),
        st.text(min_size=0, max_size=100)
    ))
    return BusinessRecord(name=name, website=website, ...)
```

### 边界条件测试

- name 为 None 或空字符串
- website 为 None 或空字符串
- name 和 website 都为 None
- 包含特殊字符（Unicode、SQL 注入字符等）
- 超长字符串
