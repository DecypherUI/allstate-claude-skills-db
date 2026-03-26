# SSDT Email System Patterns

Use this skill when creating or modifying P_EML__ procedures, email templates, or email parameter configurations.

## Architecture Overview

```
APP_EMAIL_TEMPLATE          — HTML templates with [R:Token] placeholders
APP_EMAIL_PARAMETER         — Maps tokens to data sources (static, table, function, MailKey)
APP_EMAIL_PARAMETER_FUNCTION — Maps function parameters for dynamic data
        ↓
P_EML__BUILD_*              — Builds email messages using templates
        ↓
P_INTF__GET_EMAIL           — Core builder: resolves tokens, constructs message
        ↓
UDT_MAIL_MESSAGE            — Table-valued result with fully-resolved email
        ↓
P_INTF__INSERT_EMAIL_LOG    — Logs to LOG_EMAIL (deduplication built in)
        ↓
SSIS / sp_send_dbmail       — Actual delivery
```

## UDT Definitions

### UDT_MAIL_MESSAGE — Email Output

```sql
CREATE TYPE UDT_MAIL_MESSAGE AS TABLE
(
    EMAIL_TEMPLATE_ID   INT,
    EMAIL_FRM_ADDR      VARCHAR(128),
    EMAIL_TO_ADDR       VARCHAR(500),
    EMAIL_CC_ADDR       VARCHAR(500),
    EMAIL_BCC_ADDR      VARCHAR(500),
    EMAIL_SUBJECT       VARCHAR(998),
    EMAIL_BODY          VARCHAR(MAX),
    SKIP_IND            BIT
)
```

### UDT_MAIL_KEY — Dynamic Parameter Values

```sql
CREATE TYPE dbo.UDT_MAIL_KEY AS TABLE
(
    KEY_TYPE    VARCHAR(MAX),       -- parameter name (e.g., 'Date', 'RegionName')
    KEY_VALUE   VARCHAR(MAX)        -- SQL query string or static value
)
```

### UDT_MAIL_FUNCTION_KEY — Function Parameters

```sql
CREATE TYPE dbo.UDT_MAIL_FUNCTION_KEY AS TABLE
(
    parameter_name      VARCHAR(255),   -- email parameter name
    parameter           VARCHAR(MAX),   -- SQL parameter placeholder (e.g., '@PostnKey')
    parameter_value     VARCHAR(50)     -- actual value
)
```

## P_EML__ Procedure Template

```sql
CREATE PROCEDURE dbo.P_EML__BUILD_MY_EMAIL
AS
/**************************************************************************
PROCEDURE:    P_EML__BUILD_MY_EMAIL
DESCRIPTION:  Builds and logs monthly notification email.

SAMPLE CALL:
    EXEC P_EML__BUILD_MY_EMAIL
***************************************************************************/

DECLARE @UserId             INT             = (SELECT user_id FROM app_user WHERE user_name = 'SYSTEM'),
        @emailTemplateCd    VARCHAR(50)     = 'MYTEMPLATE',
        @MailKey            UDT_MAIL_KEY,
        @FunctionKey        UDT_MAIL_FUNCTION_KEY,
        @Messages           UDT_MAIL_MESSAGE,
        @emailTemplateId    INT,
        @dateTxt            VARCHAR(50)

-- Look up template by code name
SELECT  @emailTemplateId = email_template_id
FROM    app_email_template
WHERE   template_nm = @emailTemplateCd

-- IDEMPOTENCY: Skip if already sent this month
IF NOT EXISTS
(
    SELECT  1
    FROM    log_email
    WHERE   email_template_id = @emailTemplateId
    AND     MONTH(create_date) = MONTH(GETDATE())
    AND     YEAR(create_date)  = YEAR(GETDATE())
    AND     ISNULL(skip_ind, 1) = 0
)
BEGIN
    -- Prepare dynamic token values
    SET @dateTxt = FORMAT(GETDATE(), 'MMMM yyyy')

    INSERT  @MailKey (key_value, key_type)
    SELECT  'SELECT ''Date'', ''' + @dateTxt + '''', 'Date'

    -- Build the email via core builder
    INSERT  @Messages
    EXEC    P_INTF__GET_EMAIL @UserId, @emailTemplateCd, @MailKey, @FunctionKey

    -- Log the email (with built-in deduplication)
    EXEC    P_INTF__INSERT_EMAIL_LOG @UserId, @Messages, NULL

    -- Clean up UDT variables
    DELETE  @FunctionKey
    DELETE  @MailKey
    DELETE  @Messages
END
```

## Token Replacement Pattern

Templates use `[R:TokenName]` placeholders in both subject and body:

```
Subject: "[R:CompanyName] Monthly Report - [R:Date]"
Body:    "Dear [R:RecipientName], your region [R:RegionCode] has..."
```

P_INTF__GET_EMAIL resolves tokens from four sources:

| Source | APP_EMAIL_PARAMETER.SOURCE_TABLE_NM | How It Works |
|--------|--------------------------------------|--------------|
| Static | NULL (STATIC_VALUE set) | Direct value insertion |
| MailKey | `'MailKey'` | Caller passes SQL query in UDT_MAIL_KEY |
| Function | `'FUNCTION'` | Calls stored procedure, passes params via UDT_MAIL_FUNCTION_KEY |
| Table | Table name (e.g., `'APP_EMPLOYEE'`) | Queries table column directly |

