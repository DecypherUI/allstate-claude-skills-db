# SSDT Security Model Patterns

Use this skill when working with authentication, authorization, procedure permissions, or span-of-control logic in P_SEC__ and related procedures.

## Architecture Overview

```
User Login (NTID)
    ↓
P_SEC__GET_USER                 — Validates user, returns user_type
    ↓
P_SEC__GET_USER_POSTN           — Returns user's positions with hierarchy context
    ↓
P_SEC__GET_PROCEDURE_PERMISSION — Returns list of procedures user can execute
    ↓
P_INTF__GET_TREE_CONTROL        — Returns hierarchy tree based on user's positions
    ↓
Span-of-Control Filtering      — All data queries filter by user's postn_key
```

## Core Tables

### APP_USER — User Accounts

```sql
USER_ID                 INT IDENTITY NOT NULL,  -- surrogate key
USER_NAME               VARCHAR(20) NOT NULL,   -- network ID (NTID)
USER_TYPE__OPTION_ID    INT NOT NULL,           -- FK to APP_OPTION (role)
ACTIVE_IND              BIT NOT NULL,           -- must be 1 for login
DISPLAY_NAME            VARCHAR(100),
NOTIFICATION_ADMIN_IND  BIT,
LAST_LOGIN_DATE         DATETIME,
-- audit columns...
```

### APP_USER_POSTN_REL — User-to-Position Assignments

Links users to one or more positions in the hierarchy. A user can have multiple positions (e.g., an AGN who is also partnership-assigned).

### APP_PROCEDURE_PERMISSION — Procedure Access Control

```sql
PROCEDURE_PERMISSION    INT IDENTITY NOT NULL,
PROCEDURE_NAME          VARCHAR(100) NOT NULL,  -- stored procedure name
USER_TYPE__OPTION_ID    INT,                    -- role-based access (NULL = N/A)
USER_ID                 INT,                    -- user-specific access (NULL = N/A)
CREATE_DATE             DATETIME NOT NULL,
DELETE_DATE             DATETIME,               -- soft delete
```

**Dual-mode permissions:** A procedure can be granted by role (USER_TYPE__OPTION_ID) OR by specific user (USER_ID). Either match grants access.

## P_SEC__ Procedure Patterns

### User Authentication

```sql
CREATE PROCEDURE dbo.P_SEC__GET_USER @UserName VARCHAR(20)
AS
/**************************************************************************
PROCEDURE:    P_SEC__GET_USER
DESCRIPTION:  Validates user credentials and returns user profile.

SAMPLE CALL:
    EXEC P_SEC__GET_USER @UserName = 'jsmith'
***************************************************************************/

SELECT  u.*,
        uo.option_cd AS USER_TYPE__OPTION_CD
FROM    app_user    u
JOIN    app_option  uo  ON uo.option_id = u.user_type__option_id
WHERE   u.user_name = @UserName
AND     u.active_ind = 1
```

**Key points:**
- Only returns active users (`active_ind = 1`)
- Joins APP_OPTION to resolve user type code
- Returns empty result set if user not found (no error raised)

### Procedure Permission Check

```sql
CREATE PROCEDURE dbo.P_SEC__GET_PROCEDURE_PERMISSION @UserName VARCHAR(25)
AS

DECLARE @UserTypeOptionId   INT,
        @UserId             INT

SELECT  @UserId = u.user_id,
        @UserTypeOptionId = u.user_type__option_id
FROM    app_user u WITH(NOLOCK)
WHERE   u.user_name = @UserName

SELECT  p.procedure_name
FROM    app_procedure_permission p
WHERE   p.delete_date IS NULL
AND     (   ISNULL(p.user_id, -1) = @UserId
        OR  ISNULL(p.user_type__option_id, -1) = @UserTypeOptionId)
```

**Key points:**
- `WITH(NOLOCK)` for read-only lookup performance
- `ISNULL(column, -1)` pattern to handle NULL in OR comparison
- Soft delete filter: `delete_date IS NULL`
- Returns procedure names the user is authorized to execute

### User Position Resolution

```sql
CREATE PROCEDURE dbo.P_SEC__GET_USER_POSTN @UserID INT
AS

SELECT  u.USER_ID,
        u.USER_NAME,
        uto.option_cd AS USER_TYPE__OPTION_CD,
        t.TIME_ID,
        CONVERT(VARCHAR, ur.POSTN_KEY) AS POSTN_KEY,
        o.option_cd AS POSTN_LEVEL__OPTION_CD,

        -- Session flags
        @FirstLoginInd AS SESSION_FIRST_LOGIN_IND,
        ISNULL(u.notification_admin_ind, 0) AS SESSION_NOTIFICATION_ADMIN_IND,

        -- Position ordering for UI
        ROW_NUMBER() OVER (
            ORDER BY CASE
                WHEN o.option_cd = 'EAH' THEN -2        -- EA Head first
                WHEN u.user_name = pr.emp_cd THEN -1     -- Own position second
                ELSE o.sequence_nbr                       -- Then by level sequence
            END,
            e.last_name, e.first_name
        ) AS SEQUENCE_NBR
FROM    app_user_postn_rel  ur
JOIN    app_user            u   ON u.user_id = ur.user_id
JOIN    app_postn           p   ON p.postn_key = ur.postn_key
JOIN    app_postn_rel       pr  ON pr.postn_key = p.postn_key
JOIN    app_employee        e   ON e.emp_cd = pr.emp_cd
JOIN    f_sec__get_time()   t   ON t.time_id = pr.time_id
JOIN    app_option          o   ON o.option_id = p.postn_level__option_id
WHERE   ur.user_id = @UserID
AND     ur.active_ind = 1
```

