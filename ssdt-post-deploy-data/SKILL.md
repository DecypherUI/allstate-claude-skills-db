# SSDT Post-Deployment Data Seeding

Use this skill when creating or modifying post-deployment scripts that seed reference data, configuration, or lookup values into SQL Server databases. All patterns must be **idempotent** — safe to run repeatedly without duplicating data.

## File Organization

Post-deployment scripts live in `PostDeploymentScripts/` and are orchestrated by a master script:

```sql
-- Script.PostDeployment.Master.sql
-- Active scripts (deployed):
:r .\Data.AppGroup.sql
:r .\Data.AppOption.sql

-- Inactive scripts (commented out):
--:r .\Data.OldFeature.sql
```

**Naming convention:** `Data.[TableOrFeature].sql`

**Execution order matters** — scripts in the master file run top-to-bottom. Parent tables before child tables (e.g., `Data.AppGroup.sql` before `Data.AppOption.sql`).

## Pattern 1: IF NOT EXISTS (Simple Insert)

Use for inserting rows that should exist exactly once. Best for small reference data sets.

```sql
IF NOT EXISTS (SELECT * FROM app_group WHERE group_cd = 'PRS')
BEGIN
    INSERT INTO app_group (group_cd, short_descr, long_descr, sequence_nbr)
    VALUES ('PRS', 'Status', 'Add Grow Earn promotion status', NULL)
END
```

**When to use:** Single rows or small sets where the natural key is clear.

**With parent-child lookup:**
```sql
IF NOT EXISTS (
    SELECT  *
    FROM    app_group   g
    JOIN    app_option  o   ON o.group_id = g.group_id
    WHERE   g.group_cd = 'PRS' AND o.option_cd = 'PR3'
)
BEGIN
    INSERT INTO app_option (group_id, option_cd, short_descr, long_descr, sequence_nbr)
    SELECT  group_id, 'PR3', 'Earned', NULL, NULL
    FROM    app_group
    WHERE   group_cd = 'PRS'
END
```

**Key points:**
- Check existence using the **natural key** (business-meaningful columns), not surrogate key
- Use `SELECT *` in the EXISTS check — it's optimized by SQL Server to `SELECT 1`
- Always wrap INSERT in BEGIN/END block
- Use `SELECT ... FROM` instead of `VALUES` when you need to look up a foreign key

## Pattern 2: MERGE (Upsert)

Use when rows may need updating on re-deployment (not just inserting if missing).

```sql
MERGE INTO dbo.PRO_AFS_RECOGNITION_BPS AS target
USING (VALUES
    ('1',  18, 36),
    ('2',  18, 42),
    ('3',  18, 54),
    ('4',  18, 66),
    ('4B', 18, 78)
) AS source (TIER, BPS_MIN, BPS_MAX)
ON target.TIER = source.TIER
WHEN MATCHED THEN
    UPDATE SET
        BPS_MIN = source.BPS_MIN,
        BPS_MAX = source.BPS_MAX
WHEN NOT MATCHED THEN
    INSERT (TIER, BPS_MIN, BPS_MAX)
    VALUES (source.TIER, source.BPS_MIN, source.BPS_MAX);
```

**When to use:** Configuration data that may change between releases (thresholds, rates, goals).

**Key points:**
- Always end MERGE with semicolon (`;`)
- `ON` clause uses the natural key for matching
- `WHEN MATCHED` updates non-key columns
- `WHEN NOT MATCHED` inserts new rows
- Use `VALUES` clause for inline data; use a staging table or CTE for larger sets

## Pattern 3: Bulk Insert with IF NOT EXISTS Guard

Use for large reference data sets where the entire table is seeded at once.

```sql
IF NOT EXISTS (SELECT * FROM pro_add_grow_earn_structure)
    INSERT INTO pro_add_grow_earn_structure
            (start_date, end_date, bonus_amt, create_date)
    VALUES  ('03/01/2021', '05/31/2021', 2500, GETDATE()),
            ('06/01/2021', '08/31/2021', 2000, GETDATE()),
            ('09/01/2021', '11/30/2021', 1000, GETDATE())
```

**When to use:** Tables that are fully seeded once and rarely change.

**Key points:**
- Guard checks if table is empty (any rows exist)
- All rows inserted in one statement
- Use `GETDATE()` for audit columns (`CREATE_DATE`)

## Pattern 4: Delete-and-Reload

Use sparingly — only for configuration data that is fully defined in the script and should always match source.

```sql
DELETE FROM app_direct_sale_threshold

INSERT INTO app_direct_sale_threshold (threshold_cd, metric_cd, min_value, max_value)
VALUES
    ('BOUND_AUTO', 'DAILY', 0.5, 2.0),
    ('BOUND_PROP', 'DAILY', 0.3, 1.5),
    ('ONBOARD',    'DAILY', 0.2, 1.0)
```

**When to use:** Small lookup tables where the complete set is always defined in the script.

**Key points:**
- Only for tables with no FK references pointing to them
- Only for small data sets (< 100 rows)
- Never use for tables with IDENTITY columns that other tables reference

## Verification Output

Always add verification output for important data loads:

```sql
DECLARE @RowCount VARCHAR(10)

SELECT @RowCount = CAST(COUNT(*) AS VARCHAR(10))
FROM dbo.PRO_AFS_RECOGNITION_BPS

PRINT '=== PRO_AFS_RECOGNITION_BPS Load Complete ==='
PRINT 'Rows: ' + @RowCount
```

## Handling IDENTITY Columns

When seeding tables with IDENTITY columns and specific ID values:

```sql
SET IDENTITY_INSERT dbo.app_report ON

IF NOT EXISTS (SELECT * FROM app_report WHERE report_id = 1)
    INSERT INTO app_report (report_id, report_name, report_cd, active_ind, create_date)
    VALUES (1, 'Award Grid', 'AWD', 1, GETDATE())

SET IDENTITY_INSERT dbo.app_report OFF
```

**Key points:**
- Only one table can have `IDENTITY_INSERT ON` at a time per session
- Always turn it OFF when done
- Only use when specific ID values matter (e.g., FK references hardcoded elsewhere)

## Adding a New Post-Deploy Script

1. Create the script file: `PostDeploymentScripts/Data.YourTable.sql`
2. Add to the master script: `:r .\Data.YourTable.sql`
3. Place it after any parent table scripts it depends on
4. Add to the `.sqlproj` file: `<None Include="PostDeploymentScripts\Data.YourTable.sql" />`
5. Test by running the script standalone against a populated database (idempotency check)

## Anti-Patterns

- **Do not** use `TRUNCATE TABLE` — it breaks FK constraints and isn't logged for rollback
- **Do not** hardcode IDENTITY values unless FK references require specific IDs
- **Do not** use `SELECT INTO` — it creates new tables, not inserts into existing ones
- **Do not** omit the existence check — the script will fail on duplicate key violations
- **Do not** mix DDL (CREATE/ALTER TABLE) with data seeding — DDL belongs in the main project
- **Do not** use `GETDATE()` for columns that should have stable dates across deployments — use literal dates instead
