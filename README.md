# Claude DB Skills — Allstate

Shared Claude Code skills for all Allstate SQL Server database projects (SSDT). These skills define mandatory conventions for stored procedures, tables, views, ETL pipelines, unit tests, and deployment patterns.

## Usage

This repository is included as a Git submodule at `.claude/skills/` in each database project:

- [allstate-database-apt](https://github.com/DecypherUI/allstate-database-apt)
- [allstate-database-efs-incentive-tool](https://github.com/DecypherUI/allstate-database-efs-incentive-tool)

Claude Code automatically discovers and applies these skills when working in those repositories.

## Skills

| Skill | When to Use |
|-------|-------------|
| `ssdt-stored-proc` | Stored procedure conventions (headers, naming, output formatting) |
| `ssdt-interface-proc` | P_INTF__ patterns (dashboards, grids, pagination, updates) |
| `ssdt-unit-test` | SQL Server unit test patterns (assertions, table variables, test data) |
| `ssdt-table-design` | Table creation (audit columns, soft delete, FK/PK/index naming, data types) |
| `ssdt-view-design` | View creation (naming, hierarchy flattening, column contracts) |
| `ssdt-deployment` | Deploy without Visual Studio (sqlcmd, Docker, dependency ordering) |
| `ssdt-post-deploy-data` | Idempotent data seeding (IF NOT EXISTS, MERGE, bulk insert) |
| `ssdt-dynamic-sql` | Pagination, sorting UDT, sp_executesql, dynamic pivot |
| `ssdt-etl-pipeline` | P_LOAD__/P_ETL__ staging, upsert, time-partitioned loads, rollups |
| `ssdt-hierarchy-queries` | Hierarchy traversal, transitive closure, span-of-control, tree control |
| `ssdt-excel-export` | P_XLS__ wrapper pattern (Title Case aliases, percentage formatting) |
| `ssdt-email-system` | P_EML__ template system (UDT_MAIL_MESSAGE, token replacement) |
| `ssdt-security-model` | P_SEC__ authentication, permissions, span-of-control filtering |
| `ssdt-report-proc` | P_REP__ executive reports, analytics, Crystal Reports integration |
| `ssdt-logging` | P_LOG__ error logging, security audit, log table design |
| `vs-project-files` | Adding files to Visual Studio projects (.csproj, .sqlproj) |

## Skill Maintenance

Skills are living documents. When project conventions evolve or new patterns emerge, update the relevant skill file and push. All downstream repos will pick up changes on their next `git submodule update`.

## Adding a New Skill

1. Create a directory: `my-new-skill/`
2. Add `SKILL.md` inside it with a clear "Use this skill when..." opening line
3. Commit, push, and update submodule refs in downstream repos
