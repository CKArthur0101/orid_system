# Full prod dump + research CSVs for local analysis.
# Usage: powershell -NoProfile -ExecutionPolicy Bypass -File scripts\backup-with-research.ps1
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$ComposeProject = "orid-prod"
$ComposeFile = "docker-compose.prod.yml"
$EnvFile = ".env.prod"
$SnapshotsRoot = Join-Path $Root "runtime\backups\snapshots"
$MasterLog = Join-Path $Root "runtime\backups\backup-with-research.log"

function Write-Log([string]$Message) {
    $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    Write-Host $line
    $logDir = Split-Path -Parent $MasterLog
    if ($logDir -and -not (Test-Path $logDir)) {
        New-Item -ItemType Directory -Force -Path $logDir | Out-Null
    }
    Add-Content -Path $MasterLog -Value $line -Encoding UTF8
}

function Get-DotEnvValue([string]$Path, [string]$Key) {
    foreach ($raw in Get-Content -Path $Path -Encoding UTF8) {
        $line = $raw.Trim()
        if (-not $line -or $line.StartsWith("#")) { continue }
        $eq = $line.IndexOf("=")
        if ($eq -lt 1) { continue }
        $k = $line.Substring(0, $eq).Trim()
        if ($k -ne $Key) { continue }
        return $line.Substring($eq + 1).Trim().Trim('"').Trim("'")
    }
    return $null
}

function Save-Utf8BomCsv([string]$Path, [string]$Text) {
    $utf8Bom = New-Object System.Text.UTF8Encoding $true
    [System.IO.File]::WriteAllText($Path, $Text, $utf8Bom)
}

function Invoke-ProdPsqlCopy([string]$SqlSelect, [string]$OutFile) {
    $id = [guid]::NewGuid().ToString("N")
    $tmpSql = Join-Path $env:TEMP ("orid_copy_" + $id + ".sql")
    $errOut = Join-Path $env:TEMP ("orid_csv_" + $id + ".err")
    $containerCsv = "/tmp/orid_export_$id.csv"
    $escaped = $SqlSelect.Trim().TrimEnd(";")
    # Server-side COPY allows multi-line SELECT; then docker cp to host.
    $script = @"
COPY (
$escaped
) TO '$containerCsv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');
"@
    [System.IO.File]::WriteAllText($tmpSql, $script, [System.Text.UTF8Encoding]::new($false))
    try {
        docker cp $tmpSql "${DbContainer}:/tmp/orid_copy.sql" | Out-Null
        $p = Start-Process -FilePath "docker" `
            -ArgumentList @(
                "exec", $DbContainer,
                "psql", "-U", $PostgresUser, "-d", $PostgresDb,
                "-v", "ON_ERROR_STOP=1", "-f", "/tmp/orid_copy.sql"
            ) `
            -RedirectStandardOutput (Join-Path $env:TEMP ("orid_csv_" + $id + ".out")) `
            -RedirectStandardError $errOut `
            -NoNewWindow -Wait -PassThru
        if ($p.ExitCode -ne 0) {
            $errText = ""
            if (Test-Path $errOut) { $errText = Get-Content -Raw -Path $errOut }
            throw "psql COPY failed for $OutFile : $errText"
        }
        $hostRaw = Join-Path $env:TEMP ("orid_csv_host_" + $id + ".csv")
        docker cp "${DbContainer}:${containerCsv}" $hostRaw | Out-Null
        if (-not (Test-Path $hostRaw)) { throw "CSV output missing for $OutFile" }
        $text = [System.IO.File]::ReadAllText($hostRaw, [System.Text.Encoding]::UTF8)
        Save-Utf8BomCsv -Path $OutFile -Text $text
        Remove-Item -Force -ErrorAction SilentlyContinue $hostRaw
    }
    finally {
        Remove-Item -Force -ErrorAction SilentlyContinue $tmpSql, $errOut
        Remove-Item -Force -ErrorAction SilentlyContinue (Join-Path $env:TEMP ("orid_csv_" + $id + ".out"))
        docker exec $DbContainer rm -f /tmp/orid_copy.sql $containerCsv 2>$null | Out-Null
    }
}

