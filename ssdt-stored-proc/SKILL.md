---
name: ssdt-stored-proc
description: Create SQL Server stored procedures following SSDT conventions. Use when writing new stored procedures, adding procedure headers, creating SAMPLE CALL sections, or implementing interface procedures. Includes naming conventions, output formatting, and dynamic SQL patterns.
---

# SSDT Stored Procedure Conventions

## Overview

This skill provides patterns for creating SQL Server stored procedures in SSDT projects, including naming conventions, header templates, and output formatting standards.

## IMPORTANT: Keep Documentation and Tests Updated

**After modifying a stored procedure, always update related artifacts:**

1. **Tests**: Update unit tests to reflect new columns, changed logic, or new business rules
2. **Requirements docs**: Update REQ_*.md if output schema or business rules change
3. **Test plans**: Update TESTPLAN_*.md if test scenarios change
4. **Module README**: Update module documentation if architectural changes occur
5. **SAMPLE CALL**: Update header's SAMPLE CALL and Helper Queries if parameters change

**Checklist after procedure changes:**
- [ ] Update related unit tests (column changes, logic changes)
- [ ] Add new data quality tests for new business rules
- [ ] Update requirements document if output schema changed
- [ ] Update test plan if test scenarios changed
- [ ] Update module README if significant logic changed
- [ ] Update SAMPLE CALL section if parameters changed

## Naming Convention

Stored procedures follow pattern `P_[TYPE]__[FUNCTION_NAME]`:

| Prefix | Purpose |
|--------|---------|
| `P_INTF__` | Interface/UI queries (data retrieval for screens) |
| `P_ETL__` | ETL operations |
| `P_EML__` | Email generation |
| `P_LOG__` | Logging operations |
| `P_SEC__` | Security operations |
| `P_REP__` | Reports |
| `P_UNIT__` | Unit test data management |

## Header Template

Each procedure includes a header comment block **AFTER** the CREATE PROCEDURE statement. This ensures the comment is compiled with the procedure and visible when developers browse the database.

```sql
CREATE PROCEDURE P_INTF__PROCEDURE_NAME
    @PostnKey BIGINT,
    @PromotionName VARCHAR(100)
AS
/******************************************************************************
PROC:       P_INTF__PROCEDURE_NAME
AUTHOR:     Initials (Full Name)
DATE:       MM/DD/YYYY

DESCRIPTION:
    Brief description of what the procedure does.

SAMPLE CALL:

    DECLARE @PostnKey BIGINT = 5999999999999
    DECLARE @PromotionName VARCHAR(100) = 'Home Stretch and Beyond'

    EXEC P_INTF__PROCEDURE_NAME @PostnKey, @PromotionName

Helper Queries:

    -- @PromotionName, @PostnKey: List valid promotion/position combinations
    SELECT p.PROMOTION_NAME, r.POSTN_KEY, pd.subord_name
    FROM APP_PROMOTION_RESULT r
    JOIN APP_PROMOTION p ON p.PROMOTION_ID = r.PROMOTION_ID
    JOIN V_APP__POSTN_DETAIL pd ON pd.POSTN_KEY = r.POSTN_KEY
    GROUP BY p.PROMOTION_NAME, r.POSTN_KEY, pd.subord_name
    ORDER BY p.PROMOTION_NAME, r.POSTN_KEY

******************************************************************************/
BEGIN
    SET NOCOUNT ON
    -- Procedure body here
END
```

**Important:** Comments placed BEFORE `CREATE PROCEDURE` are not compiled with the procedure and won't be visible in SQL Server Management Studio or other database tools.

### Helper Queries Guidelines

Each helper query should:
- Be commented with the parameter name(s) it helps populate
- Return actual useful values from the database
- Include enough columns to identify the correct value (names, codes, dates)
- **Combine related parameters** when they must match for the procedure to return data

## Output Column Naming

**UPPERCASE for UI-facing procedures only** (`P_INTF__` and views):

```sql
-- P_INTF__ procedures - UPPERCASE output columns (UI requirement)
SELECT emp_name AS EMP_NAME, postn_key AS POSTN_KEY FROM ...

-- All other procedures (P_LOAD__, P_ETL__, P_UNIT__) - lowercase is fine
SELECT emp_cd, postn_key, promotion_id FROM ...
```

**Rationale:** UI team requires UPPERCASE for P_INTF__ outputs due to legacy Adobe Flex naming patterns. Internal procedures don't have this constraint and lowercase is more readable.

**Preserve source column names** rather than renaming:

```sql
-- Correct: Preserve source column names
SELECT pd.REGION_CD, pd.TERR_CD, pd.MKT_CD FROM V_APP__POSTN_DETAIL pd

-- Incorrect: Unnecessary renaming loses traceability
SELECT pd.REGION_CD AS REGION, pd.TERR_CD AS DISTRICT FROM ...

-- Acceptable: Rename only when source name is unclear, document original
SELECT pd.POSTN_LEVEL__OPTION_ID AS LEVEL_ID  -- From APP_POSTN.POSTN_LEVEL__OPTION_ID
```

