# SSDT Hierarchy Query Patterns

Use this skill when working with organizational hierarchy tables (APP_HIERARCHY, APP_HIERARCHY_ALL, APP_POSTN) or writing procedures that traverse, display, or filter by hierarchical relationships.

## Core Tables

### APP_HIERARCHY — Direct Parent-Child Relationships

```
PARENT__POSTN_KEY (BIGINT)  — parent position
CHILD__POSTN_KEY  (BIGINT)  — child position
TIME_ID           (INT)     — temporal version (FK to APP_TIME)
```

Stores **one level only**. To find grandchildren or deeper, use APP_HIERARCHY_ALL.

### APP_HIERARCHY_ALL — Transitive Closure (Pre-Computed)

Same columns as APP_HIERARCHY but contains **all ancestor-descendant pairs**, including self-references for root positions. Built by the hierarchy load procedure.

**Use APP_HIERARCHY_ALL for:** Finding all descendants of a position, span-of-control filtering, rollup aggregation.

**Use APP_HIERARCHY for:** Finding direct children only, tree control navigation.

### APP_POSTN — Position Master

```
POSTN_KEY                (BIGINT)  — unique position identifier
POSTN_LEVEL__OPTION_ID   (INT)    — FK to APP_OPTION (position level code)
```

### APP_POSTN_REL — Position Details Per Time Period

```
POSTN_KEY   (BIGINT)     — FK to APP_POSTN
TIME_ID     (INT)        — FK to APP_TIME
EMP_CD      (VARCHAR 16) — employee holding this position
REGION_CD, TERR_CD, MKT_CD, STATE_CD — location codes
ACTIVE_IND  (BIT)        — whether position is active
```

### V_APP__HIERARCHY — Enriched View

Joins APP_HIERARCHY + APP_POSTN + APP_POSTN_REL + APP_EMPLOYEE + APP_OPTION to provide:
- `parent__postn_key`, `child__postn_key`, `month__time_id`
- `parent_postn_level__option_cd`, `child_postn_level__option_cd`
- `parent__emp_cd`, `child__emp_cd`
- `parent__first_name`, `parent__last_name`, `child__first_name`, `child__last_name`
- `SUBORD_NAME` — formatted display name (level-specific formatting)
- `region_cd`, `terr_cd`, `mkt_cd`, `state_cd`

## Common Query Patterns

### Get Current Time Period

```sql
DECLARE @hTimeId INT
SELECT  @hTimeId = time_id FROM f_sec__get_time()
```

### Find All Descendants of a Position

```sql
SELECT  child__postn_key, child__emp_cd, child_postn_level__option_cd
FROM    v_app__hierarchy
WHERE   parent__postn_key = @PostnKey      -- ancestor position (not in v_app__hierarchy — see note)
AND     month__time_id = @hTimeId
```

For **all descendants** (not just direct children), use APP_HIERARCHY_ALL:

```sql
SELECT  ha.child__postn_key, pr.emp_cd, o.option_cd AS postn_level_cd
FROM    app_hierarchy_all   ha
JOIN    app_postn           p   ON ha.child__postn_key = p.postn_key
JOIN    app_option          o   ON p.postn_level__option_id = o.option_id
JOIN    app_postn_rel       pr  ON ha.child__postn_key = pr.postn_key
JOIN    f_sec__get_time()   t   ON pr.time_id = t.time_id
WHERE   ha.parent__postn_key = @PostnKey
AND     ha.time_id = t.time_id
```

### Find Direct Children Only

```sql
SELECT  h.child__postn_key, pr.emp_cd, o.option_cd
FROM    app_hierarchy       h
JOIN    app_postn           p   ON h.child__postn_key = p.postn_key
JOIN    app_option          o   ON p.postn_level__option_id = o.option_id
JOIN    app_postn_rel       pr  ON h.child__postn_key = pr.postn_key
JOIN    f_sec__get_time()   t   ON pr.time_id = t.time_id AND h.time_id = t.time_id
WHERE   h.parent__postn_key = @PostnKey
```

### Filter by Position Level

