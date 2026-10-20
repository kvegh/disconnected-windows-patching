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
    $updates[$id] = @{
        id = $id
        title = [string]$update.Title
        kb = @($update.KBArticleIDs | ForEach-Object { "KB$_" })
        revision = [int]$update.Identity.RevisionNumber
        hidden = [bool]$update.IsHidden
        eula_accepted = [bool]$update.EulaAccepted
        downloaded = [bool]$update.IsDownloaded
    }
}
$system = New-Object -ComObject Microsoft.Update.SystemInfo
$Ansible.Result = @{
    schema_version = 1
    assessed_utc = (Get-Date).ToUniversalTime().ToString('o')
    source = 'managed_server'
    found_update_count = $updates.Count
    hidden_update_count = @($updates.Values | Where-Object hidden).Count
    pending_eula_count = @($updates.Values | Where-Object { -not $_.eula_accepted }).Count
    reboot_required = [bool]$system.RebootRequired
    updates = $updates
}
