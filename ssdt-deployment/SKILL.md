# SSDT Database Deployment Without Visual Studio

Use this skill when deploying SQL Server database objects to a target server without Visual Studio or SSDT installed. This covers Docker containers, Linux servers, CI/CD pipelines, and any environment with `sqlcmd` available.

## Deployment Order

SSDT resolves dependencies automatically. Without SSDT, you must deploy objects in this order to satisfy dependencies:

```
Phase 1: User Defined Types (UDTs)     — no dependencies
Phase 2: Tables                         — depends on UDTs (table types in defaults)
Phase 3: Views                          — depends on tables
Phase 4: Functions                      — depends on tables
Phase 5: Stored Procedures              — depends on all above
Phase 6: Post-Deployment Data Scripts   — depends on all above
```

**Pre-deployment scripts** (schema renames, migrations) run before Phase 1 if needed.

## sqlcmd Connection

```bash
# Direct SQL Server
sqlcmd -S <server> -U <user> -P '<password>' -d <database> -i "path/to/file.sql"

# Docker container (SQL Server on Linux)
docker exec <container> /opt/mssql-tools18/bin/sqlcmd \
  -S localhost \
  -U sa \
  -P '<password>' \
  -d <database> \
  -C \
  -i "/container/path/to/file.sql"
```

**Key flags:**
- `-S` — server (use `localhost` for Docker)
- `-U` / `-P` — credentials
- `-d` — target database
- `-C` — trust server certificate (required for Docker/self-signed)
- `-i` — input SQL file
- `-b` — batch abort on error (stop on first error in file)
- `-Q` — inline SQL string (for ad-hoc commands)

## Deployment Script Template

```bash
#!/bin/bash
# Deploy SSDT project to SQL Server without Visual Studio
# Mimics SSDT deployment order: UDTs -> Tables -> Views -> Functions -> Procedures

set -e

# === CONFIGURATION ===
# Adjust these for your environment
SQLCMD="sqlcmd"                          # or "docker exec <container> /opt/mssql-tools18/bin/sqlcmd"
SERVER="localhost"
USER="sa"
PASS="YourPassword"
DB="your_database"
BASE="Application/Database"             # path to SSDT project root
TRUST_CERT=""                           # set to "-C" for Docker/self-signed certs
CONTAINER_BASE=""                       # set to container mount path if using Docker (e.g., "/workspace")

ERRORS=0
SUCCESS=0
SKIPPED=0

run_sql_file() {
    local file="$1"
    local category="$2"
    if [ ! -f "$file" ]; then
        echo "  SKIP (not found): $file"
        ((SKIPPED++))
        return 0
    fi

    # Use container path if set, otherwise use host path
    local deploy_path="$file"
    if [ -n "$CONTAINER_BASE" ]; then
        deploy_path="$CONTAINER_BASE/$file"
    fi

    if $SQLCMD -S "$SERVER" -U "$USER" -P "$PASS" $TRUST_CERT -d "$DB" -i "$deploy_path" -b 2>&1 | tail -3; then
        ((SUCCESS++))
    else
        echo "  ERROR: $file"
        ((ERRORS++))
    fi
}

run_sql_string() {
    local sql="$1"
    $SQLCMD -S "$SERVER" -U "$USER" -P "$PASS" $TRUST_CERT -d "$DB" -Q "$sql" 2>&1
}

echo "=== Deploying to $DB ==="

# Phase 0: Pre-Deployment Scripts (optional)
if [ -f "$BASE/PreDeploymentScripts/Script.PreDeployment.Master.sql" ]; then
    echo ""
    echo "--- Phase 0: Pre-Deployment Scripts ---"
    # Note: Master script uses :r includes which require SQLCMD mode
    # Deploy individual scripts instead if :r is not supported
    for f in "$BASE/PreDeploymentScripts/"*.sql; do
        [[ "$(basename "$f")" == "Script.PreDeployment.Master.sql" ]] && continue
        [ -f "$f" ] && echo "  Deploying: $(basename "$f")" && run_sql_file "$f" "PREDEPLOY"
    done
fi

# Phase 1: User Defined Types
echo ""
echo "--- Phase 1: User Defined Types ---"
for f in "$BASE/dbo/User Defined Types/"*.sql; do
    [ -f "$f" ] && echo "  Deploying: $(basename "$f")" && run_sql_file "$f" "UDT"
done

# Phase 2: Tables
echo ""
echo "--- Phase 2: Tables ---"
for f in "$BASE/dbo/Tables/"*.sql; do
    [ -f "$f" ] && run_sql_file "$f" "TABLE"
done

# Phase 3: Views
echo ""
echo "--- Phase 3: Views ---"
for f in "$BASE/dbo/Views/"*.sql; do
    [ -f "$f" ] && echo "  Deploying: $(basename "$f")" && run_sql_file "$f" "VIEW"
done

# Phase 4: Functions
echo ""
echo "--- Phase 4: Functions ---"
for f in "$BASE/dbo/Functions/"*.sql; do
    [ -f "$f" ] && echo "  Deploying: $(basename "$f")" && run_sql_file "$f" "FUNCTION"
done

# Phase 5: Stored Procedures (including subdirectories)
echo ""
echo "--- Phase 5: Stored Procedures ---"
for f in "$BASE/dbo/Stored Procedures/"*.sql; do
    [ -f "$f" ] && run_sql_file "$f" "PROC"
done
# Deploy subdirectory procedures (e.g., UnitTestSpecific/)
for f in "$BASE/dbo/Stored Procedures/"*/*.sql; do
    [ -f "$f" ] && run_sql_file "$f" "PROC"
done

# Phase 6: Post-Deployment Data Scripts (optional)
if [ -d "$BASE/PostDeploymentScripts" ]; then
    echo ""
    echo "--- Phase 6: Post-Deployment Data ---"
    # Deploy scripts listed in master file (in order)
    # Parse active :r references from master script
    if [ -f "$BASE/PostDeploymentScripts/Script.PostDeployment.Master.sql" ]; then
        while IFS= read -r line; do
            # Match active :r includes (not commented out)
            if [[ "$line" =~ ^:r[[:space:]]+\.\\ ]]; then
                script_name=$(echo "$line" | sed 's/^:r \.\\//; s/\r$//')
                script_path="$BASE/PostDeploymentScripts/$script_name"
                if [ -f "$script_path" ]; then
                    echo "  Deploying: $script_name"
                    run_sql_file "$script_path" "POSTDEPLOY"
                fi
            fi
        done < "$BASE/PostDeploymentScripts/Script.PostDeployment.Master.sql"
    fi
fi

echo ""
echo "=== Deployment Summary ==="
echo "  Success: $SUCCESS"
echo "  Errors:  $ERRORS"
echo "  Skipped: $SKIPPED"
```