### MailKey Example (Most Common)

```sql
-- Pass a date token
INSERT  @MailKey (key_value, key_type)
SELECT  'SELECT ''Date'', ''' + FORMAT(GETDATE(), 'MMMM yyyy') + '''', 'Date'

-- Pass a region name token
INSERT  @MailKey (key_value, key_type)
SELECT  'SELECT ''RegionName'', region_cd FROM app_postn_rel WHERE postn_key = ' +
        CONVERT(VARCHAR, @PostnKey), 'RegionName'
```

The `key_value` is a SQL SELECT that returns two columns: parameter name and parameter value.

## Email Logging and Deduplication

### P_INTF__INSERT_EMAIL_LOG

Inserts into LOG_EMAIL with built-in deduplication:

```sql
INSERT  log_email (email_template_id, email_from, email_to, ..., create_date, create__user_id)
SELECT  email_template_id, email_frm_addr, email_to_addr, ..., GETDATE(), @UserId
FROM    @Messages m
WHERE   NOT EXISTS (
    SELECT  *
    FROM    log_email e
    WHERE   e.email_template_id = m.email_template_id
    AND     e.create__user_id = @UserId
    AND     CONVERT(DATE, e.create_date) = CONVERT(DATE, GETDATE())
    AND     e.email_to = m.email_to_addr
    AND     ISNULL(e.skip_ind, 0) = 0
)
```

**Dedup key:** template_id + user_id + date + recipient. Same email won't be logged twice on the same day.

## Test System Email Redirection

P_INTF__GET_EMAIL detects the environment via `@@SERVERNAME`:

```sql
-- Production servers (emails sent to real recipients)
IF @@SERVERNAME LIKE 'A0775%' OR @@SERVERNAME LIKE 'A0185%'
    -- Send normally

-- Non-production (redirect all emails to test inbox)
ELSE
BEGIN
    SET @MessageSubject = 'TEST: ' + @MessageSubject
    SET @MessageBody = '<table><tr><td>ORIGINAL RECIPIENT(s):</td><td>' +
                       ISNULL(@MessageTo, '(None)') + '</td></tr></table>' +
                       '<hr/>' + @MessageBody
    SET @MessageTo = 'decypherreporting@allstate.com'
    SET @MessageCC = NULL
    SET @MessageBCC = NULL
END
```

## Direct sp_send_dbmail Pattern

For notifications that don't use the template system (cursor-driven, multi-recipient):

```sql
-- Only send on production-class servers
IF LEFT(@@SERVERNAME, 2) IN ('A0', 'A9', 'Z0', 'Z9', 'Y0', 'Y9')
    EXEC msdb.dbo.sp_send_dbmail
        @profile_name = 'Awards Management',
        @recipients = @EmailTo,
        @subject = @EmailSubject,
        @body = @EmailBody,
        @body_format = 'HTML',
        @reply_to = 'NOREPLY@allstate.com'
```

## Template Configuration Tables

### APP_EMAIL_TEMPLATE

```sql
EMAIL_TEMPLATE_ID   INT IDENTITY    -- surrogate key
TEMPLATE_NM         VARCHAR(50)     -- lookup code (e.g., 'PMLEADER')
USER_FRIENDLY_NM    VARCHAR(100)    -- display name
SUBJECT_TXT         VARCHAR(998)    -- subject with [R:Token] placeholders
BODY_TXT            VARCHAR(MAX)    -- HTML body with [R:Token] placeholders
HTML_IND            BIT DEFAULT 1   -- always HTML
INCLUDE_EXPORT_IND  BIT DEFAULT 0   -- attach Excel export
MEDIA_LIST          VARCHAR(MAX)    -- embedded images (ContentId;Path;MediaType)
```

### APP_EMAIL_PARAMETER

```sql
EMAIL_PARAMETER_ID  INT IDENTITY
EMAIL_TEMPLATE_ID   INT             -- FK to template
EMAIL_PARAMETER_NM  VARCHAR(50)     -- token name (matches [R:Name])
SOURCE_TABLE_NM     VARCHAR(128)    -- 'MailKey', 'FUNCTION', or table name
SOURCE_COLUMN_NM    VARCHAR(128)    -- column to query (for table source)
STATIC_VALUE        VARCHAR(100)    -- direct value (if not dynamic)
FUNCTION_NAME       VARCHAR(255)    -- procedure name (for FUNCTION source)
```

## Anti-Patterns

- **Do not** send emails directly from P_EML__ — use P_INTF__GET_EMAIL + P_INTF__INSERT_EMAIL_LOG
- **Do not** hardcode email addresses in procedures — use APP_EMAIL_TEMPLATE and APP_REGION_EMAIL_NOTIFICATION
- **Do not** skip the idempotency check — always check LOG_EMAIL before building
- **Do not** forget test system redirection — all non-production emails must route to test inbox
- **Do not** use plain text — always use HTML format (HTML_IND = 1)
- **Do not** use SYSTEM user_id directly — look it up: `SELECT user_id FROM app_user WHERE user_name = 'SYSTEM'`
