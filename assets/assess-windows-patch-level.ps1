[CmdletBinding(SupportsShouldProcess)]
param(
    [Parameter(Mandatory)][string]$BaselineName,
    [Parameter(Mandatory)][hashtable]$Baselines
)
$ErrorActionPreference = 'Stop'
$Ansible.Changed = $false
$version = Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion'
$build = [string]$version.CurrentBuildNumber
$revision = [int]$version.UBR
if (-not $Baselines.ContainsKey($build)) {
    throw 'This OS build has no configured patch baseline. Supply an appropriate baseline before comparing it.'
}
$baseline = $Baselines[$build]
$targetRevision = [int]$baseline.revision
$comparison = if ($revision -lt $targetRevision) { 'below' }
    elseif ($revision -gt $targetRevision) { 'above' } else { 'at' }
$ids = @(Get-HotFix | Select-Object -ExpandProperty HotFixID | Sort-Object -Unique)
$dotnetMatches = @($baseline.dotnet_kbs | Where-Object { $_ -in $ids })
$cbsReboot = Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending'
$wuReboot = Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired'
$os = Get-CimInstance Win32_OperatingSystem
$Ansible.Result = @{
    schema_version = 1
    assessed_utc = (Get-Date).ToUniversalTime().ToString('o')
    os_name = [string]$os.Caption
    installed_build = "$build.$revision"
    baseline_name = $BaselineName
    baseline_build = "$build.$targetRevision"
    baseline_kb = [string]$baseline.kb
    comparison = $comparison
    exact_os_kb_present = ([string]$baseline.kb -in $ids)
    exact_dotnet_kbs_present = @($dotnetMatches)
    installed_hotfix_ids = @($ids)
    reboot_pending = [bool]($cbsReboot -or $wuReboot)
}
