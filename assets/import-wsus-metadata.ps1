[CmdletBinding(SupportsShouldProcess)]
param([string]$SnapshotPath, [string]$ContentPath)
$ErrorActionPreference = 'Stop'
$Ansible.Changed = $false
if ($Ansible.CheckMode) { return }
$manifest = Get-Content -LiteralPath (Join-Path $SnapshotPath 'manifest.json') -Raw | ConvertFrom-Json
$metadata = Join-Path $SnapshotPath 'metadata.xml.gz'
if ((Get-FileHash -LiteralPath $metadata -Algorithm SHA256).Hash.ToLowerInvariant() -ne $manifest.metadata.sha256) {
    throw 'Metadata checksum differs from the verified manifest.'
}
foreach ($file in $manifest.files) {
    $destination = Join-Path $ContentPath $file.relativePath
    if (-not (Test-Path -LiteralPath $destination) -or (Get-Item $destination).Length -ne $file.length -or
        (Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash.ToLowerInvariant() -ne $file.sha256) {
        throw 'An update file is missing or corrupt. Metadata import was not started.'
    }
}
Import-Module UpdateServices
$server = Get-WsusServer
if ($server.GetConfiguration().IsReplicaServer -or
    [string]$server.GetSubscription().GetSynchronizationStatus() -ne 'NotProcessing') {
    throw 'Cannot import into a replica server or during synchronization.'
}
$marker = Join-Path $SnapshotPath 'imported.sha256'
$alreadyImported = (Test-Path -LiteralPath $marker) -and
    (Get-Content -LiteralPath $marker -Raw).Trim() -eq $manifest.metadata.sha256
if (-not $alreadyImported) {
    $utility = Join-Path $env:ProgramFiles 'Update Services\Tools\WsusUtil.exe'
    $log = Join-Path $SnapshotPath ('import-' + [guid]::NewGuid().ToString('N') + '.log')
    & $utility import $metadata $log
    if ($LASTEXITCODE -ne 0) { throw "WSUS metadata import failed: $LASTEXITCODE. Inspect the local import log." }
    $Ansible.Changed = $true
}
# WSUSutil transfers metadata, not deployment approvals. Verify every selected revision exists.
foreach ($entry in $manifest.updates) {
    $id = New-Object Microsoft.UpdateServices.Administration.UpdateRevisionId ([guid]$entry.id), ([int]$entry.revision)
    $null = $server.GetUpdate($id)
}
$Ansible.Result = @{
    Snapshot = $manifest.snapshot
    VerifiedFiles = @($manifest.files).Count
    VerifiedUpdates = @($manifest.updates).Count
    Imported = -not $alreadyImported
    ClientApprovalsChanged = $false
}
