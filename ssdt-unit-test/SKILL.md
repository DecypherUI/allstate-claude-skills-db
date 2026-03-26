---
name: ssdt-unit-test
description: Create SQL Server Data Tools (SSDT) unit tests for stored procedures. Use when writing database unit tests, creating test assertions, or setting up test data procedures. Follows table variable capture pattern with EmptyResultSetCondition assertions.
---

# SSDT Unit Test Patterns

## Overview

This skill provides patterns for creating SQL Server unit tests using the Microsoft.Data.Tools.Schema.Sql.UnitTesting framework.

## IMPORTANT: Keep Tests in Sync with Procedures

**After modifying a stored procedure, always update related tests:**

1. **Column changes**: If output columns are added, removed, or renamed, update the `@Result` table variable in ALL tests for that procedure
2. **Business logic changes**: If calculations or status logic changes, update expected values in tests
3. **Parameter changes**: If parameters are added or changed, update test calls and helper queries
4. **New business rules**: Add new data quality tests for new validation requirements

**Checklist after procedure changes:**
- [ ] Update `@Result` table variable to match new output schema
- [ ] Update expected value calculations if logic changed
- [ ] Update test data procedures if new scenarios needed
- [ ] Add new tests for new business rules (BR-XX)
- [ ] Run tests to verify changes work correctly

## Table Variable Pattern

Always capture procedure output into a table variable, then query it for assertions:

```sql
-- Define table variable matching FULL procedure output schema
DECLARE @Result TABLE (
    Column1 INT,
    Column2 VARCHAR(100),
    -- Include ALL columns from requirements document
)

-- Execute procedure into table variable
INSERT INTO @Result
EXEC P_INTF__PROCEDURE_NAME @Param1, @Param2

-- Query table variable for assertions
SELECT * FROM @Result WHERE <condition>
```

**Critical:** The `@Result` table variable must match the COMPLETE column structure defined in the requirements document. Do not use a subset of columns.

## Assertion Pattern: EmptyResultSetCondition

Use WHERE clauses that return rows only when the test should FAIL:

```sql
-- Pass if empty (no rows match failure criteria)
SELECT * FROM @Result
WHERE ISNULL(column1, -999) <> ISNULL(@ExpectedValue1, -999)
   OR ISNULL(column2, -999) <> ISNULL(@ExpectedValue2, -999)
```

- `EmptyResultSetCondition` on this result set means: 0 rows = PASS, >0 rows = FAIL
- Use `ISNULL(column, sentinel)` to handle NULL comparisons
- Use appropriate sentinel values: `-999` for numbers, `''` for strings

## Test Data Verification Pattern

First result set should verify test data exists by querying source tables:

```sql
-- Result Set 1: Verify test data exists (NotEmptyResultSetCondition)
SELECT * FROM SourceTable WHERE <test data conditions>

-- Result Set 2: Actual test assertion (EmptyResultSetCondition)
SELECT * FROM @Result WHERE <failure conditions>
```

## Comprehensive Column Verification

For procedures with many output columns, create ONE test that verifies ALL columns:

```sql
-- Declare expected values from test data
DECLARE @Expected_Col1 INT, @Expected_Col2 VARCHAR(100), ...

-- Query source tables to get expected values
SELECT @Expected_Col1 = t.Column1, @Expected_Col2 = t.Column2, ...
FROM SourceTable t WHERE <conditions>

-- Execute procedure
INSERT INTO @Result EXEC P_INTF__PROCEDURE_NAME ...

-- Verify ALL columns in single assertion (EmptyResultSetCondition)
SELECT * FROM @Result
WHERE ISNULL(Col1, -999) <> ISNULL(@Expected_Col1, -999)
   OR ISNULL(Col2, '') <> ISNULL(@Expected_Col2, '')
   OR ... -- Check every column
```

## P_UNIT Procedure Pattern

Each module requiring test data should have:
- `P_UNIT__CREATE_[MODULE]_TEST_DATA` - Creates all test data for the module
- `P_UNIT__DELETE_[MODULE]_TEST_DATA` - Cleans up all test data for the module

Location: `Application\Database\dbo\Stored Procedures\UnitTestSpecific\`

### Test Execution Flow
1. Test initialization calls `P_UNIT__DELETE_*` (cleanup any orphaned data)
2. Test initialization calls `P_UNIT__CREATE_*` (create fresh test data)
3. Tests execute against the test data
4. Test cleanup calls `P_UNIT__DELETE_*`

**Key principle:** Always call DELETE before CREATE - assume previous tests may have failed to clean up.

## Per-Test Setup/Cleanup

Use PretestAction and PosttestAction for each test:

```csharp
// In .cs file
this.TestData.PretestAction = PretestAction;   // Setup
this.TestData.PosttestAction = PosttestAction; // Cleanup
this.TestData.TestAction = TestAction;         // Test

