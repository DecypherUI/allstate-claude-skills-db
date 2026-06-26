# SSDT Change Deployment Package (zip for the DBA)

Use this skill when **packaging a set of changed SSDT objects into a zip to hand off** to a DBA / recipient who will deploy it from Visual Studio. This is the *shipping artifact*, NOT a live deploy — for deploying objects yourself with `sqlcmd`/Docker, use the `ssdt-deployment` skill instead.

This is the authoritative APT/EFS convention. Follow it exactly — it has been gotten wrong before (people invented a `DEPLOY_UPDATE.sql`, added READMEs, or wrapped CREATE-OR-ALTER). **Do none of that.**

## The convention (non-negotiable)

The package contains **ONLY the changed SSDT object files, at their exact project-relative paths**, with `Application\` at the zip root. Specifically:

- ✅ The changed `.sql` object files under `Application\Database\...` (Tables, Views, Functions, Stored Procedures incl. `UnitTestSpecific\`, Pre/PostDeploymentScripts).
- ✅ `Application\Database\Database.sqlproj` — **include it** whenever objects were **added/renamed/removed**, so the recipient's Visual Studio picks up the new `<Build Include=...>` entries. (For pure edits to existing objects it is optional, but including it is harmless and safer.)
- ✅ Changed unit-test project files under `Application\DatabaseUnitTests\...` if the change touched them.
- ❌ **NO `DEPLOY_UPDATE.sql` / hand-written idempotent deploy script.** The recipient deploys from Visual Studio, which resolves dependency ordering and CREATE-vs-ALTER. The recipient writes their own `deploy_update.sql` if they want one.
- ❌ **NO** `README`, no `CREATE OR ALTER` rewrites, no PRDs/docs/`Documents\`, no `.md` files.
- ❌ **NO** obfuscation, no renamed/flattened files — ship the source files verbatim.

The recipient copies the files into their own clone of the SSDT project (identical folder structure) and deploys from Visual Studio.

## Naming & location

- **Output folder:** the workspace-level `deploy_output\` directory (sibling to the repo clones, e.g. `C:\Workspace\git\allstate\apt\deploy_output\`).
- **Filename:** `apt_db_changes_YYYYMMDD_HHMMSS.zip` (APT). EFS uses the **same format** with its own project-appropriate prefix. `YYYYMMDD_HHMMSS` = the date **and 24-hour local time** the package was built (e.g. `apt_db_changes_20260625_212857.zip`). The time component is required so multiple packages built the same day during iterative testing are uniquely identifiable and sortable (the old date-only name collided/overwrote). Get the stamp with PowerShell `Get-Date -Format 'yyyyMMdd_HHmmss'`.

## Deriving the changed-file set

Drive the file list from git so nothing is missed and nothing extra sneaks in. The feature delta = everything that differs from the base/deployment branch (`main` for APT DB), **including uncommitted working-tree edits**, filtered to `Application/`:

```bash
cd <db-repo>
# tracked changes (committed + working tree) vs the deployment branch:
git diff --name-only main -- "Application/"
# plus brand-new untracked object files:
git ls-files --others --exclude-standard -- "Application/"
```

Union + sort -u these two lists. Notes:
- A **rename** appears as the old path deleted + new path untracked; ship only the **new** file. Tell the recipient to **drop the old object** (the rename leaves it orphaned in their DB).
- If you only want committed changes, diff against the merge-base instead: `git diff --name-only $(git merge-base main HEAD)...HEAD`. Building from the working tree is fine and common, but **say so** — the zip then reflects uncommitted edits.

## Build recipe (staging in Bash, zipping in PowerShell)

⚠️ **PowerShell safety-guard gotcha:** the environment blocks `Remove-Item` on system-path-looking patterns (`*`, `/`). Do **all** file staging/copy/delete in the **Bash** tool. Use PowerShell **only** for `Compress-Archive` (no `Remove-Item` in that script). Verify zip paths without slash-regex (`.EndsWith('...')` is fine; `-match '/'` next to a delete is not).

**1. Stage (Bash)** — copy each changed file into a clean staging dir, preserving its `Application\...` relative path:

```bash
SRC="<db-repo>"
STAGE="<scratchpad>/db_pkg_YYYYMMDD"
rm -rf "$STAGE"; mkdir -p "$STAGE"
cd "$SRC"
LIST="<scratchpad>/db_files.txt"
{ git diff --name-only main -- "Application/"; git ls-files --others --exclude-standard -- "Application/"; } | sort -u > "$LIST"
count=0
while IFS= read -r f; do
  [ -z "$f" ] && continue
  mkdir -p "$STAGE/$(dirname "$f")"
  cp "$SRC/$f" "$STAGE/$f"
  count=$((count+1))
done < "$LIST"
echo "staged $count files"
find "$STAGE/Application" -type f | sort   # eyeball the list — no docs, no DEPLOY_UPDATE.sql
```

**2. Zip (PowerShell)** — `Application\` at the zip root:

```powershell
$ts    = Get-Date -Format 'yyyyMMdd_HHmmss'                       # date + 24h local time
$stage = "<scratchpad>\db_pkg_YYYYMMDD"
$dest  = "<workspace>\deploy_output\apt_db_changes_$ts.zip"        # e.g. apt_db_changes_20260625_212857.zip
Compress-Archive -Path (Join-Path $stage "Application") -DestinationPath $dest -Force
$entries = [System.IO.Compression.ZipFile]::OpenRead($dest).Entries
"size bytes: " + (Get-Item $dest).Length
"file entries: " + ($entries | Where-Object { -not $_.FullName.EndsWith('\') }).Count
$entries.FullName    # verify: every path starts with Application\ ; no .md / DEPLOY_UPDATE.sql
```

## Verification checklist

- [ ] Every entry path begins with `Application\`.
- [ ] No `.md`, no `DEPLOY_UPDATE.sql`, no `Documents\`, no PRDs.
- [ ] `Database.sqlproj` present if objects were added/renamed/removed, and its `<Build Include>` entries reference the new files (and not deleted ones).
- [ ] Renamed objects: new file present; old file absent; note to recipient to drop the old object.
- [ ] File count matches the git-derived list.
- [ ] Compare entry count/shape against the previous `apt_db_changes_*.zip` for sanity.

## Tip: match the previous package's shape

List the prior package and diff the file set — the new one should differ only by the files this change actually touched:

```bash
unzip -l deploy_output/apt_db_changes_<prevdate>.zip
```

## Anti-patterns

- **Do not** author a `DEPLOY_UPDATE.sql` or any idempotent deploy script — wrong for APT/EFS; the DBA deploys from Visual Studio and writes their own.
- **Do not** include docs, PRDs, READMEs, or `.md` files.
- **Do not** rewrite objects as `CREATE OR ALTER` or reorder them — ship source verbatim.
- **Do not** hand-pick files from memory — derive the list from `git diff` so nothing is missed.
- **Do not** run `Compress-Archive` in a script that also calls `Remove-Item` — the safety guard will block it. Stage/delete in Bash first.
