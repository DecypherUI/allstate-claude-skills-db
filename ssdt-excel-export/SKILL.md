# SSDT Excel Export Patterns (P_XLS__)

Use this skill when creating P_XLS__ stored procedures that format data for Excel export. These are thin wrappers around P_INTF__ procedures with human-readable column aliases.

## Core Pattern

P_XLS__ procedures follow a three-step pattern:

1. Set up pagination (get all rows)
2. Capture P_INTF__ output into a table variable
3. SELECT with "Title Case" column aliases for Excel headers

```sql
CREATE PROCEDURE dbo.P_XLS__GET_MY_GRID
    @PostnKey BIGINT
AS
/**************************************************************************
PROCEDURE:    P_XLS__GET_MY_GRID
DESCRIPTION:  Excel export wrapper for P_INTF__GET_MY_GRID.

SAMPLE CALL:
    EXEC P_XLS__GET_MY_GRID @PostnKey = 12345
***************************************************************************/

-- Step 1: Set up pagination to get all rows
DECLARE @Page           INT = 1,
        @PageSize       INT = 999999,
        @ColumnSorting  UDT_SORT_PAGE_DATA

INSERT INTO @ColumnSorting
VALUES  ('REGION_CD', 'ASC'),
        ('TERR_CD', 'ASC'),
        ('MKT_CD', 'ASC'),
        ('LAST_NAME', 'ASC')

-- Step 2: Capture P_INTF__ output
DECLARE @Result TABLE
(
    REGION_CD               VARCHAR(3),
    TERR_CD                 VARCHAR(1),
    MKT_CD                  VARCHAR(2),
    EMP_CD                  VARCHAR(16),
    FIRST_NAME              VARCHAR(100),
    LAST_NAME               VARCHAR(100),
    METRIC_VALUE            NUMERIC(18,2),
    METRIC_PCT              NUMERIC(18,4),
    STATUS                  VARCHAR(20),
    REPORT_DATE             VARCHAR(20),
    -- Pagination metadata (captured but not output)
    TOTAL_ROWS              INT,
    ROW                     INT,
    MIN_ROW_SHOWN           INT,
    MAX_ROW_SHOWN           INT,
    TOTAL_PAGES             INT,
    CURRENT_PAGE            INT
)

INSERT @Result
EXEC P_INTF__GET_MY_GRID @PostnKey, @Page, @PageSize, @ColumnSorting

-- Step 3: Select with Excel-friendly column names
SELECT  region_cd           AS [Reg],
        terr_cd             AS [Dist],
        mkt_cd              AS [Mkt],
        first_name          AS [First Name],
        last_name           AS [Last Name],
        emp_cd              AS [Emp Code],
        metric_value        AS [Metric Value],
        metric_pct * 100    AS [Metric %],
        status              AS [Status],
        report_date         AS [Results as of]
FROM    @Result
```

## Column Alias Conventions

### Bracket Notation

Use SQL Server brackets `[Column Name]` for all Excel column headers:

```sql
region_cd           AS [Reg]
terr_cd             AS [Dist]
mkt_cd              AS [Mkt]
state_cd            AS [State]
first_name          AS [First Name]
last_name           AS [Last Name]
emp_cd              AS [Emp Code]
agent_name          AS [Agency Name]
agent_number        AS [Agency Number]
award_name          AS [Award]
year                AS [Year]
```

Double-quote notation `"Column Name"` also works but brackets are preferred for consistency:

```sql
-- Both are acceptable
first_name          AS [Participant First Name]
first_name          AS "Participant First Name"
```

### Standard Abbreviations

| Database Column | Excel Header |
|----------------|--------------|
| `REGION_CD` | `[Reg]` |
| `TERR_CD` | `[Dist]` |
| `MKT_CD` | `[Mkt]` |
| `STATE_CD` | `[State]` |
| `EMP_CD` | `[Emp Code]` |
| `REPORT_DATE` | `[Results as of]` or `[Report Date]` |

