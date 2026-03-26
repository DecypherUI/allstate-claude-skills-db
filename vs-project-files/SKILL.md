---
name: vs-project-files
description: Add files to Visual Studio project files (.csproj, .sqlproj). Use when creating new source files, unit tests, stored procedures, or tables that need to be included in a Visual Studio solution. Provides correct XML entries for different file types.
---

# Visual Studio Project File Management

## Overview

When creating new files that belong to a Visual Studio project, you MUST add them to the `.csproj` or `.sqlproj` file. Simply creating the file on disk is not enough - Visual Studio will not recognize or compile files that aren't included in the project.

## Unit Test Files (.cs and .resx)

Add to the `.csproj` file (e.g., `DatabaseUnitTests.csproj`):

```xml
<!-- For .cs test files -->
<Compile Include="ApplicationSpecific\ModuleName\TestFileName.cs">
  <DependentUpon>TestFileName.resx</DependentUpon>
</Compile>

<!-- For .resx resource files -->
<EmbeddedResource Include="ApplicationSpecific\ModuleName\TestFileName.resx">
  <Generator>ResXFileCodeGenerator</Generator>
  <LastGenOutput>TestFileName.Designer.cs</LastGenOutput>
  <SubType>Designer</SubType>
</EmbeddedResource>
```

### Key Points for Unit Tests
- The `.cs` file uses `<Compile>` with `<DependentUpon>` linking to the `.resx`
- The `.resx` file uses `<EmbeddedResource>` with generator settings
- Path is relative to the project file location
- `DependentUpon` creates the visual nesting in Solution Explorer

## SQL Files (Stored Procedures, Tables, Views)

Add to the `.sqlproj` file (e.g., `Database.sqlproj`):

```xml
<!-- For stored procedures -->
<Build Include="dbo\Stored Procedures\P_PROCEDURE_NAME.sql" />

<!-- For tables -->
<Build Include="dbo\Tables\TABLE_NAME.sql" />

<!-- For views -->
<Build Include="dbo\Views\V_VIEW_NAME.sql" />

<!-- For functions -->
<Build Include="dbo\Functions\F_FUNCTION_NAME.sql" />
```

### Key Points for SQL Files
- All SQL files use `<Build Include="...">`
- Path is relative to the `.sqlproj` file location
- Use forward slashes or backslashes (both work)
- Files must be in the correct schema folder (typically `dbo\`)

## Checklist When Creating New Files

1. Create the file on disk in the correct directory
2. Open the appropriate `.csproj` or `.sqlproj` file
3. Find the correct `<ItemGroup>` section for your file type
4. Add the appropriate XML entry (`<Compile>`, `<EmbeddedResource>`, or `<Build>`)
5. Verify the path matches the file location relative to the project file
6. Save the project file

## Common Mistakes to Avoid

| Mistake | Consequence |
|---------|-------------|
| Forgetting to add to project file | File exists but won't compile/deploy |
| Wrong path in Include attribute | Build error: file not found |
| Missing `<DependentUpon>` for .cs | Files not nested in Solution Explorer |
| Wrong ItemGroup section | May cause unexpected behavior |

## Finding the Right ItemGroup

Look for existing entries of the same type:

```xml
<!-- Unit test files are typically in an ItemGroup like this -->
<ItemGroup>
  <Compile Include="ExistingTest.cs">
    <DependentUpon>ExistingTest.resx</DependentUpon>
  </Compile>
</ItemGroup>

<!-- SQL files are typically in an ItemGroup like this -->
<ItemGroup>
  <Build Include="dbo\Tables\ExistingTable.sql" />
  <Build Include="dbo\Stored Procedures\ExistingProc.sql" />
</ItemGroup>
```

Add your new entries to the same ItemGroup as similar files.

## Example: Adding a Complete Unit Test

For a new test file at `ApplicationSpecific\PromotionModule\NewTests.cs`:

```xml
<!-- In DatabaseUnitTests.csproj -->
<ItemGroup>
  <!-- Add .resx entry -->
  <EmbeddedResource Include="ApplicationSpecific\PromotionModule\NewTests.resx">
    <Generator>ResXFileCodeGenerator</Generator>
    <LastGenOutput>NewTests.Designer.cs</LastGenOutput>
    <SubType>Designer</SubType>
  </EmbeddedResource>
</ItemGroup>

<ItemGroup>
  <!-- Add .cs entry -->
  <Compile Include="ApplicationSpecific\PromotionModule\NewTests.cs">
    <DependentUpon>NewTests.resx</DependentUpon>
  </Compile>
</ItemGroup>
```

## Example: Adding a New Stored Procedure

For a new procedure at `dbo\Stored Procedures\P_INTF__NEW_PROCEDURE.sql`:

```xml
<!-- In Database.sqlproj -->
<ItemGroup>
  <Build Include="dbo\Stored Procedures\P_INTF__NEW_PROCEDURE.sql" />
</ItemGroup>
```