**Key points:**
- User can have multiple positions (multi-row result)
- ROW_NUMBER ordering: EAH positions first, own position second, then by hierarchy level
- Session flags computed: first login of day, notification admin, BPM access
- `f_sec__get_time()` provides current time period context

## Span-of-Control Pattern

Every data-returning P_INTF__ procedure filters by the user's position key to enforce span-of-control:

```sql
CREATE PROCEDURE dbo.P_INTF__GET_MY_DASHBOARD
    @PostnKey BIGINT
AS

-- User only sees data for positions under their span
SELECT  m.metric_value, m.metric_name
FROM    app_hierarchy_all   ha
JOIN    app_my_metric       m   ON ha.child__postn_key = m.postn_key
JOIN    f_sec__get_time()   t   ON ha.time_id = t.time_id
WHERE   ha.parent__postn_key = @PostnKey    -- user's position
AND     m.time_id = @timeId
```

**The @PostnKey parameter is the security boundary.** The UI passes the user's assigned position, and the procedure only returns data for that position's descendants via APP_HIERARCHY_ALL.

### Span Validation

To verify a target position is within a user's span:

```sql
IF NOT EXISTS (
    SELECT  1
    FROM    app_hierarchy_all   ha
    JOIN    f_sec__get_time()   t   ON ha.time_id = t.time_id
    WHERE   ha.parent__postn_key = @UserPostnKey
    AND     ha.child__postn_key = @TargetPostnKey
)
BEGIN
    -- Return empty result set (not authorized)
    RETURN
END
```

## Security Logging

### Login Activity Logging

```sql
CREATE PROCEDURE dbo.P_LOG__LOAD_SECURITY_LOG
    @UserId         INT,
    @ActivityType   VARCHAR(50),
    @ActivityDetail VARCHAR(MAX)
AS

INSERT INTO log_security (user_id, activity_type, activity_detail, activity_date)
VALUES (@UserId, @ActivityType, @ActivityDetail, GETDATE())
```

### First Login Detection

```sql
DECLARE @FirstLoginInd BIT = 1

SELECT  TOP 1 @FirstLoginInd = 0
FROM    log_security WITH(NOLOCK)
WHERE   user_id = @UserId
AND     CONVERT(DATE, GETDATE()) = CONVERT(DATE, activity_date)
```

## Permission Configuration (Post-Deploy)

Procedure permissions are seeded in post-deployment scripts:

```sql
-- Grant by user type (role-based)
IF NOT EXISTS (
    SELECT * FROM app_procedure_permission
    WHERE procedure_name = 'P_INTF__GET_ADMIN_DASHBOARD'
    AND user_type__option_id = (SELECT option_id FROM app_option WHERE option_cd = 'ADM')
)
INSERT INTO app_procedure_permission (procedure_name, user_type__option_id, create_date)
SELECT 'P_INTF__GET_ADMIN_DASHBOARD', option_id, GETDATE()
FROM app_option WHERE option_cd = 'ADM'

-- Grant by specific user
IF NOT EXISTS (
    SELECT * FROM app_procedure_permission
    WHERE procedure_name = 'P_INTF__GET_SPECIAL_REPORT'
    AND user_id = (SELECT user_id FROM app_user WHERE user_name = 'jsmith')
)
INSERT INTO app_procedure_permission (procedure_name, user_id, create_date)
SELECT 'P_INTF__GET_SPECIAL_REPORT', user_id, GETDATE()
FROM app_user WHERE user_name = 'jsmith'
```

## Position Level Codes (Common)

| Code | Level | Description |
|------|-------|-------------|
| `CWD` | Company-Wide | Top of hierarchy |
| `MOC` | Manager of Concurrent | Regional manager |
| `RGN` | Region | Region head |
| `TAM` | Territory Manager | Territory lead |
| `MKT` | Market | Market manager |
| `AGN` | Agent | Insurance agent |
| `EFS` | Employee Financial Services | EFS specialist |
| `SUB` | Sub-Agent | Agent subordinate |
| `LSP` | Life Sales Producer | Life insurance producer |
| `NAA` | NAA Agent | Named account agent |
| `ADM` | Administrator | System administrator |

## Anti-Patterns

- **Do not** hardcode user IDs or usernames in security checks — use parameters
- **Do not** raise errors for unauthorized access — return empty result sets
- **Do not** bypass span-of-control by querying tables without the @PostnKey filter
- **Do not** use cascading deletes on permission tables — use soft delete (DELETE_DATE)
- **Do not** cache permission results in application code — always call P_SEC__ procedures
- **Do not** grant permissions directly in stored procedures — use APP_PROCEDURE_PERMISSION table and post-deploy scripts