// In .resx file
// PretestAction calls P_UNIT__DELETE and P_UNIT__CREATE
// PosttestAction calls P_UNIT__DELETE
```

### ClassInitialize Pattern

At end of InitializeComponent(), assign local vars to static fields:

```csharp
// Required to prevent variable shadowing bug
ClassName._classInitializeAction = _classInitializeAction;
ClassName._classCleanupAction = _classCleanupAction;
```

## Row Count Assertions

- `RowCountCondition` with `RowCount = 1` for single-row procedures
- `EmptyResultSetCondition` for procedures that should return no rows on invalid input
- `NotEmptyResultSetCondition` for verifying test data exists

## Test Data Conventions

| Convention | Description |
|------------|-------------|
| Test promotions | `UT ` prefix (e.g., 'UT Home Stretch') |
| Test positions | Negative postn_key values (< 0) |
| Test employees | `_UT` prefix in emp_cd |
| Test period type | UPT (Unit Test Promotion periods) |

## Data Quality Testing Pattern

Data quality tests verify loaded data meets business rules. Different from procedure tests:

### Structure
- `ClassInitialize`: Run load procedure(s) to populate data
- Each test: Verify one business rule via violation query
- `ClassCleanup`: Clean up loaded data

### Violation Query Pattern

Write queries that return rows only when rule is violated (EmptyResultSetCondition = PASS):

```sql
-- BR-XX: Column must be NOT NULL
SELECT promotion_result_id, postn_key, the_column
FROM app_promotion_result r
JOIN app_promotion p ON p.promotion_id = r.promotion_id
WHERE p.promotion_name = 'Home Stretch and Beyond'
AND the_column IS NULL  -- Violation: should never be NULL
```

### Test Naming

Name tests after business rule numbers: `BR06_CurrentPeriodUnique`, `BR12_ActualGoalNotNull`

### ClassInitialize Pattern for Data Quality

```sql
-- Clean up staging
EXEC P_UNIT__DELETE_[MODULE]_STAGING_DATA

-- Populate staging with test data
EXEC P_UNIT__CREATE_[MODULE]_STAGING_DATA @SimulatedAsOfDate = '2026-01-14'

-- Run the load procedure
EXEC P_LOAD__[TABLE_NAME]
```

## VS2022 Compatibility Notes

The existing DatabaseUnitTests project was created in older Visual Studio versions. VS2022 may show designer errors:

**Error:** "The base class 'SqlDatabaseTestClass' could not be loaded"

**Workaround:** This is a designer-only issue. Tests should still compile and run. Try:
1. Build the solution first
2. Run tests from Test Explorer (not designer)

**Long-term fix:** Recreate the unit test project in VS2022 with proper dependencies.

## Namespace and Folder Structure

**Namespaces must match folder structure.** Test Explorer groups tests by namespace, so proper organization is important.

| Folder Path | Namespace |
|-------------|-----------|
| `DataQuality\` | `DatabaseUnitTests.DataQuality` |
| `DataQuality\PromotionModule\` | `DatabaseUnitTests.DataQuality.PromotionModule` |
| `ApplicationSpecific\Promotion\` | `DatabaseUnitTests.ApplicationSpecific.Promotion` |

### When Moving Test Files

When relocating test files to a different folder:

1. **Move both files** (.cs and .resx) to the new folder
2. **Update the namespace** in the .cs file to match the new folder path
3. **Update the project file** (.csproj) with new `Include` paths for both files
4. **Rebuild** to verify tests appear in correct Test Explorer location

```csharp
// Before (in DataQuality folder):
namespace DatabaseUnitTests.DataQuality

// After (moved to DataQuality\PromotionModule folder):
namespace DatabaseUnitTests.DataQuality.PromotionModule
```

## Anti-Patterns to Avoid

1. **Static verification SELECT**: `SELECT '1 - Test Passed'` always returns a row regardless of test data
2. **RAISERROR for assertions**: Harder to assess in output reports; use SQL + conditions instead
3. **Partial column capture**: Table variable must include ALL output columns from requirements
4. **Separate tests per column**: Use one comprehensive test to verify all columns match expected values
5. **INSERT/DELETE in test files**: Test data management must be in P_UNIT__* procedures only
6. **Local vars shadowing static fields**: In InitializeComponent(), use static fields directly for class-level actions
7. **Mismatched namespace and folder**: Namespace must match folder structure or tests appear in wrong Test Explorer location
