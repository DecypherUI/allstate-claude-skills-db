# SSDT Dynamic SQL Patterns

Use this skill when implementing pagination, multi-column sorting, dynamic pivoting, or any pattern requiring runtime SQL construction in SQL Server stored procedures.

## Pagination with Sorting UDT

This is the standard pattern for grid/list endpoints that support server-side paging and sorting.

### UDT Definition

```sql
CREATE TYPE [dbo].[UDT_SORT_PAGE_DATA] AS TABLE
(
    COLUMN_NAME     VARCHAR(100),
    SORT_DIRECTION  VARCHAR(4)       -- 'ASC' or 'DESC'
)
```

### Procedure Signature

```sql
CREATE PROCEDURE dbo.P_INTF__GET_MY_GRID
    @PostnKey           BIGINT,
    @Page               INT = 1,
    @PageSize           INT = 999999,
    @ColumnSorting      UDT_SORT_PAGE_DATA READONLY
AS
```

**Defaults:** `@Page = 1` and `@PageSize = 999999` (effectively no paging when omitted).

### Building the ORDER BY Clause

```sql
DECLARE @i              INT = 0,
        @SqlCmd          VARCHAR(MAX) = '',
        @SortSqlCmd      VARCHAR(MAX),
        @SortColName     VARCHAR(100),
        @SortDirection   VARCHAR(4),
        @SortIteration   INT = 0

-- Build dynamic ORDER BY from UDT rows
IF EXISTS (SELECT * FROM @ColumnSorting)
BEGIN
    DECLARE rs CURSOR FOR
        SELECT  column_name, sort_direction
        FROM    @ColumnSorting

    OPEN rs
    FETCH NEXT FROM rs INTO @SortColName, @SortDirection

    WHILE @@FETCH_STATUS = 0
    BEGIN
        SET @SortIteration = @SortIteration + 1
        IF @SortIteration > 1
            SET @SortSqlCmd = @SortSqlCmd + ', '

        SET @SortSqlCmd = ISNULL(@SortSqlCmd, '') + @SortColName + ' ' + ISNULL(@SortDirection, '')

        FETCH NEXT FROM rs INTO @SortColName, @SortDirection
    END

    CLOSE rs
    DEALLOCATE rs
END
```

### Paging with ROW_NUMBER

```sql
-- Count total rows from intermediate temp table
SELECT  @i = COUNT(*)
FROM    #tblresult

-- Build paged result with ROW_NUMBER
SET @SqlCmd = '
SELECT * INTO #tblFinalResults
FROM (
    SELECT  *,
            ' + CONVERT(VARCHAR, @i) + ' AS TOTAL_ROWS,
            ROW_NUMBER() OVER (ORDER BY ' + ISNULL(@SortSqlCmd, 'LAST_NAME, FIRST_NAME') + ') AS ROW
    FROM    #tblresult
) t
WHERE   row BETWEEN ((' + CONVERT(VARCHAR, @Page) + ' - 1) * ' + CONVERT(VARCHAR, @PageSize) + ') + 1
    AND ' + CONVERT(VARCHAR, @Page) + ' * ' + CONVERT(VARCHAR, @PageSize) + '

SELECT  t.*,
        (SELECT MIN(row) FROM #tblFinalResults) AS MIN_ROW_SHOWN,
        (SELECT MAX(row) FROM #tblFinalResults) AS MAX_ROW_SHOWN,
        CEILING(total_rows / (' + CONVERT(VARCHAR, @PageSize) + ' * 1.0)) AS TOTAL_PAGES,
        ' + CONVERT(VARCHAR, @Page) + ' AS CURRENT_PAGE
FROM    #tblFinalResults t
ORDER BY row'

EXEC(@SqlCmd)
```

### Pagination Metadata Columns

Every paginated result set returns these columns:

| Column | Type | Description |
|--------|------|-------------|
| `TOTAL_ROWS` | INT | Total matching rows (before paging) |
| `ROW` | INT | Row number within sorted result |
| `MIN_ROW_SHOWN` | INT | First row number on current page |
| `MAX_ROW_SHOWN` | INT | Last row number on current page |
| `TOTAL_PAGES` | INT | Total page count |
| `CURRENT_PAGE` | INT | Current page number |

### Sample Call with Sort Parameters