## Date Formatting

Return dates as VARCHAR in MM/DD/YYYY format to prevent JavaScript timezone issues:

```sql
CONVERT(VARCHAR(10), date_column, 101) AS DATE_COLUMN
```

## Decimal Percentage Pattern

Store and return percentages as decimals (0.80 = 80%):

```sql
-- Data type: NUMERIC(5,4) allows 0.0000 to 1.0000
-- UI multiplies by 100 for display
ON_PACE_PCT NUMERIC(5,4)  -- 0.8000 = 80%
```

## Format Mask Conventions

Use .NET format specifiers for UI formatting:

| Mask | Description | Example |
|------|-------------|---------|
| N0, N1, N2 | Number (0, 1, 2 decimals) | 1,234 |
| C0, C2 | Currency | $1,234.56 |
| P0, P1 | Percent | 85.5% |

Store in `FORMAT_MASK` column, return with data for UI to apply.

## Dynamic SQL Pattern for Pivoting Metrics

When metrics are dynamic (variable count), use dynamic SQL:

```sql
DECLARE @SQL NVARCHAR(MAX) = N''
DECLARE @MetricCount INT

-- Build column list dynamically
SELECT @MetricCount = COUNT(*) FROM APP_PROMOTION_METRIC WHERE PROMOTION_ID = @PromotionId

-- Build SELECT with METRIC_1_*, METRIC_2_*, etc.
SET @SQL = N'SELECT '
-- ... build columns based on metric count

EXEC sp_executesql @SQL, N'@Param1 INT, @Param2 BIGINT', @Param1, @Param2
```

## Single Row Results Pattern

Header procedures return exactly one row with all metrics pivoted:

```sql
-- Column structure for 2-metric promotion:
POSTN_KEY, PROMOTION_NAME, REPORT_AS_OF_DATE,
METRIC_1_NAME, METRIC_2_NAME,
METRIC_1_FORMAT_MASK, METRIC_2_FORMAT_MASK,
METRIC_1_VALUE, METRIC_1_STATUS,
METRIC_2_VALUE, METRIC_2_STATUS,
OVERALL_STATUS, OVERALL_PAYOUT_AMT
```

## Error Handling Pattern

