# SSDT Table Design Patterns

Use this skill when creating new SQL Server tables in an SSDT project. Covers audit columns, soft delete, primary/foreign key naming, index design, data type selection, and constraint patterns.

## Table Template

### Application Table (Full Audit Trail)

```sql
CREATE TABLE dbo.APP_MY_TABLE
(
    MY_TABLE_ID             INT IDENTITY NOT NULL,
    POSTN_KEY               BIGINT NOT NULL,
    TIME_ID                 INT NOT NULL,
    NAME                    VARCHAR(100),
    STATUS__OPTION_ID       INT,
    AMOUNT_AMT              NUMERIC(18,2),
    RATE_PCT                NUMERIC(18,4),
    ITEM_CNT                INT,
    COMMENT_TXT             VARCHAR(4000),
    ACTIVE_IND              BIT,
    CREATE_DATE             DATETIME,
    CREATE__USER_ID         INT,
    MODIFY_DATE             DATETIME,
    MODIFY__USER_ID         INT,
    DELETE_DATE             DATETIME,
    DELETE__USER_ID         INT,
    CONSTRAINT APP_MY_TABLE_PK PRIMARY KEY (MY_TABLE_ID)
)
GO

ALTER TABLE dbo.APP_MY_TABLE ADD CONSTRAINT APP_POSTN_APP_MY_TABLE_fk
FOREIGN KEY (POSTN_KEY)
REFERENCES dbo.APP_POSTN (POSTN_KEY)
ON DELETE NO ACTION
ON UPDATE NO ACTION
GO

ALTER TABLE dbo.APP_MY_TABLE ADD CONSTRAINT APP_TIME_APP_MY_TABLE_fk
FOREIGN KEY (TIME_ID)
REFERENCES dbo.APP_TIME (TIME_ID)
ON DELETE NO ACTION
ON UPDATE NO ACTION
GO

ALTER TABLE dbo.APP_MY_TABLE ADD CONSTRAINT APP_OPTION_APP_MY_TABLE_fk
FOREIGN KEY (STATUS__OPTION_ID)
REFERENCES dbo.APP_OPTION (OPTION_ID)
ON DELETE NO ACTION
ON UPDATE NO ACTION
GO

ALTER TABLE dbo.APP_MY_TABLE ADD CONSTRAINT APP_USER_APP_MY_TABLE_fk
FOREIGN KEY (CREATE__USER_ID)
REFERENCES dbo.APP_USER (USER_ID)
ON DELETE NO ACTION
ON UPDATE NO ACTION
GO

ALTER TABLE dbo.APP_MY_TABLE ADD CONSTRAINT APP_USER_APP_MY_TABLE_fk1
FOREIGN KEY (MODIFY__USER_ID)
REFERENCES dbo.APP_USER (USER_ID)
ON DELETE NO ACTION
ON UPDATE NO ACTION
GO

ALTER TABLE dbo.APP_MY_TABLE ADD CONSTRAINT APP_USER_APP_MY_TABLE_fk2
FOREIGN KEY (DELETE__USER_ID)
REFERENCES dbo.APP_USER (USER_ID)
ON DELETE NO ACTION
ON UPDATE NO ACTION
GO
```

### Fact/Metrics Table (Composite Key, No Audit)

```sql
CREATE TABLE dbo.PRO_MY_METRIC
(
    POSTN_KEY               BIGINT NOT NULL,
    TIME_ID                 INT NOT NULL,
    FIRST_NAME              VARCHAR(100),
    LAST_NAME               VARCHAR(100),
    EMP_CD                  VARCHAR(16),
    SUBORD_NAME             VARCHAR(200),
    METRIC_VALUE            NUMERIC(19,2),
    METRIC_PCT              NUMERIC(9,4),
    STATUS                  VARCHAR(20),
    ON_PACE_VALUE           INT,
    CURRENT_REPORTING_IND   BIT NOT NULL DEFAULT 0,
    REPORT_DATE             DATETIME,
    LOAD_DATE               DATETIME,
    CONSTRAINT PK_PRO_MY_METRIC PRIMARY KEY (POSTN_KEY, TIME_ID),
    CONSTRAINT FK_PRO_MY_METRIC__POSTN FOREIGN KEY (POSTN_KEY) REFERENCES dbo.APP_POSTN (POSTN_KEY),
    CONSTRAINT FK_PRO_MY_METRIC__TIME FOREIGN KEY (TIME_ID) REFERENCES dbo.APP_TIME (TIME_ID)
)
GO
```

### Staging Table (No Keys, No Audit)

```sql
CREATE TABLE dbo.STG_MY_DATA
(
    POSTN_KEY               BIGINT,
    TIME_ID                 INT,
    EMP_CD                  VARCHAR(16),
    METRIC_VALUE            NUMERIC(18,2),
    LOAD_DATE               DATETIME
)
GO
```