```sql
-- Get all AGN (agent) positions under a region
SELECT  ha.child__postn_key, pr.emp_cd
FROM    app_hierarchy_all   ha
JOIN    app_postn           cp  ON ha.child__postn_key = cp.postn_key
JOIN    app_option          co  ON cp.postn_level__option_id = co.option_id
JOIN    app_postn_rel       pr  ON ha.child__postn_key = pr.postn_key
JOIN    f_sec__get_time()   t   ON pr.time_id = t.time_id AND ha.time_id = t.time_id
WHERE   ha.parent__postn_key = @PostnKey
AND     co.option_cd = 'AGN'
```

### Span-of-Control Check

Verify that a user has authority over a given position:

```sql
-- Does @UserPostnKey have @TargetPostnKey in their span?
IF EXISTS (
    SELECT  1
    FROM    app_hierarchy_all   ha
    JOIN    f_sec__get_time()   t   ON ha.time_id = t.time_id
    WHERE   ha.parent__postn_key = @UserPostnKey
    AND     ha.child__postn_key = @TargetPostnKey
)
BEGIN
    -- User has authority
END
```

### Aggregate Metrics Up the Hierarchy

```sql
-- Sum agent-level metrics for each parent position
SELECT  ha.parent__postn_key,
        COUNT(*) AS agent_cnt,
        SUM(m.metric_value) AS total_metric
FROM    app_hierarchy_all       ha
JOIN    app_postn               pp  ON ha.parent__postn_key = pp.postn_key
JOIN    app_option              po  ON pp.postn_level__option_id = po.option_id
JOIN    app_my_metric           m   ON ha.child__postn_key = m.postn_key
JOIN    f_sec__get_time()       t   ON ha.time_id = t.time_id
WHERE   po.option_cd = 'RGN'                    -- aggregate at region level
AND     m.time_id = @timeId
GROUP BY ha.parent__postn_key
```

## Building the Transitive Closure (APP_HIERARCHY_ALL)

This iterative loop expands direct relationships into all ancestor-descendant pairs:

```sql
TRUNCATE TABLE app_hierarchy_all

DECLARE @i INT = 0, @NewPostnCnt INT

CREATE TABLE #completeHierarchy (
    parent__postn_key   BIGINT,
    child__postn_key    BIGINT,
    time_id             INT,
    iteration           INT
)

-- Base case: self-references + direct relationships
INSERT INTO #completeHierarchy (parent__postn_key, child__postn_key, time_id, iteration)
SELECT  child__postn_key, child__postn_key, time_id, 0
FROM    app_hierarchy
UNION
SELECT  p.postn_key, p.postn_key, pr.time_id, 0
FROM    app_postn       p
JOIN    app_postn_rel   pr  ON pr.postn_key = p.postn_key
JOIN    app_option      o   ON o.option_id = p.postn_level__option_id
WHERE   o.option_cd IN ('CWD', 'NA1')      -- root position levels

-- Iterative expansion
WHILE (SELECT COUNT(*)
       FROM #completeHierarchy      h
       JOIN app_hierarchy           h1  ON h1.parent__postn_key = h.child__postn_key
                                       AND h1.time_id = h.time_id
       WHERE iteration = @i) <> 0
BEGIN
    SET @i += 1

    INSERT INTO #completeHierarchy (parent__postn_key, child__postn_key, time_id, iteration)
    SELECT  h.parent__postn_key, h1.child__postn_key, h.time_id, @i
    FROM    #completeHierarchy      h
    JOIN    app_hierarchy           h1  ON h1.parent__postn_key = h.child__postn_key
                                       AND h1.time_id = h.time_id
    WHERE   iteration = @i - 1

    PRINT 'Iteration ' + CONVERT(VARCHAR, @i) + ': ' + CONVERT(VARCHAR, @@ROWCOUNT) + ' new records'

    IF @i = 10 BREAK    -- safety limit (max org depth)
END

-- Persist
INSERT INTO app_hierarchy_all (parent__postn_key, child__postn_key, time_id)
SELECT  DISTINCT parent__postn_key, child__postn_key, time_id
FROM    #completeHierarchy

DROP TABLE #completeHierarchy
```

**Key design decisions:**
- Iterative loop (not recursive CTE) — avoids MAXRECURSION limits
- Safety break at 10 iterations (no org should be deeper)
- Self-references for root positions enable "find everything under CWD" queries
- DISTINCT on final insert removes duplicate paths

## Location Code Assignment (Cascading Down)