```sql
DECLARE @ColumnSorting UDT_SORT_PAGE_DATA

INSERT  @ColumnSorting
VALUES  ('LAST_NAME', 'ASC'),
        ('FIRST_NAME', 'ASC')

EXEC P_INTF__GET_MY_GRID
    @PostnKey = 12345,
    @Page = 1,
    @PageSize = 25,
    @ColumnSorting = @ColumnSorting
```

### Full Procedure Pattern

```sql
CREATE PROCEDURE dbo.P_INTF__GET_MY_GRID
    @PostnKey           BIGINT,
    @Page               INT = 1,
    @PageSize           INT = 999999,
    @ColumnSorting      UDT_SORT_PAGE_DATA READONLY
AS
/**************************************************************************
PROCEDURE:    P_INTF__GET_MY_GRID
DESCRIPTION:  Returns paginated grid data with dynamic sorting.

SAMPLE CALL:
    DECLARE @ColumnSorting UDT_SORT_PAGE_DATA
    INSERT @ColumnSorting VALUES ('LAST_NAME', 'ASC')
    EXEC P_INTF__GET_MY_GRID @PostnKey = 12345, @Page = 1, @PageSize = 25, @ColumnSorting = @ColumnSorting
***************************************************************************/

-- Null-safe defaults
IF @Page IS NULL SET @Page = 1
IF @PageSize IS NULL SET @PageSize = 999999

-- Step 1: Build core result into temp table
SELECT  col1    AS COLUMN_1,
        col2    AS COLUMN_2
INTO    #tblresult
FROM    my_table
WHERE   postn_key = @PostnKey

-- Step 2: Build sort clause (cursor over UDT)
DECLARE @i INT = 0, @SqlCmd VARCHAR(MAX) = '', @SortSqlCmd VARCHAR(MAX),
        @SortColName VARCHAR(100), @SortDirection VARCHAR(4), @SortIteration INT = 0

IF EXISTS (SELECT * FROM @ColumnSorting)
BEGIN
    DECLARE rs CURSOR FOR SELECT column_name, sort_direction FROM @ColumnSorting
    OPEN rs
    FETCH NEXT FROM rs INTO @SortColName, @SortDirection
    WHILE @@FETCH_STATUS = 0
    BEGIN
        SET @SortIteration = @SortIteration + 1
        IF @SortIteration > 1 SET @SortSqlCmd = @SortSqlCmd + ', '
        SET @SortSqlCmd = ISNULL(@SortSqlCmd, '') + @SortColName + ' ' + ISNULL(@SortDirection, '')
        FETCH NEXT FROM rs INTO @SortColName, @SortDirection
    END
    CLOSE rs
    DEALLOCATE rs
END

-- Step 3: Page and return
SELECT @i = COUNT(*) FROM #tblresult

SET @SqlCmd = '
SELECT * INTO #tblFinalResults
FROM (
    SELECT *, ' + CONVERT(VARCHAR, @i) + ' AS TOTAL_ROWS,
           ROW_NUMBER() OVER (ORDER BY ' + ISNULL(@SortSqlCmd, 'COLUMN_1') + ') AS ROW
    FROM #tblresult
) t
WHERE row BETWEEN ((' + CONVERT(VARCHAR, @Page) + ' - 1) * ' + CONVERT(VARCHAR, @PageSize) + ') + 1
  AND ' + CONVERT(VARCHAR, @Page) + ' * ' + CONVERT(VARCHAR, @PageSize) + '
SELECT t.*,
    (SELECT MIN(row) FROM #tblFinalResults) AS MIN_ROW_SHOWN,
    (SELECT MAX(row) FROM #tblFinalResults) AS MAX_ROW_SHOWN,
    CEILING(total_rows / (' + CONVERT(VARCHAR, @PageSize) + ' * 1.0)) AS TOTAL_PAGES,
    ' + CONVERT(VARCHAR, @Page) + ' AS CURRENT_PAGE
FROM #tblFinalResults t
ORDER BY row'

EXEC(@SqlCmd)
```

## Dynamic SQL with sp_executesql

Use `sp_executesql` for parameterized dynamic SQL — safer than `EXEC()` for user-supplied values.

### Basic Pattern

```sql
DECLARE @SQL        NVARCHAR(MAX),
        @ParamDef   NVARCHAR(500),
        @TableName  NVARCHAR(256)

SET @SQL = N'DELETE FROM dbo.' + QUOTENAME(@TableName) + N' WHERE postn_key = @PKey'
SET @ParamDef = N'@PKey BIGINT'

EXEC sp_executesql @SQL, @ParamDef, @PKey = @PostnKey
```

