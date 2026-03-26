# SSDT Logging Patterns (P_LOG__)

Use this skill when creating or modifying logging procedures, audit trail queries, or error tracking tables and procedures.

## Log Table Pattern

```sql
CREATE TABLE [dbo].[LOG_{PURPOSE}] (
    LOG_ID              INT IDENTITY(1,1) NOT NULL,
    LOG_DATE            DATETIME NOT NULL DEFAULT GETDATE(),
    LOG_TYPE            VARCHAR(20) NOT NULL,       -- 'ERROR', 'INFO', 'WARN', 'AUDIT'
    LOG_SOURCE          VARCHAR(200) NOT NULL,       -- procedure name or module
    LOG_MESSAGE         VARCHAR(MAX) NULL,
    LOG_DETAIL          VARCHAR(MAX) NULL,           -- stack trace, parameters, etc.
    USER_ID             INT NULL,
    POSTN_KEY           BIGINT NULL,
    CONSTRAINT LOG_{PURPOSE}_PK PRIMARY KEY (LOG_ID)
)
```

## Standard Log Tables

| Table | Purpose |
|-------|---------|
| `LOG_EXCEPTION` | Application errors, TRY-CATCH output |
| `LOG_SECURITY` | Login attempts, permission denials |
| `LOG_SQL_PROFILER` | SQL execution timing and diagnostics |
| `LOG_EMAIL` | Email send history and failures |

## Error Logging Procedure Pattern

```sql
CREATE PROCEDURE [dbo].[P_LOG__INSERT_EXCEPTION]
    @ProcedureName  VARCHAR(200),
    @ErrorMessage   VARCHAR(MAX),
    @ErrorDetail    VARCHAR(MAX) = NULL,
    @UserId         INT = NULL,
    @PostnKey       BIGINT = NULL
AS
BEGIN
    SET NOCOUNT ON

    INSERT INTO LOG_EXCEPTION (
        LOG_DATE, LOG_TYPE, LOG_SOURCE,
        LOG_MESSAGE, LOG_DETAIL,
        USER_ID, POSTN_KEY
    )
    VALUES (
        GETDATE(), 'ERROR', @ProcedureName,
        @ErrorMessage, @ErrorDetail,
        @UserId, @PostnKey
    )
END
```

## Using Error Logging in Other Procedures

```sql
BEGIN TRY
    -- ... procedure logic ...
END TRY
BEGIN CATCH
    EXEC P_LOG__INSERT_EXCEPTION
        @ProcedureName = 'P_LOAD__PROCESS_DATA',
        @ErrorMessage = ERROR_MESSAGE(),
        @ErrorDetail = NULL,
        @UserId = @Userid

    -- Re-throw or return error to caller
    ;THROW
END CATCH
```

## Security Audit Logging

```sql
-- Log on successful authentication
INSERT INTO LOG_SECURITY (LOG_DATE, LOG_TYPE, LOG_SOURCE, LOG_MESSAGE, USER_ID)
VALUES (GETDATE(), 'AUTH', 'P_SEC__AUTHENTICATE', 'Login success', @UserId)

-- Log on permission denial
INSERT INTO LOG_SECURITY (LOG_DATE, LOG_TYPE, LOG_SOURCE, LOG_MESSAGE, USER_ID, POSTN_KEY)
VALUES (GETDATE(), 'DENY', 'P_SEC__CHECK_PERMISSION', 'Access denied: ' + @ProcedureName, @UserId, @PostnKey)
```

## Key Reminders

- Log tables should NOT have foreign keys (logging must never fail due to FK violations)
- Use `VARCHAR(MAX)` for message/detail columns — truncation loses debugging info
- Always include `LOG_DATE` with `DEFAULT GETDATE()` — never rely on caller to pass timestamp
- Log procedures should never throw exceptions themselves (wrap in TRY-CATCH internally)
- Consider retention: old log entries should be purged periodically (non-deployment script)