## Deploying a Single Object

When you modify a single stored procedure, view, function, or UDT, deploy just that file:

```bash
# Single procedure
sqlcmd -S localhost -U sa -P 'Password' -d mydb -C \
  -i "Application/Database/dbo/Stored Procedures/P_INTF__GET_DASHBOARD.sql"

# Single table (CREATE TABLE is idempotent only if table doesn't exist)
# For existing tables, use ALTER TABLE statements instead
```

## CREATE vs ALTER Handling

SSDT `.sql` files use `CREATE` statements. On re-deployment to an existing database:

- **Stored Procedures**: Use `CREATE OR ALTER` (SQL Server 2016 SP1+) or wrap with existence check:
  ```sql
  IF OBJECT_ID('dbo.P_INTF__MY_PROC', 'P') IS NOT NULL
      DROP PROCEDURE dbo.P_INTF__MY_PROC
  GO
  CREATE PROCEDURE dbo.P_INTF__MY_PROC ...
  ```
- **Views/Functions**: Same pattern — `CREATE OR ALTER` or drop-then-create
- **Tables**: Never drop-and-recreate in production. Use `ALTER TABLE` for changes.
- **UDTs**: Cannot be altered if referenced. Must drop dependent objects, drop UDT, recreate UDT, recreate dependents.

## Table Deployment: Foreign Key Ordering

SSDT table `.sql` files typically separate `CREATE TABLE` from `ALTER TABLE ... ADD CONSTRAINT FOREIGN KEY`. This means:
- Tables can be created in any order (no FK violations during CREATE)
- FK constraints are added after all tables exist
- If your files combine CREATE TABLE + FK in one file, you must sort by dependency

To check if FKs are inline or separate:
```bash
grep -l "FOREIGN KEY" Application/Database/dbo/Tables/*.sql | head -5
```

## Post-Deploy Data Script Patterns

Post-deployment scripts seed reference data. They must be **idempotent** — safe to run multiple times. See the `ssdt-post-deploy-data` skill for patterns.

## Pre-Deploy Migration Scripts

Pre-deployment scripts handle schema changes that must occur before the main deployment:
- Column renames (`sp_rename`)
- Data migrations between old and new schemas
- Dropping deprecated objects

Always wrap in existence checks:
```sql
IF COL_LENGTH('dbo.MY_TABLE', 'OLD_COLUMN') IS NOT NULL
    EXEC sp_rename 'dbo.MY_TABLE.OLD_COLUMN', 'NEW_COLUMN', 'COLUMN'
```

## SQLCMD Mode vs Standard SQL

SSDT master scripts use SQLCMD syntax (`:r .\file.sql` includes). This requires SQLCMD mode:
- `sqlcmd` CLI supports it natively
- SSMS requires enabling SQLCMD mode (Query menu)
- If your tool doesn't support `:r`, deploy individual scripts in order instead

## Verifying Deployment

After deployment, verify object counts match expectations:

```sql
-- Count by object type
SELECT
    CASE type
        WHEN 'P'  THEN 'Stored Procedure'
        WHEN 'U'  THEN 'Table'
        WHEN 'V'  THEN 'View'
        WHEN 'FN' THEN 'Scalar Function'
        WHEN 'TF' THEN 'Table Function'
        WHEN 'IF' THEN 'Inline Function'
        WHEN 'TT' THEN 'Table Type'
    END AS object_type,
    COUNT(*) AS object_count
FROM sys.objects
WHERE schema_id = SCHEMA_ID('dbo')
  AND type IN ('P', 'U', 'V', 'FN', 'TF', 'IF', 'TT')
GROUP BY type
ORDER BY type

-- Find objects that exist in DB but not in source (orphans)
-- Find objects in source but not in DB (missing deployments)
```

## Anti-Patterns

- **Do not** deploy tables alphabetically if FK constraints are inline — use dependency order
- **Do not** skip post-deployment scripts — the database will be empty of reference data
- **Do not** use `DROP TABLE` in deployment scripts for existing production tables
- **Do not** deploy UDT changes without first dropping dependent stored procedures
- **Do not** use `EXEC()` for deployment — use `sqlcmd -i` for file-based deployment
- **Do not** hardcode passwords in scripts checked into source control — use environment variables or secrets managers
