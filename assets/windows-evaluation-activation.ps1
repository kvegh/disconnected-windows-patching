[CmdletBinding(SupportsShouldProcess)]
param(
    [ValidateSet('Inspect', 'Activate', 'Connected', 'Verify')][string]$Mode = 'Inspect',
    [Parameter(Mandatory)][string]$ExpectedVersion,
    [Parameter(Mandatory)][string]$ConfigurationJson,
    [string]$TemporaryMac = ''
)
$ErrorActionPreference = 'Stop'
$Ansible.Changed = $false
$configuration = $ConfigurationJson | ConvertFrom-Json

function Normalize-Mac([string]$Value) { return ($Value -replace '[:-]', '').ToLowerInvariant() }
function Same-Values($First, $Second) {
    return ((@($First | Sort-Object) -join [char]0) -ceq (@($Second | Sort-Object) -join [char]0))
}

function Get-InstalledWindowsLicense {
    $licenses = @(Get-CimInstance -ClassName SoftwareLicensingProduct -Filter "ApplicationID='55c92734-d682-4d71-983e-d6ec3f16059f' AND PartialProductKey IS NOT NULL" |
        Where-Object { -not $_.LicenseIsAddon })
    if ($licenses.Count -ne 1) { throw 'Expected exactly one installed Windows operating system license.' }
    return $licenses[0]
}

$os = Get-CimInstance -ClassName Win32_OperatingSystem
if ($ExpectedVersion -notin @('2022', '2025') -or $os.Caption -notmatch "Windows Server $ExpectedVersion" -or $os.ProductType -eq 1) {
    throw 'The installed Windows Server version does not match the protected deployment mapping.'
}
$license = Get-InstalledWindowsLicense
$evaluation = $license.Description -match 'TIMEBASED_EVAL' -or $license.Name -match 'Eval'
if (-not $evaluation -and [int]$license.LicenseStatus -ne 1) {
    throw 'An unlicensed non-evaluation edition requires a separate licensing procedure.'
}

$adapters = @(Get-NetAdapter)
$configuredMacs = @($configuration.interfaces | ForEach-Object { Normalize-Mac $_.mac })
$activeMacs = @($adapters | ForEach-Object { Normalize-Mac $_.MacAddress })
foreach ($interface in $configuration.interfaces) {
    $matching = @($adapters | Where-Object { (Normalize-Mac $_.MacAddress) -eq (Normalize-Mac $interface.mac) })
    if ($matching.Count -ne 1) { throw 'An original adapter is missing or ambiguous.' }
    $addresses = @(Get-NetIPAddress -InterfaceIndex $matching[0].InterfaceIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue)
    if (@($addresses | Where-Object { $_.IPAddress -eq $interface.ipv4_address -and $_.PrefixLength -eq [int]$interface.prefix_length }).Count -ne 1) {
        throw 'An original permanent Windows address changed.'
    }
    $dns = @(Get-DnsClientServerAddress -InterfaceIndex $matching[0].InterfaceIndex -AddressFamily IPv4)
    if (-not (Same-Values @($interface.dns_servers) @($dns.ServerAddresses))) {
        throw 'An original adapter DNS configuration changed.'
    }
}

$routes = @(Get-NetRoute -AddressFamily IPv4 -DestinationPrefix '0.0.0.0/0' -ErrorAction SilentlyContinue)
if ($Mode -in @('Inspect', 'Verify')) {
    if (-not (Same-Values $configuredMacs $activeMacs)) {
        throw 'Visible adapters do not match the original protected topology.'
    }
    $expectedRoutes = @($configuration.interfaces | Where-Object gateway | ForEach-Object {
        $config = $_
        $adapter = @($adapters | Where-Object { (Normalize-Mac $_.MacAddress) -eq (Normalize-Mac $config.mac) })[0]
        "$($adapter.InterfaceIndex):$($config.gateway)"
    })
    $actualRoutes = @($routes | ForEach-Object { "$($_.InterfaceIndex):$($_.NextHop)" })
    if (-not (Same-Values $expectedRoutes $actualRoutes)) {
        throw 'Default routes do not match the original protected topology.'
    }
    if (@(Get-NetRoute -AddressFamily IPv6 -DestinationPrefix '::/0' -ErrorAction SilentlyContinue).Count) {
        throw 'Unexpected IPv6 default route; review isolation before activation.'
    }
}
if ($Mode -eq 'Connected' -and $TemporaryMac) {
    $temporary = @($adapters | Where-Object { (Normalize-Mac $_.MacAddress) -eq (Normalize-Mac $TemporaryMac) })
    if ($temporary.Count -ne 1 -or $temporary[0].Status -ne 'Up') { throw 'The temporary activation adapter is not ready.' }
    if (@($routes | Where-Object InterfaceIndex -eq $temporary[0].InterfaceIndex).Count -ne 1) {
        throw 'The temporary activation adapter has no unique IPv4 default route.'
    }
}

if ($Mode -eq 'Activate' -and [int]$license.LicenseStatus -ne 1 -and -not $Ansible.CheckMode) {
    if (-not $evaluation) { throw 'Only the already-installed evaluation license may be activated.' }
    # The local SPP licensing method activates the installed SKU. No key,
    # edition conversion, timer reset, remote COM object or Windows Update call.
    $result = Invoke-CimMethod -InputObject $license -MethodName Activate
    if ([uint32]$result.ReturnValue -ne 0) { throw ('Evaluation activation failed with code 0x{0:X8}.' -f [uint32]$result.ReturnValue) }
    $Ansible.Changed = $true
    $license = Get-InstalledWindowsLicense
}
$Ansible.Result = @{
    licensed = [int]$license.LicenseStatus -eq 1
    evaluation = [bool]$evaluation
    license_status = [int]$license.LicenseStatus
    license_reason = [uint32]$license.LicenseStatusReason
    grace_minutes = [int]$license.GracePeriodRemaining
    existing_connected_access = $routes.Count -gt 0
    original_topology_verified = $Mode -in @('Inspect', 'Verify')
}
if ($Mode -eq 'Verify' -and (-not $Ansible.Result.licensed -or ($evaluation -and $Ansible.Result.grace_minutes -le 0))) {
    throw 'Evaluation activation is not valid after original network isolation was restored.'
}