Return empty result set for invalid inputs (don't raise errors):

| Scenario | Expected Behavior |
|----------|-------------------|
| Invalid parameter | Return empty result set |
| Position not found | Return empty result set |
| No data for criteria | Return empty result set |
| NULL metric values | Return NULL in columns |

## Table Naming Conventions

| Prefix | Purpose |
|--------|---------|
| `APP_` | Application/domain tables |
| `ETL_`, `STG_` | ETL staging tables |
| `LOG_` | Logging tables |

## Standard Field Patterns

| Pattern | Description |
|---------|-------------|
| `CREATE_DATE` | Row creation timestamp |
| `MODIFY_DATE` | Last modification timestamp |
| `DELETE_DATE` | Soft delete timestamp (NULL = active) |
| `CREATE__USER_ID` | User who created record |
| `_IND` suffix | BIT indicator fields |
| `_fk` suffix | Foreign key constraints |

## Views and Functions

- Views: `V_APP__`, `V_ETL__`, `V_LOG__` prefixes
- Functions: `F_` prefix

## Code Formatting and Indentation

Use **tabs** for alignment between SQL keywords and their operands. This creates consistent column alignment across statements.

### SQL Keyword Formatting

SQL keywords are followed by tabs to align operands:

```sql
SELECT	column1,
		column2,
		column3
FROM	table_name				t
JOIN	other_table				o	ON	o.id = t.other_id
WHERE	t.status = 'active'
AND		t.delete_date IS NULL
```

### Table Alias Alignment

Table names and aliases are separated by **multiple tabs** to align aliases vertically:

```sql
FROM	app_annual_life_insurance_award		lia
JOIN	app_option							so	ON	lia.status__option_id = so.option_id
JOIN	app_time							t	ON	lia.time_id = t.time_id
```

The `ON` keyword is also tab-separated: `alias	ON	condition`

### LEFT OUTER JOIN Pattern

For LEFT OUTER JOIN, put the keywords on their own line:

```sql
FROM	app_promotion_result				r
JOIN	app_promotion						p	ON	p.promotion_id = r.promotion_id
LEFT OUTER JOIN
		app_promotion_metric				pm	ON	pm.promotion_metric_id = r.promotion_metric_id
WHERE	r.postn_key = @PostnKey
```

### Multi-line JOIN Conditions

When JOIN conditions span multiple lines, align AND under the first condition:

```sql
LEFT OUTER JOIN
		#agent_pc_production				prd	ON	prd.primary_agent_nbr = f.agent_number
												AND	prd.line_of_business = f.line_of_business
												AND	prd.cal_dt BETWEEN t.start_of_period_date AND t.end_of_period_date
```

### GROUP BY and ORDER BY Formatting

Columns on separate lines, aligned with tabs:

```sql
GROUP BY pd.postn_key,
		 p.promotion_id,
		 t.time_id,
		 pm.promotion_metric_id
ORDER BY p.promotion_name,
		 t.end_of_period_date
```

### CTE Formatting

Use CTEs instead of inline subqueries in FROM/JOIN clauses for better readability:

```sql
-- CORRECT: Use CTE for derived tables
;WITH agent_positions AS
(
	SELECT	DISTINCT primary_agent_nbr, postn_key
	FROM	#agents
)
INSERT INTO stg_promotion_result (...)
SELECT	a.postn_key AS postn_key,
		...
FROM	file__pro_home_stretch_baseline		f
JOIN	agent_positions						a	ON	a.primary_agent_nbr = f.agent_number
JOIN	app_promotion						p	ON	p.promotion_id = @PromotionId

-- INCORRECT: Inline subquery makes code hard to read
FROM	file__pro_home_stretch_baseline								f
JOIN	(SELECT DISTINCT primary_agent_nbr, postn_key FROM #agents)	a	ON	a.primary_agent_nbr = f.agent_number
```

Multiple CTEs example:

```sql
;WITH YtdTimeID	AS
(
	SELECT	TOP 1 t.time_id
	FROM	app_time				t
	JOIN	app_option				pto	ON	t.period_type__option_id = pto.option_id
	WHERE	pto.option_cd = 'YTD'
	ORDER BY t.end_of_period_date DESC
),
MthTimeID AS
(
	SELECT	TOP 1 t.time_id
	FROM	app_time				t
	JOIN	app_option				pto	ON	t.period_type__option_id = pto.option_id
	WHERE	pto.option_cd = 'MTH'
	ORDER BY t.end_of_period_date DESC
)
SELECT	...
FROM	YtdTimeID	ytd
JOIN	MthTimeID	mth	ON	...
```

### Key Formatting Rules Summary

| Element | Convention |
|---------|------------|
| Keyword to operand | Tab character(s) |
| Table to alias | Multiple tabs (align aliases vertically) |
| Alias to ON | Tab character |
| AND/OR continuation | Tabs to align under first condition |
| GROUP BY columns | Comma at end, tabs to align continuation |
| LEFT OUTER JOIN | Keywords on own line, table indented below |

### Temp Table and Variable Naming

```sql
-- Temp tables: lowercase with underscores
CREATE TABLE #agents (...)
CREATE TABLE #agent_pc_production (...)

-- Variables: @PascalCase
DECLARE @PromotionId INT
DECLARE @MaxResultDate DATETIME
```

## Projection/Pace Calculation Pattern

When calculating projected values (e.g., ON_PACE_VALUE), use overall daily average from all available data:

```sql
-- Calculate daily average using PTD period's cumulative actual
;WITH daily_averages AS
(
    SELECT	stg.postn_key,
            stg.promotion_metric_id,
            ISNULL(stg.actual_value, 0) AS total_actual,
            DATEDIFF(DAY, @PromotionStartDate, @MaxResultDate) + 1 AS days_elapsed,
            CASE
                WHEN DATEDIFF(DAY, @PromotionStartDate, @MaxResultDate) + 1 > 0
                THEN ISNULL(stg.actual_value, 0) * 1.0 / (DATEDIFF(DAY, @PromotionStartDate, @MaxResultDate) + 1)
                ELSE 0
            END AS daily_average
    FROM	stg_promotion_result		stg
    JOIN	app_time					t	ON	t.time_id = stg.time_id
    JOIN	app_option					o	ON	o.option_id = t.period_type__option_id
    WHERE	o.group_id = @PPTGroupId  -- PTD periods have cumulative total
)
UPDATE	stg
SET		on_pace_value =
        CASE
            WHEN t.end_of_period_date <= @MaxResultDate THEN NULL  -- Completed
            WHEN @MaxResultDate >= t.start_of_period_date THEN     -- Current
                CEILING(da.daily_average * DATEDIFF(DAY, @MaxResultDate, t.end_of_period_date))
            ELSE                                                    -- Future
                CEILING(da.daily_average * (DATEDIFF(DAY, t.start_of_period_date, t.end_of_period_date) + 1))
        END
FROM	stg_promotion_result		stg
JOIN	app_time					t	ON	t.time_id = stg.time_id
JOIN	daily_averages				da	ON	da.postn_key = stg.postn_key
                                        AND	da.promotion_metric_id = stg.promotion_metric_id
```

**Key Principles:**
- Use all available production data for more accurate projections
- Same formula for all period types (PTD and non-PTD)
- PTD actual_value is cumulative, making it ideal for total production
- CEILING for whole-number projections

## Anti-Patterns to Avoid

1. **Inline subqueries in FROM/JOIN**: Use CTEs instead for readability
2. **Tab-aligned column aliases**: Put `AS alias` right after the column, not aligned with tabs
3. **UPPERCASE for internal procedures**: Only P_INTF__ and views need uppercase output columns
4. **Missing column aliases in INSERT...SELECT**: Always alias SELECT columns to match INSERT columns
