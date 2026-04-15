# SSDT ETL Pipeline Patterns

Use this skill when creating or modifying P_LOAD__ and P_ETL__ stored procedures that move data through the staging-to-production pipeline.

## Pipeline Architecture

```
External Sources (EWSOP000__, FILE__, EXCEL__)
        ↓
   SSIS Packages (extract & stage)
        ↓
   ETL_ Tables (raw extracts)
        ↓
   P_LOAD__STG_* (transform into STG_ tables)
        ↓
   STG_ Tables (staging)
        ↓
   P_LOAD__MOVE_STG_TO_APP / P_LOAD__APP_* (validate & load)
        ↓
   APP_ / PRO_ Tables (production)
```

## P_LOAD__ Procedure Types

### Type 1: Direct Source to APP (TRUNCATE + INSERT)

Simplest pattern — full reload of a target table from source data.

```sql
CREATE PROCEDURE dbo.P_LOAD__APP_MY_METRIC
AS
/**************************************************************************
PROCEDURE:    P_LOAD__APP_MY_METRIC
DESCRIPTION:  Loads MY_METRIC data from external source to APP table.

SAMPLE CALL:
    EXEC P_LOAD__APP_MY_METRIC
***************************************************************************/

-- Step 1: Clear target
TRUNCATE TABLE app_my_metric

-- Step 2: Load from source with transformation
INSERT  app_my_metric
        (postn_key, emp_cd, metric_value, metric_pct, report_date, load_date)
SELECT  h.child__postn_key,
        src.agent_nbr,
        src.total_amt,
        src.total_amt / NULLIF(src.goal_amt, 0),
        src.report_dt,
        GETDATE()
FROM    ewsop000__source_table      src
JOIN    v_app__hierarchy             h   ON src.agent_nbr = h.child__emp_cd
WHERE   h.child_postn_level__option_cd IN ('AGN', 'EFS')
```

**Use when:** Target table is a snapshot that gets fully replaced each load cycle.

### Type 2: Staging to APP (Upsert Pattern)

UPDATE existing rows, then INSERT new rows.

```sql
CREATE PROCEDURE dbo.P_LOAD__APP_PERSON
AS

DECLARE @hierarchyTimeId INT
SELECT  @hierarchyTimeId = time_id FROM f_sec__get_time()

-- Step 1: Clear staging tables
TRUNCATE TABLE stg_person

-- Step 2: Populate staging from multiple sources
INSERT INTO stg_person (business_partner_id, first_name, last_name, emp_cd)
SELECT  DISTINCT bus_ptnr_id, agcy_1st_nm, agcy_lst_nm, agcy_nbr
FROM    ewsop000__ewv_agcy_dim ad
WHERE   ad.agt_ty_cd IN ('41', '06', '40', '08')

INSERT INTO stg_person (business_partner_id, first_name, last_name, emp_cd)
SELECT  DISTINCT bp.bpid, child__first_name, child__last_name, h.child__emp_cd
FROM    v_app__hierarchy            h
JOIN    etl_employee_bpid_rel       bp  ON bp.emp_cd = h.child__emp_cd
WHERE   h.month__time_id = @hierarchyTimeId

-- Step 3: UPDATE existing records
UPDATE  app_person
SET     first_name = s.first_name,
        last_name = s.last_name
FROM    stg_person      s
JOIN    app_person      p   ON p.business_partner_id = s.business_partner_id

-- Step 4: Remove staging rows that already exist
DELETE  stg_person
FROM    stg_person      sp
JOIN    app_person      p   ON p.business_partner_id = sp.business_partner_id

-- Step 5: INSERT only new records
INSERT INTO app_person (business_partner_id, first_name, last_name)
SELECT  DISTINCT s.business_partner_id, s.first_name, s.last_name
FROM    stg_person              s
LEFT OUTER JOIN app_person      p   ON p.business_partner_id = s.business_partner_id
WHERE   p.person_id IS NULL
```

**Use when:** Target table has data that persists across load cycles and needs incremental updates.

### Type 3: Time-Partitioned Load (DELETE by TIME_ID + INSERT)

Replace data for a specific time period only.

