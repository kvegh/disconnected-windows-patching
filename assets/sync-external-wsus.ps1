[CmdletBinding(SupportsShouldProcess)]
param(
    [string[]]$Products,
    [string[]]$Classifications,
    [string[]]$Languages,
    [int]$AgeDays,
    [int]$MaximumUpdates,
    [int]$ReserveGB,
    [int]$SyncTimeout,
    [int]$DownloadTimeout,
    [string]$GroupName,
    [string]$StatePath
)
$ErrorActionPreference = 'Stop'
$Ansible.Changed = $false
if ($Ansible.CheckMode) { return }
Import-Module UpdateServices
$server = Get-WsusServer
$config = $server.GetConfiguration()
if ($config.IsReplicaServer -or -not $config.SyncFromMicrosoftUpdate) {
    throw 'Only an autonomous external WSUS synchronizing from Microsoft may run this operation.'
}
$subscription = $server.GetSubscription()
if ([string]$subscription.GetSynchronizationStatus() -ne 'NotProcessing') {
    throw 'Another synchronization is active. Wait for it before launching this job.'
}
if ($config.HostBinariesOnMicrosoftUpdate -or $config.DownloadExpressPackages -or
    -not $config.DownloadUpdateBinariesAsNeeded -or $config.AllUpdateLanguagesEnabled -or
    ((@($config.GetEnabledUpdateLanguages() | Sort-Object) -join ',') -ne
     (@($Languages | Sort-Object -Unique) -join ','))) {
    $config.HostBinariesOnMicrosoftUpdate = $false
    $config.DownloadExpressPackages = $false
    $config.DownloadUpdateBinariesAsNeeded = $true
    $config.AllUpdateLanguagesEnabled = $false
    $config.SetEnabledUpdateLanguages($Languages)
    $config.Save()
    $Ansible.Changed = $true
}
if ($subscription.SynchronizeAutomatically) {
    $subscription.SynchronizeAutomatically = $false
    $subscription.Save()
    $Ansible.Changed = $true
}
function Wait-Synchronization {
    $deadline = (Get-Date).AddSeconds($SyncTimeout)
    do {
        Start-Sleep -Seconds 10
        if ((Get-Date) -gt $deadline) {
            $subscription.StopSynchronization()
            throw 'WSUS synchronization timed out.'
        }
    } while ([string]$subscription.GetSynchronizationStatus() -ne 'NotProcessing')
    $info = $subscription.GetLastSynchronizationInfo()
    if ([string]$info.Result -ne 'Succeeded') {
        throw "WSUS synchronization failed: $($info.Result): $($info.ErrorText)"
    }
}
# Fetch the product catalogue before selecting newly published OS categories.
$subscription.StartSynchronizationForCategoryOnly()
$Ansible.Changed = $true
Wait-Synchronization
$categories = New-Object Microsoft.UpdateServices.Administration.UpdateCategoryCollection
foreach ($title in $Products) {
    $matches = @($server.GetUpdateCategories() | Where-Object { $_.Title -eq $title })
    if ($matches.Count -ne 1) { throw "Product must match exactly one category: $title" }
    $null = $categories.Add($matches[0])
}
$classes = New-Object Microsoft.UpdateServices.Administration.UpdateClassificationCollection
foreach ($title in $Classifications) {
    $matches = @($server.GetUpdateClassifications() | Where-Object { $_.Title -eq $title })
    if ($matches.Count -ne 1) { throw "Classification must match exactly once: $title" }
    $null = $classes.Add($matches[0])
}
$subscription.SetUpdateCategories($categories)
$subscription.SetUpdateClassifications($classes)
$subscription.Save()
$subscription.StartSynchronization()
Wait-Synchronization
$cutoff = (Get-Date).ToUniversalTime().AddDays(-$AgeDays)
$selected = @($server.GetUpdates() | Where-Object {
    $update = $_
    -not $update.IsDeclined -and -not $update.IsSuperseded -and $update.IsLatestRevision -and
    $update.CreationDate.ToUniversalTime() -ge $cutoff -and
    $update.Title -notmatch '(?i)\b(preview|arm64|x86|itanium)\b' -and
    $update.UpdateClassificationTitle -in $Classifications -and
    @($update.ProductTitles | Where-Object { $_ -in $Products }).Count -gt 0
})
if ($selected.Count -eq 0) { throw 'No current updates matched the requested products and classifications.' }
# Include file-bearing prerequisites even when older or superseded (e.g. checkpoint updates).
$updates = @{}
$queue = New-Object 'System.Collections.Generic.Queue[object]'
foreach ($update in $selected) { $queue.Enqueue($update) }
while ($queue.Count -gt 0) {
    $update = $queue.Dequeue()
    $key = [string]$update.Id.UpdateId
    if ($updates.ContainsKey($key)) { continue }
    $updates[$key] = $update
    foreach ($required in $update.GetRelatedUpdates(
        [Microsoft.UpdateServices.Administration.UpdateRelationship]::UpdatesRequiredByThisUpdate)) {
        if (@($required.GetInstallableItems()).Count -gt 0) {
            if ($required.IsDeclined) { throw 'A required prerequisite is declined; inspect before continuing.' }
            $queue.Enqueue($required)
        }
    }
}
if ($updates.Count -gt $MaximumUpdates) {
    throw "Selection including prerequisites has $($updates.Count) updates, above the configured limit $MaximumUpdates."
}
$content = (Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Update Services\Server\Setup').ContentDir.TrimEnd('\')
$drive = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='$([IO.Path]::GetPathRoot($content).TrimEnd('\'))'"
$files = @{}
foreach ($update in $updates.Values) {
    foreach ($installable in $update.GetInstallableItems()) {
        foreach ($file in $installable.Files) {
            # Conservative estimate; files already on disk still count in this budget.
            if ([string]$file.Type -ne 'Express') { $files[[string]$file.OriginUri] = [long]$file.TotalBytes }
        }
    }
}
$estimated = [long](($files.Values | Measure-Object -Sum).Sum)
if ($estimated + ($ReserveGB * 1GB) -gt $drive.FreeSpace) {
    throw 'Selected update files exceed free disk space plus the reserve. Narrow selection or provide more storage.'
}
$group = @($server.GetComputerTargetGroups() | Where-Object Name -eq $GroupName)
if ($group.Count -eq 0) { $group = @($server.CreateComputerTargetGroup($GroupName)) }
if (@($group[0].GetComputerTargets()).Count -ne 0) {
    throw 'The download-only group must contain no computers.'
}
foreach ($update in $updates.Values) {
    if ($update.RequiresLicenseAgreementAcceptance) { $update.AcceptLicenseAgreement() }
    $approval = @($update.GetUpdateApprovals($group[0]) | Where-Object { [string]$_.Action -eq 'Install' })
    if ($approval.Count -eq 0) {
        $null = $update.Approve([Microsoft.UpdateServices.Administration.UpdateApprovalAction]::Install, $group[0])
    }
    if ([string]$update.State -in @('Failed', 'Cancelled', 'LicenseAgreementFailed')) { $update.ResumeDownload() }
}
$deadline = (Get-Date).AddSeconds($DownloadTimeout)
do {
    $notReady = @()
    foreach ($update in $updates.Values) {
        $update.Refresh()
        if ([string]$update.State -in @('Failed', 'LicenseAgreementFailed', 'InstallationImpossible')) {
            throw "An update cannot be downloaded: $($update.Id.UpdateId), state $($update.State)"
        }
        if ([string]$update.State -ne 'Ready') { $notReady += $update }
    }
    if ($notReady.Count -eq 0) { break }
    $drive = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='$($drive.DeviceID)'"
    if ($drive.FreeSpace -lt ($ReserveGB * 1GB)) {
        foreach ($update in $notReady) { $update.CancelDownload() }
        throw 'Disk reserve reached; pending selection downloads cancelled.'
    }
    if ((Get-Date) -gt $deadline) {
        throw 'Update binary downloads timed out. Downloads may continue in WSUS; export remains blocked until ready.'
    }
    Start-Sleep -Seconds 30
} while ($true)
$selection = @{
    completedUtc = (Get-Date).ToUniversalTime().ToString('o')
    languages = @($Languages)
    express = $false
    products = @($Products)
    classifications = @($Classifications)
    updates = @($updates.Values | ForEach-Object {
        @{ id = [string]$_.Id.UpdateId; revision = $_.Id.RevisionNumber; title = $_.Title }
    } | Sort-Object id)
}
$selection | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath (Join-Path $StatePath 'selection.json') -Encoding UTF8
$Ansible.Result = @{ SelectedUpdates = $updates.Count; ReadyUpdates = $updates.Count; EstimatedBytes = $estimated }
