[CmdletBinding(SupportsShouldProcess)]
param(
    [Parameter(Mandatory)][string]$FunctionsSource,
    [Parameter(Mandatory)][string]$Month,
    [string[]]$Products,
    [string[]]$Classifications,
    [string[]]$Languages,
    [hashtable]$PrerequisiteMonths = @{},
    [int]$MaximumUpdates,
    [int]$ReserveGB,
    [int]$DownloadTimeout,
    [string]$GroupName
)
$ErrorActionPreference = 'Stop'
$Ansible.Changed = $false
. ([scriptblock]::Create($FunctionsSource))
Import-Module UpdateServices
$server = Get-WsusServer
$config = $server.GetConfiguration()
if ($config.IsReplicaServer -or -not $config.SyncFromMicrosoftUpdate -or
    $config.HostBinariesOnMicrosoftUpdate -or $config.DownloadExpressPackages) {
    throw 'Baseline preparation requires autonomous external WSUS with local full content.'
}
if ([string]$server.GetSubscription().GetSynchronizationStatus() -ne 'NotProcessing') {
    throw 'Wait for the active metadata synchronization before preparing a baseline.'
}
if ($config.AllUpdateLanguagesEnabled -or
    ((@($config.GetEnabledUpdateLanguages() | Sort-Object) -join ',') -ne
     (@($Languages | Sort-Object -Unique) -join ','))) {
    throw 'Configured download languages differ from the pipeline; reconcile them before preparing content.'
}
$plan = Get-WsusPatchMonthPlan $server $Month $Products $Classifications $PrerequisiteMonths
if ($plan.Allowed.Count -gt $MaximumUpdates) {
    throw 'The explicit monthly baseline including prerequisites exceeds the configured selection bound.'
}
$content = Get-WsusPatchMonthContent $plan
$summary = Get-WsusPatchMonthSummary $plan $content
$Ansible.Result = $summary
if ($Ansible.CheckMode) { return }
if ($summary.pending_license_updates.Count -gt 0) {
    throw 'A selected update requires license acceptance. Review and accept its agreement separately; this job never accepts licenses.'
}
if ($content.MissingBytes + ($ReserveGB * 1GB) -gt $content.FreeBytes) {
    throw 'Missing baseline content exceeds the available disk budget and reserve.'
}
$group = @($server.GetComputerTargetGroups() | Where-Object Name -eq $GroupName)
if ($group.Count -gt 1) { throw 'The download-only group name is ambiguous.' }
if ($group.Count -eq 1 -and @($group[0].GetComputerTargets()).Count -ne 0) {
    throw 'The download-only group must contain no computers.'
}
if ($group.Count -eq 0) {
    $group = @($server.CreateComputerTargetGroup($GroupName))
    $Ansible.Changed = $true
}
# Approving superseded updates explicitly is necessary for historical baselines.
# This empty external group makes content downloadable without targeting clients.
foreach ($update in $plan.Explicit.Values) {
    $approval = @($update.GetUpdateApprovals($group[0]) | Where-Object {
        [string]$_.Action -eq 'Install' -and
        $_.UpdateId.RevisionNumber -eq $update.Id.RevisionNumber -and
        $_.UpdateId.UpdateId -eq $update.Id.UpdateId
    })
    if ($update.IsDeclined -or $approval.Count -eq 0) {
        $null = $update.Approve([Microsoft.UpdateServices.Administration.UpdateApprovalAction]::Install, $group[0])
        $Ansible.Changed = $true
    }
    if ([string]$update.State -in @('Failed', 'Cancelled', 'LicenseAgreementFailed')) {
        $update.ResumeDownload()
        $Ansible.Changed = $true
    }
}
$deadline = (Get-Date).AddSeconds($DownloadTimeout)
do {
    $notReady = @()
    foreach ($update in $plan.Allowed.Values) {
        $update.Refresh()
        if ([string]$update.State -in @('Failed', 'LicenseAgreementFailed', 'InstallationImpossible')) {
            throw "A selected update cannot be downloaded: $($update.Id.UpdateId), state $($update.State)."
        }
        if ([string]$update.State -ne 'Ready') { $notReady += $update }
    }
    if ($notReady.Count -eq 0) { break }
    $contentRoot = (Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Update Services\Server\Setup').ContentDir
    $drive = Get-CimInstance Win32_LogicalDisk -Filter (
        "DeviceID='" + [IO.Path]::GetPathRoot($contentRoot).TrimEnd('\') + "'")
    if ($drive.FreeSpace -lt ($ReserveGB * 1GB)) {
        foreach ($update in $notReady) { $update.CancelDownload() }
        throw 'The disk reserve was reached; pending baseline downloads were cancelled.'
    }
    if ((Get-Date) -gt $deadline) {
        throw 'Baseline download timed out. The internal approval policy has not been changed.'
    }
    Start-Sleep -Seconds 30
} while ($true)
$content = Get-WsusPatchMonthContent $plan
if ($content.MissingBytes -ne 0) { throw 'Selected payload files are missing or incomplete.' }
$summary = Get-WsusPatchMonthSummary $plan $content
$summary.selection = @{
    patchMonth = $Month
    languages = @($Languages)
    express = $false
    products = @($Products)
    classifications = @($Classifications)
    updates = @($summary.selected_updates)
}
$Ansible.Result = $summary