```sql
CREATE PROCEDURE dbo.P_LOAD__APP_LEADER_SUMMARY
AS

DECLARE @timeId     INT,
        @reportDate DATETIME

-- Step 1: Determine current reporting period
SELECT  @reportDate = MAX(cal_day_dt)
FROM    ewsop000__source_fact

SELECT  @timeId = t.time_id
FROM    app_time    t
JOIN    app_option  o   ON o.option_id = t.period_type__option_id
WHERE   @reportDate BETWEEN t.start_of_period_date AND t.end_of_period_date
AND     o.option_cd = 'MTH'

-- Step 2: Clear staging
TRUNCATE TABLE stg_leader_summary

-- Step 3: Build staging data with aggregation
INSERT  stg_leader_summary
        (postn_key, time_id, agent_cnt, metric_value, report_date, load_date)
SELECT  ha.parent__postn_key,
        @timeId,
        COUNT(*),
        SUM(s.metric_value),
        @reportDate,
        GETDATE()
FROM    app_hierarchy_all       ha
JOIN    app_postn               pp  ON ha.parent__postn_key = pp.postn_key
JOIN    app_option              ppl ON pp.postn_level__option_id = ppl.option_id
JOIN    app_summary             s   ON ha.child__postn_key = s.postn_key
WHERE   ppl.option_cd IN ('RGN')
AND     s.time_id = @timeId
GROUP BY ha.parent__postn_key

-- Step 4: Delete existing data for this time period
DELETE  app_leader_summary
WHERE   time_id = @timeId

-- Step 5: Insert from staging
INSERT  app_leader_summary
        (postn_key, time_id, agent_cnt, metric_value, report_date, load_date)
SELECT  postn_key, time_id, agent_cnt, metric_value, report_date, GETDATE()
FROM    stg_leader_summary
```

**Use when:** Data is partitioned by time period (monthly snapshots) and each period is reloaded independently.

### Type 4: Hierarchical Rollup

Build metrics at agent level, then roll up through the organizational hierarchy.

```sql
CREATE PROCEDURE dbo.P_LOAD__APP_ROLLUP_METRIC
AS

DECLARE @timeId INT, @hTimeId INT
SELECT  @hTimeId = time_id FROM f_sec__get_time()

-- Step 1: Load agent-level data
TRUNCATE TABLE stg_rollup_metric

INSERT  stg_rollup_metric (postn_key, time_id, metric_value, load_date)
SELECT  child__postn_key, @timeId, SUM(raw_value), GETDATE()
FROM    v_app__hierarchy            h
JOIN    ewsop000__source_data       src ON src.agent_nbr = h.child__emp_cd
WHERE   h.child_postn_level__option_cd IN ('AGN', 'EFS')
AND     h.month__time_id = @hTimeId
GROUP BY child__postn_key

-- Step 2: Roll up to MKT level
INSERT  stg_rollup_metric (postn_key, time_id, metric_value, load_date)
SELECT  h.parent__postn_key, @timeId, SUM(s.metric_value), GETDATE()
FROM    v_app__hierarchy            h
JOIN    stg_rollup_metric           s   ON h.child__postn_key = s.postn_key
WHERE   h.parent_postn_level__option_cd = 'MKT'
AND     h.child_postn_level__option_cd IN ('AGN', 'EFS')
AND     h.month__time_id = @hTimeId
GROUP BY h.parent__postn_key

-- Step 3: Roll up to TAM level
INSERT  stg_rollup_metric (postn_key, time_id, metric_value, load_date)
SELECT  h.parent__postn_key, @timeId, SUM(s.metric_value), GETDATE()
FROM    v_app__hierarchy            h
JOIN    stg_rollup_metric           s   ON h.child__postn_key = s.postn_key
WHERE   h.parent_postn_level__option_cd = 'TAM'
AND     h.child_postn_level__option_cd = 'MKT'
AND     h.month__time_id = @hTimeId
GROUP BY h.parent__postn_key

-- Step 4: Continue up through RGN, CWD...

-- Step 5: Move to production
DELETE app_rollup_metric WHERE time_id = @timeId

INSERT app_rollup_metric (postn_key, time_id, metric_value, report_date, load_date)
SELECT postn_key, time_id, metric_value, GETDATE(), GETDATE()
FROM stg_rollup_metric
```

**Use when:** Metrics are calculated at the leaf level and aggregated upward through the org hierarchy.

## P_ETL__ Procedure Pattern

P_ETL__ procedures extract and transform data, often calling P_INTF__ procedures to get formatted results for downstream consumption (reports, SSIS exports).