### Log Table (Write-Only, FILLFACTOR)

```sql
CREATE TABLE dbo.LOG_MY_EVENT
(
    EVENT_ID                INT IDENTITY(1,1) NOT NULL,
    EVENT_TYPE              VARCHAR(50),
    MESSAGE_TXT             VARCHAR(MAX),
    USER_NAME               VARCHAR(20),
    CREATE_DATE             DATETIME,
    CREATE__USER_ID         INT,
    CONSTRAINT LOG_MY_EVENT_PK PRIMARY KEY CLUSTERED (EVENT_ID ASC) WITH (FILLFACTOR = 90)
)
GO
```

## Table Prefix Rules

| Prefix | Purpose | Audit Columns | Foreign Keys |
|--------|---------|---------------|--------------|
| `APP_` | Application/domain data | Full (CREATE/MODIFY/DELETE) | Yes |
| `PRO_` | Production/promotion results | REPORT_DATE, LOAD_DATE | POSTN_KEY, TIME_ID |
| `STG_` | Staging (ETL intermediate) | LOAD_DATE only | None |
| `ETL_` | ETL extract tables | LOAD_DATE only | None |
| `LOG_` | Logging/audit | CREATE_DATE, CREATE__USER_ID | Minimal |
| `EXCEL__` | Excel import (note double underscore) | None | None |
| `FILE__` | File-based import (note double underscore) | None | None |
| `EWSOP000__` | External data warehouse mirror | None | None |

## Audit Column Patterns

### Full Audit (APP_ tables with user modifications)

```sql
CREATE_DATE             DATETIME,
CREATE__USER_ID         INT,           -- FK to APP_USER
MODIFY_DATE             DATETIME,      -- or CHANGE_DATE
MODIFY__USER_ID         INT,           -- or CHANGE__USER_ID
DELETE_DATE             DATETIME,      -- soft delete marker
DELETE__USER_ID         INT,
```

Note: Some tables use `CHANGE_DATE`/`CHANGE__USER_ID` instead of `MODIFY_DATE`/`MODIFY__USER_ID`. Both are acceptable — be consistent within a table.

### ETL/Load Audit (staging and result tables)

```sql
REPORT_DATE             DATETIME,      -- business date of the data
LOAD_DATE               DATETIME,      -- when the ETL ran (GETDATE())
```

### No Audit (external source mirrors, staging)

No audit columns — these are truncated and reloaded.

## Data Type Standards

| Purpose | Type | Notes |
|---------|------|-------|
| Surrogate key | `INT IDENTITY NOT NULL` | Auto-incrementing |
| Position key | `BIGINT NOT NULL` | Always BIGINT for POSTN_KEY |
| Time reference | `INT NOT NULL` | FK to APP_TIME.TIME_ID |
| Employee code | `VARCHAR(16)` | Always VARCHAR(16) for EMP_CD |
| Option reference | `INT` | FK to APP_OPTION.OPTION_ID |
| Money/amounts | `NUMERIC(18,2)` | 2 decimal places |
| Percentages | `NUMERIC(18,4)` or `NUMERIC(9,4)` | 4 decimal places, stored as decimal (0.80 = 80%) |
| Counts | `INT` | Whole numbers |
| Short codes | `VARCHAR(3)` to `VARCHAR(6)` | OPTION_CD, REGION_CD, etc. |
| Names | `VARCHAR(100)` | Standard for person/entity names |
| Descriptions | `VARCHAR(100)` (short) / `VARCHAR(4000)` (long) | SHORT_DESCR, LONG_DESCR |
| Free text | `VARCHAR(MAX)` | Comments, message bodies |
| Boolean flags | `BIT` | Suffix with `_IND` |
| Timestamps | `DATETIME` | Never use DATE-only columns |

## Column Naming Standards

| Suffix | Meaning | Example |
|--------|---------|---------|
| `_IND` | Boolean indicator (BIT) | `ACTIVE_IND`, `SKIP_IND` |
| `_AMT` | Monetary amount | `WRITTEN_PREMIUM_AMT` |
| `_PCT` | Percentage | `LOSS_RATIO_PCT` |
| `_CNT` | Count/quantity | `POLICY_INFORCE_CNT` |
| `_CD` | Code | `REGION_CD`, `OPTION_CD` |
| `_TXT` | Text content | `COMMENT_TXT`, `MESSAGE_TXT` |
| `_NBR` | Number as string | `AGENT_NBR`, `POLICY_NBR` |
| `_KEY` | Position/business key | `POSTN_KEY` |
| `_ID` | Surrogate identifier | `AWARD_ID`, `TIME_ID` |
| `_DATE` or `_DT` | Timestamp | `CREATE_DATE`, `AGCY_TRMNTN_DT` |
| `_NAME` | Entity name | `AGENCY_NAME` |
| `SHORT_DESCR` | Short description | — |
| `LONG_DESCR` | Long description | — |

