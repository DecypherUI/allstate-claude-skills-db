# SSDT Report Procedure Patterns (P_REP__)

Use this skill when creating or modifying `P_REP__` stored procedures that generate executive reports, analytics summaries, or formatted report output.

## Naming Convention

```
P_REP__GET_{REPORT_NAME}           -- Report data retrieval
P_REP__GET_{MODULE}_{DETAIL}       -- Module-specific report
```

## Key Differences from P_INTF__

| Aspect | P_INTF__ | P_REP__ |
|--------|----------|---------|
| Consumer | Frontend UI (AJAX) | Crystal Reports / direct export |
| Column case | UPPERCASE (mandatory) | Mixed case OK (report engine handles display) |
| Pagination | Yes (ROW_NUMBER) | No (full result set) |
| ISNULL wrapping | All columns | Numeric columns only |
| Multiple result sets | Rare | Common (summary + detail) |

## Standard Pattern

```sql
CREATE PROCEDURE [dbo].[P_REP__GET_{REPORT_NAME}]
    @PostnKey       BIGINT,
    @TimeId         INT = -1,
    @StartDate      DATE = NULL,
    @EndDate        DATE = NULL
AS
BEGIN
    SET NOCOUNT ON

    -- Resolve defaults
    IF @TimeId = -1
        SELECT @TimeId = MAX(TIME_ID) FROM APP_TIME_PERIOD WHERE ...

    IF @StartDate IS NULL
        SET @StartDate = DATEADD(YEAR, -1, GETDATE())

    IF @EndDate IS NULL
        SET @EndDate = GETDATE()

    -- Result set 1: Summary
    SELECT
        COUNT(*) AS total_count,
        SUM(ISNULL(amount, 0)) AS total_amount
    FROM {table}
    WHERE TIME_ID = @TimeId
      AND DELETE_DATE IS NULL

    -- Result set 2: Detail
    SELECT
        r.POSTN_KEY,
        r.SUBORD_NAME,
        ISNULL(r.METRIC_1, 0) AS metric_1,
        ISNULL(r.METRIC_2, 0) AS metric_2
    FROM {table} r
    WHERE r.TIME_ID = @TimeId
      AND r.DELETE_DATE IS NULL
    ORDER BY r.SUBORD_NAME
END
```

## Multi-Level Report Pattern

Reports that aggregate across hierarchy levels:

```sql
-- CWD/Manager level: aggregate subordinates
SELECT
    h.SUBORD_NAME,
    h.POSTN_LEVEL_CD,
    SUM(ISNULL(r.METRIC, 0)) AS metric_total,
    COUNT(DISTINCT r.POSTN_KEY) AS agent_count
FROM APP_HIERARCHY h
JOIN {table} r ON r.POSTN_KEY = h.SUBORD_POSTN_KEY
WHERE h.POSTN_KEY = @PostnKey
  AND r.TIME_ID = @TimeId
  AND r.DELETE_DATE IS NULL
GROUP BY h.SUBORD_NAME, h.POSTN_LEVEL_CD
ORDER BY h.SUBORD_NAME
```

## Crystal Reports Integration

- Crystal Reports reads result sets by ordinal position (first = subreport 0, second = subreport 1)
- Parameter names in the procedure must match Crystal Reports parameter names
- Date parameters should accept NULL and default internally (Crystal may not pass them)
- Keep column names stable — renaming breaks Crystal Reports field bindings

## Key Reminders

- Reports often join across multiple modules — use explicit table aliases
- Include `DELETE_DATE IS NULL` on every joined table
- Use `ORDER BY` on detail result sets (Crystal Reports may not sort)
- Avoid dynamic SQL in reports unless absolutely necessary (harder to debug)