```sql
CREATE PROCEDURE dbo.P_ETL__GET_MY_REPORT_DATA @PostnKey BIGINT
AS

-- Step 1: Validate/adjust input
IF (SELECT child_postn_level__option_cd
    FROM v_app__hierarchy
    WHERE child__postn_key = @PostnKey) = 'SUB'
BEGIN
    SELECT TOP 1 @PostnKey = parent__postn_key
    FROM v_app__hierarchy
    WHERE child__postn_key = @PostnKey
    AND parent_postn_level__option_cd = 'AGN'
END

-- Step 2: Set up pagination (get all rows)
DECLARE @Page           INT = 1,
        @PageSize       INT = 999999,
        @ColumnSorting  UDT_SORT_PAGE_DATA

-- Step 3: Capture P_INTF__ output
DECLARE @Result TABLE (
    -- Match full output schema of the P_INTF__ procedure
    COLUMN_1    VARCHAR(100),
    COLUMN_2    NUMERIC(18,4),
    TOTAL_ROWS  INT,
    ROW         INT,
    -- ... pagination metadata columns
)

INSERT @Result
EXEC P_INTF__GET_MY_GRID @PostnKey, @Page, @PageSize, @ColumnSorting

-- Step 4: Transform and return
SELECT  ISNULL(COLUMN_1, '') AS COLUMN_1,
        ISNULL(CONVERT(VARCHAR(30), CONVERT(INT, COLUMN_2)), '') AS COLUMN_2
FROM    @Result
```

## Common ETL Sub-Patterns

### Time Context Retrieval

```sql
DECLARE @timeId INT, @hTimeId INT, @reportDate DATETIME

-- Get current hierarchy time period
SELECT  @hTimeId = time_id FROM f_sec__get_time()

-- Get report date from source data
SELECT  @reportDate = MAX(report_dt) FROM ewsop000__source_table

-- Map report date to monthly time_id
SELECT  @timeId = t.time_id
FROM    app_time    t
JOIN    app_option  o   ON o.option_id = t.period_type__option_id
WHERE   @reportDate BETWEEN t.start_of_period_date AND t.end_of_period_date
AND     o.option_cd = 'MTH'
```

### De-duplication with ROW_NUMBER

```sql
INSERT  etl_agent_data (emp_cd, name, term_date, row)
SELECT  emp_cd, name, term_date,
        ROW_NUMBER() OVER (
            PARTITION BY emp_cd
            ORDER BY term_date DESC, start_date ASC
        ) AS row
FROM    source_table

-- Use only first row per partition
DELETE FROM etl_agent_data WHERE row > 1
```

### Annualization Calculation

```sql
DECLARE @currentProdDayCnt INT, @totalProdDay INT

SELECT  @currentProdDayCnt = COUNT(*)
FROM    etl_production_day
WHERE   production_day BETWEEN DATENAME(YEAR, @reportDate) + '-01-01' AND @reportDate

SELECT  @totalProdDay = COUNT(*)
FROM    etl_production_day
WHERE   production_day BETWEEN DATENAME(YEAR, @reportDate) + '-01-01'
        AND DATENAME(YEAR, @reportDate) + '-12-31'

-- Annualized = YTD * (total_days / current_days)
SELECT  ROUND(ytd_value * 1.0 * @totalProdDay / NULLIF(@currentProdDayCnt, 0), 0) AS annualized_value
```

### On-Pace Weekly Pool for Trend Charts (Daily-Accumulation Programs)

When building weekly pool rows for a stacked bar chart that shows actual vs on-pace,
the pool table must contain ALL weeks in the period (not just through the as-of date).
Each week falls into one of three categories:

```
@AsOfDate = the latest date with source data
@PoolFundingRateDec = POOL_FUNDING_RATE_PCT / 100.0 (read from period table, NEVER hardcoded)
@DailyRate = (TOP 1 TRANSACTIONAL_GDC ORDER BY WEEK_END_DATE DESC WHERE started) / @ElapsedProdDays

COMPLETED week  (END_OF_PERIOD_DATE <= @AsOfDate):
  ACTUAL_POOL_AMT        = running CW GDC through week end * pool_rate
  ON_PACE_POOL_AMT       = 0  (actuals are final — nothing to project)
  IS_INCOMPLETE_PERIOD_IND = 0
  Chart: solid actual bar only

INCOMPLETE week (START_OF_PERIOD_DATE <= @AsOfDate < END_OF_PERIOD_DATE):
  ACTUAL_POOL_AMT        = running CW GDC through @AsOfDate * pool_rate (partial)
  ON_PACE_POOL_AMT       = @DailyRate * prod_days_to_week_end * pool_rate
  IS_INCOMPLETE_PERIOD_IND = 1
  Chart: actual bar + on-pace remainder stacked on top
  The on-pace slice = the remaining working days in that week projected at the daily rate

FUTURE week     (START_OF_PERIOD_DATE > @AsOfDate):
  ACTUAL_POOL_AMT        = 0  (no data yet)
  ON_PACE_POOL_AMT       = @DailyRate * prod_days_to_week_end * pool_rate
  IS_INCOMPLETE_PERIOD_IND = 1
  Chart: entirely on-pace bar (no actual component)
  Each future week is LARGER than the previous because it covers more cumulative prod days
```

The chart P_INTF__ procedure computes:
```sql
COLUMN_1 = ACTUAL_POOL_AMT
COLUMN_2 = CASE WHEN ON_PACE_POOL_AMT > ACTUAL_POOL_AMT
                THEN ON_PACE_POOL_AMT - ACTUAL_POOL_AMT ELSE 0 END
```

**Key rules:**
- On-pace is NEVER computed for completed weeks — actuals are final
- The daily rate uses the most current actual data (including partial incomplete week)
- Each future week must show a GROWING on-pace value (more prod days = higher projection)
- The on-pace slice on the incomplete week equals exactly the remaining working days * daily rate * pool rate
- Percentages (payout rates) are stored as whole numbers (24.0 = 24%), not decimals (0.24)
- Pool funding rate (e.g. 12%) must be read from the period config table, NEVER hardcoded
- **CRITICAL: Never ORDER BY identity/surrogate keys (TIME_ID, etc.)** — always ORDER BY date columns (WEEK_END_DATE, START_OF_PERIOD_DATE, END_OF_PERIOD_DATE). Identity columns are internal keys for record identification only; their sequential order is not guaranteed. Use dates for all ordering, comparison, and range logic.

**Reference implementation:** `P_LOAD__APP_AFS_QUARTERLY_INCENTIVE` in `allstate-database-apt`

### Constraint Validation Before Load

```sql
DECLARE @constraintViolation BIT = 0

;WITH duplicateCheck AS (
    SELECT  ROW_NUMBER() OVER (
                PARTITION BY parent__postn_key, child__postn_key, time_id
                ORDER BY parent__postn_key
            ) AS row_check
    FROM    stg_hierarchy
)
SELECT  @constraintViolation = 1
FROM    duplicateCheck
WHERE   row_check > 1

IF @constraintViolation = 1
BEGIN
    -- Send notification email about constraint violation
    EXEC msdb.dbo.sp_send_dbmail
        @profile_name = 'Awards Management',
        @recipients = 'team@company.com',
        @subject = 'ETL Constraint Violation',
        @body = 'Duplicate records detected in staging hierarchy.',
        @body_format = 'HTML'
END
```

### Temp Table Cleanup

Always drop temp tables at the end of the procedure:

```sql
-- At end of procedure
DROP TABLE #working_data
DROP TABLE #intermediate
DROP TABLE #rollup
```

## Key Conventions

- **TRUNCATE** for staging tables (faster than DELETE, resets identity)
- **DELETE WHERE time_id = @timeId** for time-partitioned production tables
- **GETDATE()** for `load_date` columns (when the ETL ran)
- **No explicit transactions** — P_LOAD__ procedures use implicit auto-commit
- **NULLIF for division safety** — `value / NULLIF(divisor, 0)`
- **ISNULL for NULL defaults** — wrap source columns to prevent NULL propagation
- **Multiple INSERT blocks** for different source systems feeding the same staging table
- **PRINT statements** for ETL monitoring: `PRINT 'Loaded ' + CONVERT(VARCHAR, @@ROWCOUNT) + ' rows'`

## Anti-Patterns

- **Do not** wrap P_LOAD__ procedures in explicit transactions unless doing multi-table atomic operations
- **Do not** use MERGE in load procedures — the codebase uses UPDATE-then-INSERT (upsert) pattern instead
- **Do not** skip staging tables for complex loads — always stage, validate, then move to production
- **Do not** forget to clear staging tables at the start of the procedure
- **Do not** hardcode time_id values — always derive from `f_sec__get_time()` or source data dates