**Key points:**
- Use `NVARCHAR` for SQL strings (required by sp_executesql)
- Use `QUOTENAME()` for object names (prevents SQL injection)
- Define parameter list with `@ParamDef`
- Pass parameter values by name

### Dynamic Object Iteration

For operations across multiple tables (e.g., cleanup by convention):

```sql
DECLARE @TableName  NVARCHAR(256)
DECLARE @SQL        NVARCHAR(MAX)

DECLARE table_cursor CURSOR FOR
    SELECT  t.name
    FROM    sys.columns c
    JOIN    sys.tables  t   ON c.object_id = t.object_id
    WHERE   c.name = 'postn_key'
    AND     t.name NOT IN ('app_postn', 'app_postn_rel')
    ORDER BY t.name

OPEN table_cursor
FETCH NEXT FROM table_cursor INTO @TableName

WHILE @@FETCH_STATUS = 0
BEGIN
    SET @SQL = N'DELETE FROM dbo.' + QUOTENAME(@TableName) + N' WHERE postn_key < 0'
    EXEC sp_executesql @SQL
    FETCH NEXT FROM table_cursor INTO @TableName
END

CLOSE table_cursor
DEALLOCATE table_cursor
```

### Debug Mode

Add a `@Debug` parameter to print SQL instead of (or before) executing:

```sql
CREATE PROCEDURE dbo.P_MY_PROC
    @PostnKey   BIGINT,
    @Debug      BIT = 0
AS

DECLARE @SQL NVARCHAR(MAX) = N'SELECT * FROM dbo.my_table WHERE postn_key = @PKey'

IF @Debug = 1 PRINT @SQL

EXEC sp_executesql @SQL, N'@PKey BIGINT', @PKey = @PostnKey
```

## Dynamic Pivot Pattern

For procedures that pivot a variable number of columns (e.g., monthly metrics):

```sql
DECLARE @PivotCols  NVARCHAR(MAX),
        @SelectCols NVARCHAR(MAX),
        @SQL        NVARCHAR(MAX)

-- Build column lists dynamically from data
SELECT  @PivotCols = STRING_AGG(QUOTENAME(period_name), ', ') WITHIN GROUP (ORDER BY period_seq),
        @SelectCols = STRING_AGG('ISNULL(' + QUOTENAME(period_name) + ', 0) AS ' + QUOTENAME(period_name), ', ')
                      WITHIN GROUP (ORDER BY period_seq)
FROM    (SELECT DISTINCT period_name, period_seq FROM #metrics) p

SET @SQL = N'
SELECT  postn_key, agent_name, ' + @SelectCols + N'
FROM (
    SELECT  postn_key, agent_name, period_name, metric_value
    FROM    #metrics
) src
PIVOT (
    SUM(metric_value)
    FOR period_name IN (' + @PivotCols + N')
) pvt
ORDER BY agent_name'

EXEC sp_executesql @SQL
```

**Key points:**
- Use `STRING_AGG` (SQL Server 2017+) or cursor-based concatenation for column lists
- Wrap pivot columns in `ISNULL(..., 0)` to prevent NULL in output
- Use `QUOTENAME()` for all dynamically-generated column names

## Error Handling in Dynamic SQL

```sql
BEGIN TRY
    EXEC sp_executesql @SQL, @ParamDef, @Param1 = @Value1
END TRY
BEGIN CATCH
    DECLARE @ErrorMsg VARCHAR(MAX) = ERROR_MESSAGE()
    IF @Debug = 1 PRINT 'Failed SQL: ' + @SQL
    RAISERROR(@ErrorMsg, 16, 1)
END CATCH
```

## Anti-Patterns

- **Do not** concatenate user input directly into SQL strings — use `sp_executesql` with parameters
- **Do not** use `EXEC()` when parameters are involved — it doesn't support parameterization
- **Do not** forget `QUOTENAME()` for dynamic object names — prevents injection and handles special characters
- **Do not** use `VARCHAR` for `sp_executesql` SQL strings — it requires `NVARCHAR`
- **Do not** build sort clauses from user input without validating against known column names
- **Do not** forget to close and deallocate cursors — leaked cursors consume server resources
