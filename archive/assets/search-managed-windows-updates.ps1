# Purpose and language choice: [rationale](../docs/supporting-code.md#windows-inspection-and-evidence).
[CmdletBinding(SupportsShouldProcess)]
param()
$ErrorActionPreference = 'Stop'
$Ansible.Changed = $false

# win_updates 3.8.0 can call AcceptEula() even with state:searched or check
# mode. Use only WUA read operations here; native win_updates remains responsible
# for installation and repeated reboots in a normal run.
$session = New-Object -ComObject Microsoft.Update.Session
$session.ClientApplicationID = 'Ansible managed WSUS read-only assessment'
$searcher = $session.CreateUpdateSearcher()
$searcher.ServerSelection = 1 # ssManagedServer; never Microsoft Update.
$searcher.Online = $true
$search = $searcher.Search('IsInstalled = 0')
if ([int]$search.ResultCode -ne 2) {
    throw 'The managed WSUS applicability search was incomplete or unsuccessful.'
}
$updates = @{}
foreach ($update in $search.Updates) {
    $id = [string]$update.Identity.UpdateID
    $title = [string]$update.Title
    $kbs = @($update.KBArticleIDs | ForEach-Object { "KB$_" })
    # The pinned native module concatenates its title string and KB array for
    # accept_list matching. Accept only the observed title or that exact native
    # representation, retaining anchors and rejecting additional title text.
    $nativeMatchText = $title + $kbs
    $updates[$id] = @{
        id = $id
        title = $title
        kb = $kbs
        accept_pattern = '^(?:' + [regex]::Escape($title) + '|' + [regex]::Escape($nativeMatchText) + ')$'
        revision = [int]$update.Identity.RevisionNumber
        hidden = [bool]$update.IsHidden
        eula_accepted = [bool]$update.EulaAccepted
        downloaded = [bool]$update.IsDownloaded
    }
}
# SystemInfo creation is denied in the existing WinRM context even when the
# managed-server search succeeds. Read the same update/CBS reboot indicators
# used by inspect-windows-update-client.ps1 without changing COM permissions.
$cbsReboot = Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending'
$wuReboot = Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired'
$Ansible.Result = @{
    schema_version = 1
    assessed_utc = (Get-Date).ToUniversalTime().ToString('o')
    source = 'managed_server'
    found_update_count = $updates.Count
    hidden_update_count = @($updates.Values | Where-Object hidden).Count
    pending_eula_count = @($updates.Values | Where-Object { -not $_.eula_accepted }).Count
    reboot_required = [bool]($cbsReboot -or $wuReboot)
    updates = $updates
}
