# Read-only regression tests using mocks; no WSUS or registry changes occur.
# Run with Windows PowerShell 5.1 or PowerShell 7.
$ErrorActionPreference = 'Stop'
$scriptPath = Join-Path $PSScriptRoot '..\assets\inspect-windows-update-client.ps1'
$script:Assertions = 0
function Assert-True {
    param([bool]$Condition, [string]$Message)
    if (-not $Condition) { throw $Message }
    $script:Assertions++
}
function Assert-Rejected {
    param([string]$Expected = 'https://updates.internal.example:8531')
    $rejected = $false
    try { & $scriptPath -ExpectedWsusUrl $Expected } catch { $rejected = $true }
    Assert-True $rejected 'Unsafe or unsupported update-source configuration must be rejected.'
}
function Reset-TestState {
    $script:policy = [pscustomobject]@{
        WUServer = 'https://updates.internal.example:8531'
        WUStatusServer = 'https://updates.internal.example:8531'
        DoNotConnectToWindowsUpdateInternetLocations = 1
    }
    $script:automatic = [pscustomobject]@{ UseWUServer = 1; NoAutoUpdate = 1 }
    $script:version = [pscustomobject]@{ CurrentBuildNumber = '26100'; UBR = 1742 }
    $script:Ansible = @{ Changed = $true; CheckMode = $true }
}
function Get-ItemProperty {
    param([string]$LiteralPath, [string]$Path)
    $selected = if ($LiteralPath) { $LiteralPath } else { $Path }
    if ($selected -like '*\CurrentVersion') { return $script:version }
    if ($selected -like '*\WindowsUpdate\AU') { return $script:automatic }
    if ($selected -like '*\WindowsUpdate') { return $script:policy }
    throw 'Unexpected mocked registry read.'
}
function Get-CimInstance {
    param([string]$ClassName)
    if ($ClassName -ne 'Win32_OperatingSystem') { throw 'Unexpected mocked CIM read.' }
    return [pscustomobject]@{
        Caption = 'Windows Server 2025'; ProductType = 3; LastBootUpTime = [datetime]'2026-01-01T00:00:00Z'
    }
}
function Get-HotFix { return [pscustomobject]@{ HotFixID = 'KB1234567' } }
function Test-Path { return $false }

Reset-TestState
& $scriptPath -ExpectedWsusUrl 'https://UPDATES.internal.example:8531/'
Assert-True ($Ansible.Result.source_verified) 'The normalized protected source must be accepted.'
Assert-True ($Ansible.Result.installed_build -eq '26100.1742') 'Report actual installed build, without assuming an April target.'
Assert-True (-not $Ansible.Changed) 'Client inspection must remain read-only in check mode.'

Reset-TestState
$policy.WUStatusServer = 'https://another.internal.example:8531'
Assert-Rejected
Reset-TestState
$automatic.UseWUServer = 0
Assert-Rejected
Reset-TestState
$policy.DoNotConnectToWindowsUpdateInternetLocations = 0
Assert-Rejected
Reset-TestState
$automatic.NoAutoUpdate = 0
Assert-Rejected
Reset-TestState
$policy.WUServer = ''
Assert-Rejected
Reset-TestState
$policy | Add-Member NoteProperty SetPolicyDrivenUpdateSourceForQualityUpdates 0
Assert-Rejected
Reset-TestState
$policy | Add-Member NoteProperty SetPolicyDrivenUpdateSourceForQualityUpdates 1
& $scriptPath -ExpectedWsusUrl 'https://updates.internal.example:8531'
Assert-True ($Ansible.Result.source_verified) 'An explicit corporate source policy is permitted.'
Reset-TestState
$policy | Add-Member NoteProperty UpdateServiceUrlAlternate 'https://another.internal.example:8531'
Assert-Rejected
Reset-TestState
Assert-Rejected 'https://updates.internal.example:8531/unexpected-path'
Reset-TestState
$version.CurrentBuildNumber = '99999'
Assert-Rejected
Write-Output "Passed $Assertions Windows update client source-policy assertions."
