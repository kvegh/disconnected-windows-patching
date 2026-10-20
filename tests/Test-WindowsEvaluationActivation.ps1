# Read-only regression tests: every Windows licensing/network command is mocked.
param([string]$ActivationSource = '')
$ErrorActionPreference = 'Stop'
if (-not $ActivationSource) {
    $ActivationSource = Get-Content (Join-Path $PSScriptRoot '..\assets\windows-evaluation-activation.ps1') -Raw
}
$activation = [scriptblock]::Create($ActivationSource)
$script:Assertions = 0
function Assert-True([bool]$Condition, [string]$Message) {
    if (-not $Condition) { throw $Message }
    $script:Assertions++
}
function Reset-TestState {
    $script:Ansible = @{ Changed = $true; CheckMode = $false }
    $script:activationCalls = 0
    $script:license = [pscustomobject]@{
        Name = 'Windows Server DatacenterEval'; Description = 'TIMEBASED_EVAL channel';
        LicenseStatus = 1; LicenseStatusReason = 0; GracePeriodRemaining = 250000; LicenseIsAddon = $false
    }
    $script:licenses = @($script:license)
    $script:adapters = @([pscustomobject]@{ MacAddress = '52-54-00-11-22-33'; InterfaceIndex = 4; Status = 'Up' })
    $script:addresses = @([pscustomobject]@{ IPAddress = '192.0.2.10'; PrefixLength = 24 })
    $script:dns = @()
    $script:routes = @()
    $script:ipv6Routes = @()
    $script:configuration = @{ interfaces = @(@{ mac = '52:54:00:11:22:33'; ipv4_address = '192.0.2.10'; prefix_length = 24; dns_servers = @(); gateway = '' }) }
    $script:version = '2025'
    $script:activationResult = 0
}
function Get-CimInstance([string]$ClassName, [string]$Filter) {
    if ($ClassName -eq 'Win32_OperatingSystem') { return [pscustomobject]@{ Caption = "Microsoft Windows Server $script:version Datacenter Evaluation"; ProductType = 3 } }
    if ($ClassName -eq 'SoftwareLicensingProduct') { return $script:licenses }
    throw 'Unexpected CIM call.'
}
function Invoke-CimMethod($InputObject, [string]$MethodName) {
    Assert-True ($MethodName -eq 'Activate' -and $InputObject -eq $script:license) 'Only the already-installed Windows SKU may be activated.'
    $script:activationCalls++
    $script:license.LicenseStatus = 1
    $script:license.GracePeriodRemaining = 259200
    return [pscustomobject]@{ ReturnValue = $script:activationResult }
}
function Get-NetAdapter { return $script:adapters }
function Get-NetIPAddress($InterfaceIndex, $AddressFamily, $ErrorAction) { return $script:addresses }
function Get-DnsClientServerAddress($InterfaceIndex, $AddressFamily) { return [pscustomobject]@{ ServerAddresses = $script:dns } }
function Get-NetRoute($AddressFamily, $DestinationPrefix, $ErrorAction) {
    if ($AddressFamily -eq 'IPv6') { return $script:ipv6Routes }
    return $script:routes
}
function Invoke-Inspection([string]$Mode = 'Inspect', [string]$TemporaryMac = '') {
    & $activation -Mode $Mode -ExpectedVersion '2025' -ConfigurationJson ($script:configuration | ConvertTo-Json -Depth 5) -TemporaryMac $TemporaryMac
}
function Assert-Rejected([string]$Mode = 'Inspect') {
    $rejected = $false
    try { Invoke-Inspection $Mode } catch { $rejected = $true }
    Assert-True $rejected "Unsafe $Mode configuration must fail."
}

Reset-TestState
Invoke-Inspection 'Activate'
Assert-True ($Ansible.Result.licensed -and -not $Ansible.Changed -and $activationCalls -eq 0) 'Already-licensed clones must skip activation.'
Reset-TestState
$license.LicenseStatus = 5
$license.GracePeriodRemaining = 0
Invoke-Inspection 'Activate'
Assert-True ($activationCalls -eq 1 -and $Ansible.Result.licensed -and $Ansible.Changed) 'Activate the installed evaluation and inspect its resulting state.'
Reset-TestState
$license.LicenseStatus = 5
$Ansible.CheckMode = $true
Invoke-Inspection 'Activate'
Assert-True ($activationCalls -eq 0 -and -not $Ansible.Changed) 'Check mode must never activate.'
Reset-TestState
$license.Name = 'Windows Server Datacenter'
$license.Description = 'RETAIL channel'
$license.LicenseStatus = 0
Assert-Rejected 'Activate'
Assert-True ($activationCalls -eq 0) 'Never activate an unlicensed non-evaluation edition.'
Reset-TestState
$script:licenses += $license
Assert-Rejected
Reset-TestState
$script:version = '2022'
Assert-Rejected
Reset-TestState
$addresses[0].IPAddress = '192.0.2.99'
Assert-Rejected
Reset-TestState
$script:dns = @('192.0.2.1')
Assert-Rejected
Reset-TestState
$script:routes = @([pscustomobject]@{ InterfaceIndex = 4; NextHop = '192.0.2.1' })
Assert-Rejected
Reset-TestState
$script:ipv6Routes = @([pscustomobject]@{ NextHop = '2001:db8::1' })
Assert-Rejected
Reset-TestState
$script:adapters += [pscustomobject]@{ MacAddress = '52-54-00-44-55-66'; InterfaceIndex = 5; Status = 'Up' }
Assert-Rejected 'Verify'
Reset-TestState
$script:adapters += [pscustomobject]@{ MacAddress = '52-54-00-44-55-66'; InterfaceIndex = 5; Status = 'Up' }
$script:routes = @([pscustomobject]@{ InterfaceIndex = 5; NextHop = '192.0.2.1' })
Invoke-Inspection 'Connected' '52:54:00:44:55:66'
Assert-True (-not $Ansible.Changed) 'A temporary route can be inspected without altering the permanent NIC.'
Reset-TestState
$configuration.interfaces[0].gateway = '192.0.2.1'
$configuration.interfaces[0].dns_servers = @('192.0.2.1')
$script:routes = @([pscustomobject]@{ InterfaceIndex = 4; NextHop = '192.0.2.1' })
$script:dns = @('192.0.2.1')
Invoke-Inspection 'Verify'
Assert-True $Ansible.Result.original_topology_verified 'Existing repository-server connectivity is preserved.'
Reset-TestState
$license.LicenseStatus = 5
Assert-Rejected 'Verify'
Reset-TestState
$license.GracePeriodRemaining = 0
Assert-Rejected 'Verify'
Reset-TestState
$license.LicenseStatus = 5
$script:activationResult = 5
Assert-Rejected 'Activate'
Write-Output "Passed $Assertions Windows evaluation activation assertions."
