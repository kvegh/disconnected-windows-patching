[CmdletBinding(SupportsShouldProcess)]
param([string]$ExportRoot, [string]$StatePath)
$ErrorActionPreference = 'Stop'
$Ansible.Changed = $false
if ($Ansible.CheckMode) { return }
Import-Module UpdateServices
$server = Get-WsusServer
$config = $server.GetConfiguration()
if ($config.IsReplicaServer -or $config.HostBinariesOnMicrosoftUpdate -or $config.DownloadExpressPackages) {
    throw 'Export requires autonomous WSUS, local full update files and express disabled.'
}
if ([string]$server.GetSubscription().GetSynchronizationStatus() -ne 'NotProcessing') {
    throw 'Wait until metadata synchronization has finished before exporting.'
}
$progress = $server.GetContentDownloadProgress()
if ($progress.DownloadedBytes -lt $progress.TotalBytesToDownload) {
    throw 'Update files are still downloading. Complete synchronization before export.'
}
$selectionPath = Join-Path $StatePath 'selection.json'
if (-not (Test-Path -LiteralPath $selectionPath)) { throw 'Run the external synchronization playbook first.' }
$selection = Get-Content -LiteralPath $selectionPath -Raw | ConvertFrom-Json
$selectionHash = (Get-FileHash -LiteralPath $selectionPath -Algorithm SHA256).Hash.ToLowerInvariant()
if (@($selection.updates).Count -eq 0) { throw 'Cannot publish an empty update selection.' }
foreach ($entry in $selection.updates) {
    $id = New-Object Microsoft.UpdateServices.Administration.UpdateRevisionId ([guid]$entry.id), ([int]$entry.revision)
    if ([string]$server.GetUpdate($id).State -ne 'Ready') { throw 'A selected update does not have all required files ready.' }
}
if ($config.AllUpdateLanguagesEnabled -or
    ((@($config.GetEnabledUpdateLanguages() | Sort-Object) -join ',') -ne
     (@($selection.languages | Sort-Object) -join ','))) { throw 'Language configuration changed since synchronization.' }
$content = (Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Update Services\Server\Setup').ContentDir.TrimEnd('\')
if ((Split-Path $content -Leaf) -ne 'WsusContent') { $content = Join-Path $content 'WsusContent' }
# Include all downloaded content and EULAs, preserving the WSUS directory layout.
$fileEntries = @(Get-ChildItem -LiteralPath $content -File -Recurse |
    Where-Object { $_.Name -ine 'web.config' } | ForEach-Object {
    if (($_.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'Unexpected reparse point in update content.' }
    [ordered]@{
        relativePath = $_.FullName.Substring($content.Length + 1).Replace('\', '/')
        length = $_.Length
        sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    }
} | Sort-Object relativePath)
if ($fileEntries.Count -eq 0) { throw 'No downloaded update files were found.' }
$currentPath = Join-Path $ExportRoot 'current.json'
if (Test-Path -LiteralPath $currentPath) {
    $current = Get-Content -LiteralPath $currentPath -Raw | ConvertFrom-Json
    $currentMetadata = Join-Path $ExportRoot $current.metadata.path
    if ($current.selectionHash -eq $selectionHash -and (Test-Path -LiteralPath $currentMetadata) -and
        (Get-FileHash -LiteralPath $currentMetadata -Algorithm SHA256).Hash.ToLowerInvariant() -eq $current.metadata.sha256 -and
        (ConvertTo-Json -InputObject @($current.files) -Depth 5 -Compress) -eq
        (ConvertTo-Json -InputObject $fileEntries -Depth 5 -Compress)) {
        $Ansible.Result = @{ Snapshot = $current.snapshot; Files = $fileEntries.Count; Reused = $true }
        return
    }
}
$snapshot = 'snapshot-' + (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmss') + '-' + [guid]::NewGuid().ToString('N')
$folder = Join-Path $ExportRoot $snapshot
$null = New-Item -Path $folder -ItemType Directory
$logDirectory = Join-Path $StatePath 'logs'
$metadata = Join-Path $folder 'metadata.xml.gz'
$log = Join-Path $logDirectory "$snapshot-export.log"
$utility = Join-Path $env:ProgramFiles 'Update Services\Tools\WsusUtil.exe'
& $utility export $metadata $log
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $metadata) -or (Get-Item $metadata).Length -eq 0) {
    throw "WSUS metadata export failed: exit code $LASTEXITCODE. Inspect the local export log."
}
$manifest = [ordered]@{
    schemaVersion = 1
    snapshot = $snapshot
    createdUtc = (Get-Date).ToUniversalTime().ToString('o')
    selectionHash = $selectionHash
    languages = @($selection.languages)
    express = $false
    products = @($selection.products)
    classifications = @($selection.classifications)
    updates = @($selection.updates)
    metadata = @{
        path = "$snapshot/metadata.xml.gz"
        length = (Get-Item $metadata).Length
        sha256 = (Get-FileHash -LiteralPath $metadata -Algorithm SHA256).Hash.ToLowerInvariant()
    }
    files = $fileEntries
}
$json = $manifest | ConvertTo-Json -Depth 12
$encoding = New-Object Text.UTF8Encoding $false
[IO.File]::WriteAllText((Join-Path $folder 'manifest.json'), $json, $encoding)
# Publish only after export, file enumeration and hashing have succeeded.
$temporary = Join-Path $ExportRoot 'current.pending'
[IO.File]::WriteAllText($temporary, $json, $encoding)
if (Test-Path -LiteralPath $currentPath) {
    [IO.File]::Replace($temporary, $currentPath, $null)
} else { [IO.File]::Move($temporary, $currentPath) }
$Ansible.Changed = $true
$Ansible.Result = @{ Snapshot = $snapshot; Files = $fileEntries.Count; Reused = $false }