### Double Underscore Convention

Double underscores prefix the semantic type of a foreign key:

```sql
POSTN_LEVEL__OPTION_ID      INT     -- position level → APP_OPTION
USER_TYPE__OPTION_ID        INT     -- user type → APP_OPTION
PERIOD_TYPE__OPTION_ID      INT     -- period type → APP_OPTION
PARENT__POSTN_KEY           BIGINT  -- parent position → APP_POSTN
CHILD__POSTN_KEY            BIGINT  -- child position → APP_POSTN
CREATE__USER_ID             INT     -- creator → APP_USER
PARENT__GROUP_ID            INT     -- parent group → APP_GROUP (self-ref)
```

## Primary Key Naming

```
[TABLE_NAME]_PK    or    [TABLE_NAME]_pk    or    PK_[TABLE_NAME]
```

All three forms are used. Be consistent within new work. Examples:
- `APP_AWARD_PK` — single column (INT IDENTITY)
- `APP_HIERARCHY_pk` — composite (PARENT__POSTN_KEY, CHILD__POSTN_KEY, TIME_ID)
- `PK_PRO_AFS_RECOGNITION` — composite (POSTN_KEY, TIME_ID)

### FILLFACTOR

Apply `WITH (FILLFACTOR = 90)` to primary keys and indexes on tables with heavy UPDATE/INSERT activity:

```sql
CONSTRAINT APP_HIERARCHY_pk PRIMARY KEY (PARENT__POSTN_KEY, CHILD__POSTN_KEY, TIME_ID)
    WITH (FILLFACTOR = 90)
```

Use on: APP_HIERARCHY, APP_OPTION, LOG_EMAIL, APP_POSTN_REL, and any high-churn table.

## Foreign Key Rules

**Naming:** `[REFERENCED_TABLE]_[CURRENT_TABLE]_fk` — append number for multiples:

```sql
APP_USER_APP_AWARD_fk       -- CREATE__USER_ID
APP_USER_APP_AWARD_fk1      -- MODIFY__USER_ID
APP_USER_APP_AWARD_fk2      -- DELETE__USER_ID
```

**Always use:**
```sql
ON DELETE NO ACTION
ON UPDATE NO ACTION
```

No cascading deletes or updates — ever. Soft delete with DELETE_DATE instead.

**Separate from CREATE TABLE:** Place FK constraints in separate `ALTER TABLE` statements after the CREATE TABLE. This allows tables to be deployed in any order.

## Index Design

**Naming:** `IX_[TABLE]__[COLUMN]`

```sql
CREATE NONCLUSTERED INDEX IX_APP_USER__USER_NAME
    ON dbo.APP_USER (USER_NAME)
GO

CREATE NONCLUSTERED INDEX IX_APP_HIERARCHY__PARENT__POSTN_KEY
    ON dbo.APP_HIERARCHY (CHILD__POSTN_KEY ASC, TIME_ID ASC)
    INCLUDE (PARENT__POSTN_KEY)
    WITH (FILLFACTOR = 90)
GO
```

**When to add indexes:**
- Foreign key columns (speeds up JOIN performance)
- Columns used in WHERE clauses of P_INTF__ procedures
- Columns used in ORDER BY of pagination queries
- Use `INCLUDE` clause for covering indexes (avoids table lookups)

## DEFAULT Values

Use sparingly — only for columns with clear business defaults:

```sql
CURRENT_REPORTING_IND   BIT NOT NULL DEFAULT 0
HTML_IND                BIT DEFAULT 1 NOT NULL
```

Do not add defaults for audit columns (CREATE_DATE, etc.) — these are set explicitly by stored procedures using `GETDATE()`.

## Adding to SSDT Project

After creating the `.sql` file in `dbo/Tables/`:

1. Add to `.sqlproj`: `<Build Include="dbo\Tables\APP_MY_TABLE.sql" />`
2. Place in the `<ItemGroup>` with other table files
3. See the `vs-project-files` skill for detailed `.sqlproj` entry patterns

## Anti-Patterns

- **Do not** use cascading deletes — use soft delete with DELETE_DATE
- **Do not** put FK constraints inline in CREATE TABLE for APP_ tables — use separate ALTER TABLE statements
- **Do not** use `DATE` type — use `DATETIME` for all date/time columns
- **Do not** use `MONEY` type — use `NUMERIC(18,2)` for amounts
- **Do not** add DEFAULT GETDATE() to audit columns — set explicitly in procedures
- **Do not** create tables without adding them to the `.sqlproj` file
- **Do not** use `NVARCHAR` unless storing Unicode data — use `VARCHAR` for standard text