Location codes (REGION_CD, TERR_CD, MKT_CD) are assigned at their owning level and cascaded to all descendants:

```sql
-- Step 1: Assign region_cd at RGN level
;WITH myPostns AS (
    SELECT  child__postn_key,
            ROW_NUMBER() OVER (ORDER BY child__postn_key) AS row_num
    FROM    v_app__hierarchy
    WHERE   child_postn_level__option_cd IN ('RGN')
    AND     month__time_id = @TimeId
)
UPDATE  pr
SET     region_cd = RIGHT('000' + CONVERT(VARCHAR, row_num), 3)
FROM    app_postn_rel   pr
JOIN    myPostns        p   ON p.child__postn_key = pr.postn_key

-- Step 2: Cascade region_cd to all descendants
;WITH myPostns AS (
    SELECT  child__postn_key, region_cd
    FROM    v_app__hierarchy
    WHERE   child_postn_level__option_cd IN ('RGN')
    AND     month__time_id = @TimeId
)
UPDATE  pr
SET     region_cd = p.region_cd
FROM    app_hierarchy_all   ha
JOIN    myPostns            p   ON p.child__postn_key = ha.parent__postn_key
JOIN    app_postn_rel       pr  ON pr.postn_key = ha.child__postn_key

-- Step 3: Assign terr_cd at TAM level (partitioned by region)
;WITH myPostns AS (
    SELECT  child__postn_key,
            ROW_NUMBER() OVER (PARTITION BY region_cd ORDER BY child__postn_key) AS row_num
    FROM    v_app__hierarchy
    WHERE   child_postn_level__option_cd IN ('TAM')
    AND     month__time_id = @TimeId
)
UPDATE  pr
SET     terr_cd = CHAR(row_num + 65)   -- A, B, C, ...
FROM    app_postn_rel   pr
JOIN    myPostns        p   ON p.child__postn_key = pr.postn_key

-- Step 4: Cascade terr_cd down, then repeat for MKT level
```

## SUBORD_NAME Formatting by Position Level

The view V_APP__HIERARCHY formats display names based on position level:

```sql
CASE
    WHEN option_cd IN ('RGN')
        THEN region_cd + ' (' + last_name + ', ' + first_name + ')'
    WHEN option_cd IN ('TAM')
        THEN dbo.F_CONVERT_TO_PROPER_CASE(last_name + ', ' + first_name)
    WHEN option_cd IN ('MKT')
        THEN dbo.F_CONVERT_TO_PROPER_CASE(last_name + ', ' + first_name)
    WHEN option_cd IN ('AGN', 'SUB', 'EFS')
        THEN dbo.F_CONVERT_TO_PROPER_CASE(last_name + ', ' + first_name)
             + ' (' + emp_cd + ')'
END AS SUBORD_NAME
```

## Tree Control Pattern

UI tree controls use two queries — one for the root node, one for expanding children:

```sql
-- First call: get user's root positions
SELECT  postn_key, display_name, postn_level_cd, has_children
FROM    ...
WHERE   user_id = @UserId

-- Subsequent calls: get children of expanded node
SELECT  h.child__postn_key AS postn_key,
        formatted_name AS display_name,
        o.option_cd AS postn_level_cd,
        CASE WHEN EXISTS (
            SELECT 1 FROM app_hierarchy h2
            WHERE h2.parent__postn_key = h.child__postn_key
            AND h2.time_id = h.time_id
        ) THEN 'true' ELSE 'false' END AS has_children
FROM    app_hierarchy       h
JOIN    app_postn_rel       pr  ON h.child__postn_key = pr.postn_key
                               AND h.time_id = pr.time_id
WHERE   h.parent__postn_key = @ParentPostnKey
```

## Anti-Patterns

- **Do not** use recursive CTEs for hierarchy traversal in production procedures — use APP_HIERARCHY_ALL (pre-computed)
- **Do not** query APP_HIERARCHY when you need all descendants — that only has direct children
- **Do not** forget the TIME_ID join — hierarchy relationships are temporal
- **Do not** hardcode position level codes — use APP_OPTION lookups via `option_cd`
- **Do not** assume position keys are sequential — POSTN_KEY values encode the position level
- **Do not** sort by `AGENCY_NAME` in ROW_NUMBER() — use `SUBORD_NAME` or source column names (SELECT aliases can't be used in OVER clause)