### Percentage Columns

Multiply decimal percentages by 100 for Excel display:

```sql
-- Database stores 0.85 (85%)
metric_pct * 100            AS [Metric %]
staff_opt_in_pct * 100      AS [Total Staff Opt-In %]
loss_ratio_pct * 100        AS [Loss Ratio %]
```

### Option Code Lookups

Replace option IDs with human-readable descriptions:

```sql
SELECT  r.*,
        o.short_descr   AS [Role]
FROM    @Result r
JOIN    app_group   g   ON g.group_cd = 'PSL'
JOIN    app_option  o   ON o.group_id = g.group_id
                        AND o.option_cd = r.postn_level__option_cd
```

## Variations

### Direct Query (No P_INTF__ Wrapper)

Some P_XLS__ procedures query tables directly when the P_INTF__ output doesn't match Excel needs:

```sql
CREATE PROCEDURE dbo.P_XLS__GET_AFFILIATION_EXPORT
    @PostnKey BIGINT = NULL
AS

;WITH person_hire AS (
    SELECT  per.person_id, MIN(CONVERT(DATE, per.start_date)) AS hire_date
    FROM    app_person_employee_rel per
    GROUP BY per.person_id
)
SELECT  pd.region_cd                AS [RGN],
        pd.terr_cd                  AS [DIST],
        pd.mkt_cd                   AS [MKT],
        per.emp_cd                  AS [AGENT],
        ap.business_partner_id      AS [BPID],
        pd.first_name + ' ' + pd.last_name AS [AGENT NAME],
        CONVERT(VARCHAR(10), ph.hire_date, 101) AS [HIRE DATE],
        s.anniversary_year_cnt      AS [AFFILIATION COUNT]
FROM    app_summary                 s
JOIN    app_person                  ap  ON ap.person_id = s.person_id
-- ... more joins ...
WHERE   (@PostnKey IS NULL OR ha.parent__postn_key = @PostnKey)
ORDER BY pd.region_cd, pd.terr_cd, pd.mkt_cd, per.emp_cd
```

### With Additional Sorting

```sql
-- Define sort order for Excel output
INSERT INTO @ColumnSorting
VALUES  ('REGION_CD', 'DESC'),
        ('TERR_CD', 'ASC'),
        ('MKT_CD', 'ASC'),
        ('LSP_NAME', 'ASC')
```

## Table Variable Schema

The `@Result` table variable must match the **full output schema** of the P_INTF__ procedure, including pagination metadata columns:

```sql
DECLARE @Result TABLE
(
    -- Business columns (match P_INTF__ output exactly)
    COLUMN_1        VARCHAR(100),
    COLUMN_2        NUMERIC(18,2),
    -- ...

    -- Pagination metadata (always included, not output to Excel)
    TOTAL_ROWS      INT,
    ROW             INT,
    MIN_ROW_SHOWN   INT,
    MAX_ROW_SHOWN   INT,
    TOTAL_PAGES     INT,
    CURRENT_PAGE    INT
)
```

If the schema doesn't match, `INSERT ... EXEC` will fail with a column mismatch error.

## Naming Convention

```
P_XLS__GET_[FEATURE]_[VIEW]
```

Examples:
- `P_XLS__GET_AWARD_GRID` — wraps `P_INTF__GET_AWARD_GRID`
- `P_XLS__GET_LSP_AGENT_DASHBOARD_GRID` — wraps `P_INTF__GET_LSP_AGENT_DASHBOARD_GRID`
- `P_XLS__GET_AFFILIATION_EXPORT` — standalone export query

## Anti-Patterns

- **Do not** include pagination metadata columns in the final SELECT — they are internal
- **Do not** use UPPERCASE column aliases — use Title Case in brackets for readability
- **Do not** duplicate business logic from P_INTF__ — call it via INSERT...EXEC
- **Do not** forget to match the full P_INTF__ output schema in the table variable
- **Do not** leave percentages as decimals — multiply by 100 for Excel