try {
    if (-not (Test-Path $EnvFile)) { throw "Missing $EnvFile" }
    if (-not (Test-Path $ComposeFile)) { throw "Missing $ComposeFile" }

    $PostgresUser = Get-DotEnvValue $EnvFile "POSTGRES_USER"
    $PostgresDb = Get-DotEnvValue $EnvFile "POSTGRES_DB"
    if (-not $PostgresUser -or -not $PostgresDb) {
        throw "POSTGRES_USER / POSTGRES_DB missing in $EnvFile"
    }

    New-Item -ItemType Directory -Force -Path $SnapshotsRoot | Out-Null
    New-Item -ItemType Directory -Force -Path (Split-Path $MasterLog) | Out-Null

    $Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $SnapDir = Join-Path $SnapshotsRoot $Timestamp
    New-Item -ItemType Directory -Force -Path $SnapDir | Out-Null

    Write-Log "Starting backup snapshot $Timestamp"

    docker compose -p $ComposeProject -f $ComposeFile --env-file $EnvFile config | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "compose config failed" }

    docker compose -p $ComposeProject -f $ComposeFile --env-file $EnvFile up -d db | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "failed to start db" }

    $ready = $false
    for ($i = 1; $i -le 30; $i++) {
        docker compose -p $ComposeProject -f $ComposeFile --env-file $EnvFile exec -T db pg_isready -U $PostgresUser -d $PostgresDb | Out-Null
        if ($LASTEXITCODE -eq 0) { $ready = $true; break }
        Start-Sleep -Seconds 2
    }
    if (-not $ready) { throw "database not ready" }

    $DbContainer = "orid-prod-db-1"
    $DumpFile = Join-Path $SnapDir ("orid_prod_" + $Timestamp + ".dump")
    Write-Log "Creating dump $DumpFile"
    # Binary dump must go through cmd redirection; PowerShell pipes corrupt -Fc output.
    $dumpCmd = "docker compose -p `"$ComposeProject`" -f `"$ComposeFile`" --env-file `"$EnvFile`" exec -T db pg_dump -U `"$PostgresUser`" -d `"$PostgresDb`" -Fc > `"$DumpFile`""
    cmd.exe /c $dumpCmd
    if ($LASTEXITCODE -ne 0) {
        if (Test-Path $DumpFile) { Remove-Item -Force $DumpFile }
        throw "pg_dump failed"
    }
    if (-not (Test-Path $DumpFile) -or (Get-Item $DumpFile).Length -le 0) {
        if (Test-Path $DumpFile) { Remove-Item -Force $DumpFile }
        throw "dump file empty"
    }

    $ExperimentFilter = @"
c.year = 2026
AND c.external_code IN ('501','502','503','504','505','506','508','509')
AND c.archived_at IS NULL
"@

    Write-Log "Exporting research CSVs"
    Invoke-ProdPsqlCopy @"
SELECT
  c.external_code AS class_code,
  c.name AS class_name,
  c.study_condition AS class_condition,
  m.seat_no,
  u.email AS login,
  u.display_name,
  u.role,
  u.orid_condition,
  u.is_active,
  u.is_verified,
  u.password_change_used
FROM student_class_memberships m
JOIN classes c ON c.id = m.class_id
JOIN "user" u ON u.id = m.student_id
WHERE $ExperimentFilter
ORDER BY c.external_code, m.seat_no NULLS LAST, u.email
"@ (Join-Path $SnapDir "01_roster.csv")

    Invoke-ProdPsqlCopy @"
SELECT
  c.external_code AS class_code,
  c.study_condition AS class_condition,
  u.email AS login,
  u.display_name,
  u.orid_condition,
  r.week,
  r.task_type,
  r.condition AS summary_condition,
  r.word_count,
  r.save_count,
  r.revision_count,
  r.guide_use_count,
  r.badge_count,
  r.is_submitted,
  r.updated_at
FROM orid_weekly_research_summaries r
JOIN "user" u ON u.id = r.user_id
LEFT JOIN classes c ON c.id = r.class_id
WHERE r.week BETWEEN 1 AND 7
  AND r.user_id IN (
  SELECT m.student_id
  FROM student_class_memberships m
  JOIN classes c2 ON c2.id = m.class_id
  WHERE c2.year = 2026
    AND c2.external_code IN ('501','502','503','504','505','506','508','509')
    AND c2.archived_at IS NULL
)
ORDER BY c.external_code NULLS LAST, u.email, r.week
"@ (Join-Path $SnapDir "02_research_summary.csv")

    Invoke-ProdPsqlCopy @"
