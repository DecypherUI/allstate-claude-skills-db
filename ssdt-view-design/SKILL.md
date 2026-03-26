# SSDT View Design Patterns

Use this skill when creating or modifying SQL Server views in an SSDT project. Views provide a stable abstraction layer over tables, especially for cross-module queries and reporting.

## Naming Convention

```
V_APP__{VIEW_NAME}     -- Application/domain views
V_ETL__{VIEW_NAME}     -- ETL layer views
V_LOG__{VIEW_NAME}     -- Logging views
```

Note the **double underscore** between prefix and name (same pattern as stored procedures).

## When to Use Views

✅ **Use views for:**
- Cross-table joins reused by multiple procedures
- Flattening hierarchy lookups for reporting
- Providing a stable column contract when underlying tables change
- Simplifying complex ETL source queries

❌ **Do NOT use views for:**
- Simple single-table queries (just query the table directly)
- Business logic with conditional branching (use a procedure)
- Anything requiring parameters (views can't accept parameters)

## Standard View Pattern

```sql
CREATE VIEW [dbo].[V_APP__{NAME}]
AS
    SELECT
        t.PRIMARY_KEY_COL,
        t.COLUMN_1,
        t.COLUMN_2,
        ISNULL(t.NULLABLE_COL, '') AS NULLABLE_COL,
        r.RELATED_FIELD
    FROM APP_{TABLE} t
    LEFT JOIN APP_{RELATED} r
        ON r.FK_COL = t.PK_COL
        AND r.DELETE_DATE IS NULL
    WHERE t.DELETE_DATE IS NULL
```

## Key Rules

- Always include `DELETE_DATE IS NULL` on every table in the view (soft delete filter)
- Use `LEFT JOIN` for optional relationships (never `INNER JOIN` unless the relationship is guaranteed)
- Column aliases should be UPPERCASE (consistent with P_INTF__ output convention)
- Prefix all columns with table alias to avoid ambiguity
- Do NOT use `ORDER BY` in views (SQL Server doesn't guarantee order without `TOP` — let the consumer sort)
- Do NOT use `SELECT *` — explicitly list all columns
- `ISNULL` wrap nullable columns that consumers expect to be non-null

## Hierarchy Flattening View Pattern

```sql
CREATE VIEW [dbo].[V_APP__HIERARCHY_FLAT]
AS
    SELECT
        h.POSTN_KEY,
        h.SUBORD_POSTN_KEY,
        p.POSTN_LEVEL_CD,
        p.EMP_CD,
        ISNULL(p.FIRST_NAME + ' ' + p.LAST_NAME, '') AS FULL_NAME,
        p.NTID
    FROM APP_HIERARCHY h
    JOIN APP_POSTN p
        ON p.POSTN_KEY = h.SUBORD_POSTN_KEY
        AND p.DELETE_DATE IS NULL
    WHERE h.DELETE_DATE IS NULL
```

## SSDT Project Integration

Add view files to the project at:
```
Application/Database/dbo/Views/V_APP__{NAME}.sql
```

Add to `.sqlproj`:
```xml
<Build Include="dbo\Views\V_APP__{NAME}.sql" />
```

## Key Reminders

- Views in SSDT participate in dependency tracking — the build will fail if referenced tables don't exist
- Avoid nested views (view referencing view) — they're hard to debug and optimize
- Document the view's purpose in a header comment (same format as stored procedure headers)
- If a view becomes complex (>50 lines), consider whether it should be a procedure instead
