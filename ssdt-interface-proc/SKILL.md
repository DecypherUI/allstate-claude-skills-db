# SSDT Interface Procedure Patterns (P_INTF__)

Use this skill when creating or modifying `P_INTF__` stored procedures that serve data to the frontend UI. These are the most common procedure type in the codebase and follow strict output conventions.

## Naming Convention

```
P_INTF__GET_{MODULE}_{WHAT}        -- Read/query
P_INTF__SET_{MODULE}_{WHAT}        -- Create/update
P_INTF__DELETE_{MODULE}_{WHAT}     -- Soft delete
```

## Standard Parameters

```sql
-- Read procedures (grids/dashboards)
@PostnKey       BIGINT,
@Userid         INT,
@TimeId         INT = -1,           -- -1 = current/default

-- Paginated grids add:
@Page           INT = 1,
@PageSize       INT = 999999,
@ColumnSorting  UDT_SORT_PAGE_DATA READONLY

-- Update procedures add:
@ModifyUserId   INT
```

## Output Column Rules

- **UPPERCASE** column aliases — mandatory for all `P_INTF__` output (UI framework requirement)
- Wrap all numeric outputs: `ISNULL(column, 0) AS COLUMN_NAME`
- Wrap all string outputs: `ISNULL(column, '') AS COLUMN_NAME`
- Use `NULLIF` for division safety: `ISNULL(a / NULLIF(b, 0), 0)`
- Preserve source column names where possible (don't rename unless necessary)

## Empty Result Set Pattern

When input is invalid (bad postn_key, no access), return an **empty result set** — never throw an exception:

```sql
IF @PostnKey IS NULL OR @PostnKey = 0
BEGIN
    SELECT TOP 0
        CAST(NULL AS BIGINT) AS POSTN_KEY,
        CAST(NULL AS VARCHAR(100)) AS SUBORD_NAME
    RETURN
END
```

## Dashboard Procedure Pattern

```sql
CREATE PROCEDURE [dbo].[P_INTF__GET_{MODULE}_DASHBOARD]
    @PostnKey       BIGINT,
    @Userid         INT,
    @TimeId         INT = -1
AS
BEGIN
    SET NOCOUNT ON

    -- Resolve default time_id if needed
    IF @TimeId = -1
        SELECT @TimeId = MAX(TIME_ID) FROM APP_TIME_PERIOD WHERE ...

    SELECT
        ISNULL(r.METRIC_1, 0)          AS METRIC_1,
        ISNULL(r.METRIC_2, 0)          AS METRIC_2,
        ISNULL(r.STATUS_CD, '')         AS STATUS,
        r.RESULTS_AS_OF_DATE            AS RESULTS_AS_OF_DATE
    FROM PRO_{MODULE} r
    WHERE r.POSTN_KEY = @PostnKey
      AND r.TIME_ID = @TimeId
      AND r.DELETE_DATE IS NULL
END
```

## Grid Procedure Pattern (with pagination)

```sql
CREATE PROCEDURE [dbo].[P_INTF__GET_{MODULE}_GRID]
    @PostnKey       BIGINT,
    @Userid         INT,
    @TimeId         INT = -1,
    @Page           INT = 1,
    @PageSize       INT = 999999,
    @ColumnSorting  UDT_SORT_PAGE_DATA READONLY
AS
BEGIN
    SET NOCOUNT ON

    -- Build sort clause from UDT
    DECLARE @SortClause NVARCHAR(MAX) = ''
    SELECT @SortClause = @SortClause + COLUMN_NAME + ' ' + SORT_DIRECTION + ', '
    FROM @ColumnSorting
    ORDER BY SORT_ORDER

    IF @SortClause = ''
        SET @SortClause = '[SUBORD_NAME] ASC, '

    SET @SortClause = LEFT(@SortClause, LEN(@SortClause) - 1)

    -- Dynamic SQL with pagination
    DECLARE @SQL NVARCHAR(MAX) = '
    ;WITH cte AS (
        SELECT
            ROW_NUMBER() OVER (ORDER BY ' + @SortClause + ') AS ROW_NUM,
            COUNT(*) OVER() AS TOTAL_ROWS,
            ISNULL(r.FIELD_1, 0) AS FIELD_1,
            ISNULL(r.FIELD_2, '''') AS FIELD_2
        FROM {source} r
        WHERE r.DELETE_DATE IS NULL
    )
    SELECT
        *,
        TOTAL_ROWS,
        @Page AS CURRENT_PAGE,
        @PageSize AS PAGE_SIZE,
        CEILING(CAST(TOTAL_ROWS AS FLOAT) / @PageSize) AS TOTAL_PAGES,
        ((@Page - 1) * @PageSize) + 1 AS MIN_ROW_SHOWN,
        CASE WHEN @Page * @PageSize > TOTAL_ROWS THEN TOTAL_ROWS
             ELSE @Page * @PageSize END AS MAX_ROW_SHOWN
    FROM cte
    WHERE ROW_NUM BETWEEN ((@Page - 1) * @PageSize) + 1 AND @Page * @PageSize
    '

    EXEC sp_executesql @SQL,
        N'@Page INT, @PageSize INT',
        @Page, @PageSize
END
```

## Update Procedure Pattern

```sql
CREATE PROCEDURE [dbo].[P_INTF__SET_{MODULE}_{FIELD}]
    @PostnKey       BIGINT,
    @Userid         INT,
    @NewValue       VARCHAR(100)
AS
BEGIN
    SET NOCOUNT ON

    BEGIN TRY
        UPDATE {table}
        SET FIELD = @NewValue,
            MODIFY_DATE = GETDATE(),
            MODIFY__USER_ID = @Userid
        WHERE POSTN_KEY = @PostnKey
          AND DELETE_DATE IS NULL
    END TRY
    BEGIN CATCH
        -- Log error but don't throw to UI
        SELECT ERROR_MESSAGE() AS ERROR_MSG
    END CATCH
END
```

## Key Reminders

- `ROW_NUMBER() OVER (ORDER BY ...)` cannot reference SELECT aliases — use the actual column name or expression
- Default sort should use `[SUBORD_NAME]` (bracketed) for column names that might conflict with reserved words
- Always include `SET NOCOUNT ON` at the top
- Use `DELETE_DATE IS NULL` filter on all queries (soft delete pattern)
- Time period resolution: `@TimeId = -1` means "use the latest/current period"
