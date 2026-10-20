[CmdletBinding(SupportsShouldProcess)]
param([Parameter(Mandatory)][string]$ExpectedWsusUrl)
$ErrorActionPreference = 'Stop'
$Ansible.Changed = $false

function Get-NormalizedWsusUrl {
    param([string]$Value)
    $uri = $null
    if (-not [uri]::TryCreate($Value, [UriKind]::Absolute, [ref]$uri) -or
        $uri.Scheme -notin @('http', 'https') -or $uri.UserInfo -or
        $uri.Query -or $uri.Fragment -or $uri.AbsolutePath -ne '/') {
        throw 'A WSUS source URL is invalid; correct source configuration before patching.'
    }
    return $uri.AbsoluteUri.TrimEnd('/')
}

$expected = Get-NormalizedWsusUrl $ExpectedWsusUrl
$policyPath = 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate'
$policy = Get-ItemProperty -LiteralPath $policyPath
$automatic = Get-ItemProperty -LiteralPath "$policyPath\AU"
if ((Get-NormalizedWsusUrl ([string]$policy.WUServer)) -ne $expected -or
    (Get-NormalizedWsusUrl ([string]$policy.WUStatusServer)) -ne $expected -or
    $automatic.UseWUServer -ne 1 -or
    $policy.DoNotConnectToWindowsUpdateInternetLocations -ne 1 -or
    $automatic.NoAutoUpdate -ne 1) {
    throw 'The existing source must use only the protected internal WSUS with unattended updates disabled. Run the source-configuration playbook first.'
}
# Explicit Microsoft Update source policies must never override the managed
# source. Missing values retain the existing WSUS policy; no registry is changed.
foreach ($name in @('SetPolicyDrivenUpdateSourceForFeatureUpdates',
    'SetPolicyDrivenUpdateSourceForQualityUpdates',
    'SetPolicyDrivenUpdateSourceForDriverUpdates',
    'SetPolicyDrivenUpdateSourceForOtherUpdates')) {
    $setting = $policy.PSObject.Properties[$name]
    if ($null -ne $setting -and [int]$setting.Value -ne 1) {
        throw 'An explicit update-class source policy conflicts with internal WSUS.'
    }
}
if ($policy.UpdateServiceUrlAlternate -and
    (Get-NormalizedWsusUrl ([string]$policy.UpdateServiceUrlAlternate)) -ne $expected) {
    throw 'An alternate update download source needs review before managed patching.'
}

$version = Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion'
$os = Get-CimInstance Win32_OperatingSystem
if ([string]$version.CurrentBuildNumber -notin @('20348', '26100') -or [int]$os.ProductType -eq 1) {
    throw 'Only the configured Windows Server 2022 and 2025 build families may use this patch job.'
}
$cbsReboot = Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending'
$wuReboot = Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired'
$Ansible.Result = @{
    schema_version = 1
    assessed_utc = (Get-Date).ToUniversalTime().ToString('o')
    source_verified = $true
    os_name = [string]$os.Caption
    build_family = [string]$version.CurrentBuildNumber
    revision = [int]$version.UBR
    installed_build = "$($version.CurrentBuildNumber).$($version.UBR)"
    installed_hotfix_ids = @(Get-HotFix | Select-Object -ExpandProperty HotFixID | Sort-Object -Unique)
    reboot_pending = [bool]($cbsReboot -or $wuReboot)
    last_boot_utc = $os.LastBootUpTime.ToUniversalTime().ToString('o')
}
