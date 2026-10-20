[CmdletBinding(SupportsShouldProcess)]
param(
    [Parameter(Mandatory)][string]$FunctionsSource,
    [Parameter(Mandatory)][string]$Month,
    [string[]]$Products,
    [string[]]$Classifications,
    [hashtable]$PrerequisiteMonths = @{},
    [switch]$ValidatePolicy
)
$ErrorActionPreference = 'Stop'
$Ansible.Changed = $false
. ([scriptblock]::Create($FunctionsSource))
Import-Module UpdateServices
$server = Get-WsusServer
$config = $server.GetConfiguration()
if ($config.IsReplicaServer -or $config.HostBinariesOnMicrosoftUpdate) {
    throw 'The patch ceiling may only be applied to autonomous internal WSUS with local update files.'
}
# The existing offline setup retains the Microsoft upstream flag on both
# autonomous servers. Inventory identifies the internal role; only manual
# metadata import is used, and automatic synchronization is disabled below.
$subscription = $server.GetSubscription()
if ([string]$subscription.GetSynchronizationStatus() -ne 'NotProcessing') {
    throw 'Wait for active WSUS synchronization before enforcing the ceiling.'
}
$plan = Get-WsusPatchMonthPlan $server $Month $Products $Classifications $PrerequisiteMonths
$content = Get-WsusPatchMonthContent $plan
$summary = Get-WsusPatchMonthSummary $plan $content
$summary.enabled_automatic_rules = @($server.GetInstallApprovalRules() | Where-Object Enabled).Count
$summary.updates_needing_decline = @($plan.Blocked | Where-Object { -not $_.IsDeclined }).Count
$Ansible.Result = $summary
if ($ValidatePolicy) {
    $problems = @(Get-WsusPatchMonthPolicyViolations $server $plan $content)
    if ($problems.Count -gt 0) {
        throw ('The active WSUS patch ceiling is not ready or has drifted: ' + ($problems -join ', '))
    }
    $summary.policy_verified = $true
    $Ansible.Result = $summary
    return
}
if ($Ansible.CheckMode) { return }
# Finish all identity, graph, EULA and file checks before changing approvals.
if ($summary.pending_license_updates.Count -gt 0) {
    throw 'A selected update requires separate license review and acceptance. No approval policy changes were applied.'
}
if ($content.MissingBytes -gt 0) {
    throw 'The baseline has missing or incomplete internal payloads. Prepare, export and import it before applying the ceiling.'
}
$allComputersId = [guid]'a0a08746-4dbe-4a37-9adf-9e7652c0b421'
$groups = @($server.GetComputerTargetGroups() | Where-Object { $_.Id -eq $allComputersId })
if ($groups.Count -ne 1) { throw 'The built-in All Computers group could not be identified uniquely.' }
$allComputers = $groups[0]
foreach ($rule in $server.GetInstallApprovalRules()) {
    if ($rule.Enabled) {
        $rule.Enabled = $false
        $rule.Save()
        $Ansible.Changed = $true
    }
}
if ($config.AutoRefreshUpdateApprovals -or $config.AutoApproveWsusInfrastructureUpdates) {
    $config.AutoRefreshUpdateApprovals = $false
    $config.AutoApproveWsusInfrastructureUpdates = $false
    $config.Save()
    $Ansible.Changed = $true
}
if ($subscription.SynchronizeAutomatically) {
    $subscription.SynchronizeAutomatically = $false
    $subscription.Save()
    $Ansible.Changed = $true
}
# Decline removes approvals across groups and revisions, so inherited approvals
# cannot defeat the ceiling. Historical unselected CUs are blocked too: a baseline
# is the selected cumulative releases plus their prerequisites, not every old CU.
foreach ($update in $plan.Blocked) {
    if (-not $update.IsDeclined) {
        $update.Decline()
        $Ansible.Changed = $true
    }
}
foreach ($update in $plan.Explicit.Values) {
    $approvals = @($update.GetUpdateApprovals())
    $wanted = @($approvals | Where-Object {
        [string]$_.Action -eq 'Install' -and $_.ComputerTargetGroupId -eq $allComputersId -and
        $_.UpdateId.RevisionNumber -eq $update.Id.RevisionNumber -and
        $_.UpdateId.UpdateId -eq $update.Id.UpdateId -and $_.Deadline -eq [datetime]::MaxValue
    })
    foreach ($approval in $approvals) {
        # Bundle approvals are managed by the parent; the API forbids Delete().
        if ([string]$approval.Action -ne 'Bundle' -and $approval -notin $wanted) {
            $approval.Delete()
            $Ansible.Changed = $true
        }
    }
    if ($update.IsDeclined -or $wanted.Count -eq 0) {
        $null = $update.Approve([Microsoft.UpdateServices.Administration.UpdateApprovalAction]::Install, $allComputers)
        $Ansible.Changed = $true
    }
}
# WSUS may need a short interval to recognize already imported local content.
$readyDeadline = (Get-Date).AddMinutes(5)
do {
    $notReady = @($plan.Explicit.Values | Where-Object {
        $_.Refresh()
        [string]$_.State -ne 'Ready'
    })
    if ($notReady.Count -eq 0) { break }
    if ((Get-Date) -ge $readyDeadline) {
        throw 'Selected WSUS updates did not become ready; no successful ceiling marker was written.'
    }
    Start-Sleep -Seconds 10
} while ($true)
# Re-read the catalogue to detect concurrent imports or approval changes.
$violations = @(Get-WsusPatchMonthPolicyViolations $server $plan $content)
if ($violations.Count -gt 0) {
    # Fail closed for any remaining undesired catalogue entries.
    foreach ($update in @($server.GetUpdates() | Where-Object IsLatestRevision)) {
        if (-not $plan.Allowed.ContainsKey([string]$update.Id.UpdateId) -and -not $update.IsDeclined) {
            $update.Decline()
        }
    }
    throw 'WSUS policy verification failed. Inspect concurrent activity and rerun; no successful ceiling marker was written.'
}
$summary.policy_verified = $true
$summary.offered_updates = $plan.Allowed.Count
$Ansible.Result = $summary
