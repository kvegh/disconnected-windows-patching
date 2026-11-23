# Show the proof history written by playbooks/proof-report.yml, one block per
# stage, values that changed since the previous line in green. Display only.
$log = Join-Path $PSScriptRoot 'proof-log.csv'
if (-not (Test-Path -LiteralPath $log)) { Write-Host "No proof history yet: $log" -ForegroundColor Yellow; return }
$previous = $null
foreach ($row in Import-Csv -LiteralPath $log) {
    Write-Host ("{0}  {1}  {2}" -f $row.utc, $row.host, $row.stage) -ForegroundColor Cyan
    foreach ($column in $row.PSObject.Properties.Name | Where-Object { $_ -notin 'utc', 'host', 'stage' }) {
        $changed = $previous -and $previous.$column -ne $row.$column
        Write-Host ("    {0,-20} {1}" -f $column, $row.$column) -ForegroundColor $(if ($changed) { 'Green' } else { 'Gray' })
    }
    $previous = $row
}
