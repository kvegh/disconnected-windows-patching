# Mock Windows APIs in their native language; see [rationale](README.md#powershell-tests).
# Reproduce a restricted WinRM context using mocks; no update or registry changes.
[CmdletBinding()]
param([string]$SearchSource)
$ErrorActionPreference = 'Stop'
if (-not $SearchSource) {
    $SearchSource = Get-Content -LiteralPath (Join-Path $PSScriptRoot '..\assets\search-managed-windows-updates.ps1') -Raw
}
$searchScript = [scriptblock]::Create($SearchSource)
$script:Assertions = 0
function Assert-True {
    param([bool]$Condition, [string]$Message)
    if (-not $Condition) { throw $Message }
    $script:Assertions++
}
function Reset-TestState {
    $script:Ansible = @{ Changed = $true; CheckMode = $true }
    $script:cbsReboot = $false
    $script:wuReboot = $false
    $script:response = [pscustomobject]@{
        ResultCode = 2
        Updates = @([pscustomobject]@{
            Identity = [pscustomobject]@{ UpdateID = 'example-update'; RevisionNumber = 1 }
            Title = '2026-04 Example Cumulative Update'
            KBArticleIDs = @('1234567')
            IsHidden = $false
            EulaAccepted = $false
            IsDownloaded = $false
        })
    }
    $script:searcher = [pscustomobject]@{ ServerSelection = 0; Online = $false }
    $searcher | Add-Member ScriptMethod Search {
        param([string]$Criteria)
        $script:criteria = $Criteria
        return $script:response
    }
    $script:session = [pscustomobject]@{ ClientApplicationID = '' }
    $session | Add-Member ScriptMethod CreateUpdateSearcher { return $script:searcher }
}
function New-Object {
    param([string]$ComObject)
    if ($ComObject -eq 'Microsoft.Update.Session') { return $script:session }
    throw [UnauthorizedAccessException]::new('This COM interface is unavailable to the remote caller.')
}
function Test-Path {
    param([string]$Path)
    if ($Path -like '*\Component Based Servicing\RebootPending') { return $script:cbsReboot }
    if ($Path -like '*\WindowsUpdate\Auto Update\RebootRequired') { return $script:wuReboot }
    throw 'Unexpected registry probe.'
}

Reset-TestState
& $searchScript
Assert-True ($Ansible.Result.found_update_count -eq 1) 'A remote-safe search must retain update offers.'
Assert-True ($Ansible.Result.pending_eula_count -eq 1) 'Unaccepted licenses must remain unaccepted and visible.'
Assert-True (-not $Ansible.Result.reboot_required) 'No update/CBS reboot marker means no pending update reboot.'
Assert-True (-not $Ansible.Changed) 'Assessment must remain read-only.'
Assert-True ($searcher.ServerSelection -eq 1 -and $searcher.Online) 'Search must use the managed server.'
$observed = $Ansible.Result.updates['example-update']
Assert-True ($observed.title -match $observed.accept_pattern) 'The exact observed title must match.'
Assert-True (($observed.title + $observed.kb) -match $observed.accept_pattern) 'The native title-plus-KB representation must match.'
Assert-True (($observed.title + ' newer') -notmatch $observed.accept_pattern) 'A title with additional text must remain excluded.'
Assert-True (($observed.title + 'KB7654321') -notmatch $observed.accept_pattern) 'An unobserved appended KB must remain excluded.'

Reset-TestState
$script:cbsReboot = $true
& $searchScript
Assert-True ($Ansible.Result.reboot_required) 'A servicing reboot marker must be reported.'

Reset-TestState
$script:wuReboot = $true
& $searchScript
Assert-True ($Ansible.Result.reboot_required) 'A Windows Update reboot marker must be reported.'

Reset-TestState
$response.ResultCode = 3
$rejected = $false
try { & $searchScript } catch { $rejected = $true }
Assert-True $rejected 'An incomplete applicability search must still fail.'
Write-Output "Passed $Assertions managed update search assertions."