SELECT
  c.external_code AS class_code,
  u.email AS login,
  u.display_name,
  u.orid_condition,
  w.week,
  w.updated_at,
  COALESCE(w.content::jsonb #>> '{stages,O,d1}', '') AS o_text,
  COALESCE(w.content::jsonb #>> '{stages,R,d1}', '') AS r_text,
  COALESCE(w.content::jsonb #>> '{stages,I,d1}', '') AS i_text,
  COALESCE(w.content::jsonb #>> '{stages,D,d1}', '') AS d_text,
  COALESCE(w.content::jsonb ->> 'synthesis_draft', '') AS synthesis_draft
FROM orid_week_submissions w
JOIN "user" u ON u.id = w.user_id
JOIN student_class_memberships m ON m.student_id = u.id
JOIN classes c ON c.id = m.class_id
WHERE $ExperimentFilter
  AND w.week BETWEEN 1 AND 7
ORDER BY c.external_code, u.email, w.week
"@ (Join-Path $SnapDir "03_writings.csv")

    Invoke-ProdPsqlCopy @"
SELECT
  c.external_code AS class_code,
  u.email AS login,
  u.orid_condition,
  a.stage,
  a.draft,
  a.condition,
  a.source,
  a.word_count,
  a.feedback_strength,
  a.created_at AS attempt_at,
  f.ok AS feedback_ok,
  f.created_at AS feedback_at
FROM orid_stage_attempts a
JOIN "user" u ON u.id = a.user_id
JOIN student_class_memberships m ON m.student_id = u.id
JOIN classes c ON c.id = m.class_id
LEFT JOIN LATERAL (
  SELECT fe.ok, fe.created_at
  FROM orid_feedback_events fe
  WHERE fe.attempt_id = a.id
  ORDER BY fe.created_at DESC
  LIMIT 1
) f ON TRUE
WHERE $ExperimentFilter
ORDER BY c.external_code, u.email, a.created_at
"@ (Join-Path $SnapDir "04_feedback_log.csv")

    Invoke-ProdPsqlCopy @"
SELECT
  c.external_code AS class_code,
  u.email AS login,
  u.orid_condition,
  b.week,
  b.task_type,
  b.condition,
  b.badge_id,
  b.word_count,
  b.feedback_count,
  b.prompt_view_count,
  b.used_feedback_or_prompt,
  b.created_at
FROM orid_badge_events b
JOIN "user" u ON u.id = b.user_id
JOIN student_class_memberships m ON m.student_id = u.id
JOIN classes c ON c.id = m.class_id
WHERE $ExperimentFilter
  AND b.week BETWEEN 1 AND 7
ORDER BY c.external_code, u.email, b.week, b.created_at
"@ (Join-Path $SnapDir "05_badge_events.csv")

    $manifest = @"
snapshot=$Timestamp
dump=$(Split-Path -Leaf $DumpFile)
dump_bytes=$((Get-Item $DumpFile).Length)
roster=01_roster.csv
research_summary=02_research_summary.csv
writings=03_writings.csv
feedback_log=04_feedback_log.csv
badge_events=05_badge_events.csv
note=Full DB dump plus experiment-class research CSVs (501-506,508,509). Open CSV in Excel. Restore dump only via restore-db.bat.
"@
    Save-Utf8BomCsv -Path (Join-Path $SnapDir "README.txt") -Text $manifest

    Write-Log "Backup snapshot complete: $SnapDir"
    Write-Host ""
    Write-Host "Snapshot folder:"
    Write-Host "  $SnapDir"
    Get-ChildItem $SnapDir | ForEach-Object {
        Write-Host ("  - {0} ({1:N0} bytes)" -f $_.Name, $_.Length)
    }
    exit 0
}
catch {
    Write-Log ("Backup FAILED: " + $_.Exception.Message)
    Write-Error $_.Exception.Message
    exit 1
}
