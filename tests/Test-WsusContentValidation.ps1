param([string]$FunctionsSource, [string]$PrepareSource)
$ErrorActionPreference = 'Stop'
if (-not $FunctionsSource) {
    $FunctionsSource = Get-Content (Join-Path $PSScriptRoot '..\assets\wsus-patch-month-functions.ps1') -Raw
}
if (-not $PrepareSource) {
    $PrepareSource = Get-Content (Join-Path $PSScriptRoot '..\assets\prepare-wsus-import.ps1') -Raw
}
. ([scriptblock]::Create($FunctionsSource))
$script:Assertions = 0
function Assert-True {
    param([bool]$Condition, [string]$Message)
    if (-not $Condition) { throw $Message }
    $script:Assertions++
}
$script:ContentRoot = 'C:\Example\WsusContent'
$names = @(('AA/' + ('a' * 40) + '.cab'), ('BB/' + ('b' * 40) + '.cab'), ('CC/' + ('c' * 40) + '.cab'))
$script:Existing = @{
    $script:ContentRoot = @{ Length = 0 }
    (Join-Path $script:ContentRoot $names[0]) = @{ Length = 3; Hash = 'a' * 64 }
    (Join-Path $script:ContentRoot $names[2]) = @{ Length = 1; Hash = 'b' * 64 }
}
$script:HashCalls = 0
function Get-ItemProperty { param($Path) [pscustomobject]@{ ContentDir = $script:ContentRoot } }
function Get-CimInstance { param($ClassName, $Filter) [pscustomobject]@{ FreeSpace = 100GB } }
function Test-Path {
    param($LiteralPath, $PathType)
    $script:Existing.ContainsKey([string]$LiteralPath)
}
function Get-Item { param($LiteralPath) [pscustomobject]$script:Existing[[string]$LiteralPath] }
function Get-FileHash {
    param($LiteralPath, $Algorithm)
    $script:HashCalls++
    [pscustomobject]@{ Hash = $script:Existing[[string]$LiteralPath].Hash }
}
$files = @($names | ForEach-Object {
    [pscustomobject]@{ FileUri = 'http://example.invalid/Content/' + $_; Type = 'SelfContained'; TotalBytes = 3 }
})
$update = [pscustomobject]@{ Files = $files }
$update | Add-Member ScriptMethod GetInstallableItems { [pscustomobject]@{ Files = $this.Files } }
$content = Get-WsusPatchMonthContent @{ Allowed = @{ sample = $update } }
Assert-True ($content.Files.Count -eq 3) 'Keep every selected content path.'
Assert-True ($content.MissingBytes -eq 6) 'Count missing and truncated files for disk budgeting.'
Assert-True ($content.Files[$names[0]].Present) 'Recognize an existing full-length file.'
Assert-True ($script:HashCalls -eq 0) 'Monthly policy checks must not hash payloads.'

# Transfer preparation still detects a same-length corrupt file, but does not
# send an already verified matching file to the downloader for another hash.
$script:Existing[(Join-Path $script:ContentRoot $names[2])].Length = 3
$snapshot = 'snapshot-20261020T000000-' + ('d' * 32)
$manifest = @{
    schemaVersion = 1; express = $false; languages = @('en'); snapshot = $snapshot
    metadata = @{ path = "$snapshot/metadata.xml.gz"; sha256 = 'd' * 64; length = 1 }
    updates = @(@{ id = 'example'; revision = 1 })
    files = @($names | ForEach-Object { @{ relativePath = $_; length = 3; sha256 = 'a' * 64 } })
}
$script:ManifestJson = $manifest | ConvertTo-Json -Depth 6
function Get-Content { param($LiteralPath, [switch]$Raw) $script:ManifestJson }
function Import-Module { param($Name) }
$subscription = [pscustomobject]@{}
$subscription | Add-Member ScriptMethod GetSynchronizationStatus { 'NotProcessing' }
$script:Server = [pscustomobject]@{ Subscription = $subscription }
$script:Server | Add-Member ScriptMethod GetConfiguration {
    [pscustomobject]@{ IsReplicaServer = $false; HostBinariesOnMicrosoftUpdate = $false }
}
$script:Server | Add-Member ScriptMethod GetSubscription { $this.Subscription }
function Get-WsusServer { $script:Server }
$Ansible = @{ CheckMode = $true; Changed = $false; Result = @{} }
& ([scriptblock]::Create($PrepareSource)) -ManifestPath 'C:\Example\manifest.json' -ReserveGB 4
$queued = @($Ansible.Result.FilesToDownload | ForEach-Object relativePath | Sort-Object)
Assert-True ($script:HashCalls -eq 2) 'Hash each existing internal file once.'
Assert-True ($queued.Count -eq 2) 'Queue only missing or mismatched payloads.'
Assert-True (($queued -join ',') -eq (($names[1..2] | Sort-Object) -join ',')) 'Do not queue a verified matching payload.'
Assert-True ($Ansible.Result.RequiredBytes -eq 7) 'Budget replacement files and metadata.'
Write-Output "Passed $Assertions content validation assertions."
