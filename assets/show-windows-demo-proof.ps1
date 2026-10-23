[CmdletBinding()]
param(
    [string]$ExpectedJson = '',
    [string]$ConfigPath = '',
    [switch]$AsJson,
    [switch]$FunctionsOnly
)
$ErrorActionPreference = 'Stop'

function Get-DemoBuildComparison {
    param([string]$Installed,[string]$Expected)
    $actualVersion = [version]$Installed
    $expectedVersion = [version]$Expected
    if ($actualVersion -eq $expectedVersion) { return 'exact' }
    if ($actualVersion -gt $expectedVersion) { return 'above' }
    return 'below'
}

function ConvertFrom-DemoChocolateyHistory {
    param([string[]]$Lines)
    $pending = @{}
    $events = @()
    foreach ($line in $Lines) {
        $record = [regex]::Match($line, '^(?<date>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:[,.]\d{3})?)\s+\d+\s+\[[A-Z ]+\]\s+-\s*(?<message>.*)$')
        if (-not $record.Success) { continue }
        $message = $record.Groups['message'].Value
        $version = [regex]::Match($message, '^(?<id>7zip\.install|git\.install) v(?<version>[0-9.]+)(?:\s|$)', 'IgnoreCase')
        if ($version.Success) {
            $pending[$version.Groups['id'].Value.ToLowerInvariant()] = $version.Groups['version'].Value
        }
        $success = [regex]::Match($message, '^The (?<operation>install|upgrade) of (?<id>7zip\.install|git\.install) was successful\.', 'IgnoreCase')
        if (-not $success.Success) { continue }
        $id = $success.Groups['id'].Value.ToLowerInvariant()
        if (-not $pending.ContainsKey($id)) { continue }
        $stamp = [datetime]::MinValue
        if (-not [datetime]::TryParseExact($record.Groups['date'].Value,
            [string[]]@('yyyy-MM-dd HH:mm:ss,fff','yyyy-MM-dd HH:mm:ss.fff','yyyy-MM-dd HH:mm:ss'),
            [Globalization.CultureInfo]::InvariantCulture, [Globalization.DateTimeStyles]::None, [ref]$stamp)) { continue }
        $events += [pscustomobject]@{
            id=$id; version=[string]$pending[$id]; operation=$success.Groups['operation'].Value.ToLowerInvariant();
            observed_utc=$stamp.ToUniversalTime().ToString('o'); source='Chocolatey successful-operation log'
        }
        $pending.Remove($id)
    }
    return $events
}

function Get-DemoPackageSequence {
    param([object[]]$Events,[string]$Id,[string]$Baseline,[string]$Current)
    $baselineEvents = @($Events | Where-Object { $_.id -eq $Id -and $_.version -eq $Baseline } | Sort-Object observed_utc)
    foreach ($first in $baselineEvents) {
        $upgrade = @($Events | Where-Object {
            $_.id -eq $Id -and $_.version -eq $Current -and $_.operation -in @('upgrade','verified-current') -and
            [datetimeoffset]$_.observed_utc -gt [datetimeoffset]$first.observed_utc
        } | Sort-Object observed_utc | Select-Object -First 1)
        if ($upgrade.Count) {
            return @{ status='PASS'; baseline=$first; upgrade=$upgrade[0]; detail='Baseline was recorded before the successful upgrade.' }
        }
    }
    if ($baselineEvents.Count) {
        return @{ status='WARN'; baseline=$baselineEvents[-1]; upgrade=$null; detail='Baseline history exists; a later successful upgrade is not retained.' }
    }
    return @{ status='WARN'; baseline=$null; upgrade=$null; detail='Historical baseline installation is not proven by retained local evidence.' }
}

function Get-DemoRegistryValue {
    param($Object,[string]$Name)
    if ($null -eq $Object) { return $null }
    $property = $Object.PSObject.Properties[$Name]
    if ($null -ne $property) { return $property.Value }
    return $null
}

function Write-DemoProofConsole {
    param($Report)
    Write-Host ''
    Write-Host ('=' * 78) -ForegroundColor Cyan
    Write-Host (' WINDOWS DEMO PROOF - ' + $Report.server) -ForegroundColor Cyan
    Write-Host ($Report.os_name + ' | assessed ' + $Report.assessed_utc)
    Write-Host ('=' * 78) -ForegroundColor Cyan
    foreach ($section in @(
        @{name='INTERNAL WSUS'; value=$Report.wsus},
        @{name='APRIL OS PATCH LEVEL'; value=$Report.patching}
    )) {
        $color = if ($section.value.status -eq 'PASS') { 'Green' } elseif ($section.value.status -eq 'FAIL') { 'Red' } else { 'Yellow' }
        Write-Host ('[{0}] {1}' -f $section.value.status,$section.name) -ForegroundColor $color
        foreach ($line in $section.value.evidence) { Write-Host ('  ' + $line) }
        Write-Host ''
    }
    Write-Host 'APPLICATION BASELINE AND UPGRADE' -ForegroundColor Cyan
    foreach ($package in $Report.applications) {
        $color = if ($package.status -eq 'PASS') { 'Green' } elseif ($package.status -eq 'FAIL') { 'Red' } else { 'Yellow' }
        Write-Host ('[{0}] {1}' -f $package.status,$package.title) -ForegroundColor $color
        foreach ($line in $package.evidence) { Write-Host ('  ' + $line) }
    }
    Write-Host ''
    Write-Host ('[INFO] Enabled package feeds: ' + ($Report.enabled_package_sources -join ', ')) -ForegroundColor Cyan
    foreach ($errorText in $Report.errors) { Write-Host ('[WARN] ' + $errorText) -ForegroundColor Yellow }
    Write-Host ''
    Write-Host 'Live read-only query complete. Close this window when finished.' -ForegroundColor Cyan
}

function Get-WindowsDemoProof {
    param($Configuration)
    if ($Configuration.schema_version -ne 1) { throw 'Unsupported proof configuration.' }
    $expectedUri = [uri]$Configuration.wsus_url
    if ($expectedUri.Scheme -notin @('http','https') -or $expectedUri.UserInfo -or $expectedUri.Query -or $expectedUri.Fragment) {
        throw 'The expected WSUS URL must not contain credentials or query data.'
    }
    $errors = @()
    $osInfo = Get-CimInstance Win32_OperatingSystem
    $machineUuid = [string](Get-CimInstance Win32_ComputerSystemProduct).UUID
    $systemVersion = Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion'
    $family = [string]$systemVersion.CurrentBuildNumber
    $installedBuild = "$family.$($systemVersion.UBR)"
    $baselineProperty = $Configuration.baselines.PSObject.Properties[$family]
    if ($null -eq $baselineProperty -or [int]$osInfo.ProductType -eq 1) { throw 'This server has no configured Windows Server proof baseline.' }
    $baseline = $baselineProperty.Value
    $hotfixes = @(Get-HotFix)
    $hotfixIds = @($hotfixes | ForEach-Object HotFixID)
    $pendingReboot = (Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending') -or
        (Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired')
    $comparison = Get-DemoBuildComparison $installedBuild ([string]$baseline.build)
    $osStatus = if ($comparison -eq 'below') { 'FAIL' } elseif ($comparison -eq 'above' -or $pendingReboot -or $baseline.kb -notin $hotfixIds) { 'WARN' } else { 'PASS' }
    $dotnet = @()
    $dotnetProperty = $Configuration.dotnet_candidates.PSObject.Properties[$family]
    if ($dotnetProperty) { $dotnet = @($dotnetProperty.Value | Where-Object { $_ -in $hotfixIds }) }
    $patchEvidence = @(
        "Target: $($Configuration.baseline_name), $($baseline.build), $($baseline.kb)",
        "Actual installed build: $installedBuild ($comparison target)",
        "Expected cumulative KB present: $($baseline.kb -in $hotfixIds)",
        "April .NET markers present: $($dotnet -join ', ')",
        "Pending servicing reboot: $pendingReboot"
    )
    if ($comparison -eq 'above') { $patchEvidence += 'This is newer than the exact April cutoff.' }
    $policy = Get-ItemProperty 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate' -ErrorAction SilentlyContinue
    $automatic = Get-ItemProperty 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU' -ErrorAction SilentlyContinue
    $configuredUrl = [string](Get-DemoRegistryValue $policy 'WUServer')
    $statusUrl = [string](Get-DemoRegistryValue $policy 'WUStatusServer')
    $useManaged = (Get-DemoRegistryValue $automatic 'UseWUServer') -eq 1
    $noPublic = (Get-DemoRegistryValue $policy 'DoNotConnectToWindowsUpdateInternetLocations') -eq 1
    $noUnattended = (Get-DemoRegistryValue $automatic 'NoAutoUpdate') -eq 1
    $policyVerified = $configuredUrl.TrimEnd('/') -eq $Configuration.wsus_url.TrimEnd('/') -and
        $statusUrl.TrimEnd('/') -eq $Configuration.wsus_url.TrimEnd('/') -and $useManaged -and $noPublic -and $noUnattended
    foreach ($name in @('SetPolicyDrivenUpdateSourceForFeatureUpdates','SetPolicyDrivenUpdateSourceForQualityUpdates',
        'SetPolicyDrivenUpdateSourceForDriverUpdates','SetPolicyDrivenUpdateSourceForOtherUpdates')) {
        $value = Get-DemoRegistryValue $policy $name
        if ($null -ne $value -and [int]$value -ne 1) { $policyVerified = $false }
    }
    $reachable = $false
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri ($Configuration.wsus_url.TrimEnd('/') + '/ClientWebService/client.asmx') -TimeoutSec 8
        $reachable = $response.StatusCode -eq 200
    } catch { $errors += 'The configured internal WSUS web service did not return HTTP 200.' }
    $managedHistory = @()
    try {
        $updateSession = New-Object -ComObject Microsoft.Update.Session
        $searcher = $updateSession.CreateUpdateSearcher()
        $count = [Math]::Min(300,$searcher.GetTotalHistoryCount())
        if ($count -gt 0) {
            $managedHistory = @($searcher.QueryHistory(0,$count) | Where-Object {
                [int]$_.ResultCode -eq 2 -and [int]$_.Operation -eq 1 -and [int]$_.ServerSelection -eq 1
            } | Select-Object -First 8 | ForEach-Object {
                @{title=[string]$_.Title; reported_date=$_.Date.ToString('s'); source='Managed WSUS'; result='Succeeded'}
            })
        }
    } catch { $errors += 'Windows Update Agent local history could not be read.' }
    $wsusEvidence = @(
        "Expected internal WSUS: $($Configuration.wsus_url)", "Actual WUServer: $configuredUrl", "Actual WUStatusServer: $statusUrl",
        "UseWUServer=$useManaged; public update connections blocked=$noPublic; unattended updates disabled=$noUnattended",
        "Internal ClientWebService reachable: $reachable"
    )
    foreach ($entry in $managedHistory | Select-Object -First 3) { $wsusEvidence += "Managed-WSUS installation: $($entry.reported_date) - $($entry.title)" }
    if (-not $managedHistory.Count) { $wsusEvidence += 'No retained managed-WSUS installation history was found; the policy checks describe the current configuration.' }
    $chocoRoot = [string](Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Environment' -Name ChocolateyInstall -ErrorAction SilentlyContinue).ChocolateyInstall
    if (-not $chocoRoot) { $chocoRoot = Join-Path $env:ProgramData 'chocolatey' }
    $logLines = @()
    $logFiles = @(Get-ChildItem (Join-Path $chocoRoot 'logs') -Filter 'chocolatey*.log*' -File -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime | Select-Object -Last 8)
    foreach ($file in $logFiles) {
        if ($file.Length -le 16777216) { $logLines += @(Get-Content -LiteralPath $file.FullName -ErrorAction SilentlyContinue) }
    }
    $packageHistory = @(ConvertFrom-DemoChocolateyHistory $logLines)
    foreach ($receiptFile in @(Get-ChildItem $Configuration.evidence_directory -Filter '*.json' -File -ErrorAction SilentlyContinue)) {
        try {
            $receipt = Get-Content -LiteralPath $receiptFile.FullName -Raw -Encoding UTF8 | ConvertFrom-Json
            if ($receipt.schema_version -eq 1 -and $receipt.computer_name -eq $env:COMPUTERNAME -and
                $receipt.machine_uuid -eq $machineUuid) {
                foreach ($item in $receipt.packages) {
                    $packageHistory += [pscustomobject]@{id=[string]$item.id;version=[string]$item.version;
                        operation=if($receipt.track -eq 'current'){'verified-current'}else{'verified-baseline'};
                        observed_utc=[string]$receipt.observed_utc;source='Verified Ansible package-state receipt'}
                }
            }
        } catch { $errors += 'An application evidence receipt is unreadable.' }
    }
    $applications = @()
    foreach ($id in @($Configuration.packages | ForEach-Object id | Sort-Object -Unique)) {
        $older = @($Configuration.packages | Where-Object { $_.id -eq $id -and $_.track -eq 'baseline' })
        $newer = @($Configuration.packages | Where-Object { $_.id -eq $id -and $_.track -eq 'current' })
        if ($older.Count -ne 1 -or $newer.Count -ne 1) { throw 'A package comparison target is ambiguous.' }
        $installedVersion = ''
        $nuspec = Join-Path (Join-Path (Join-Path $chocoRoot 'lib') $id) ($id + '.nuspec')
        if (Test-Path -LiteralPath $nuspec) { $installedVersion = [string]([xml](Get-Content -LiteralPath $nuspec -Raw)).package.metadata.version }
        $binaryVersion = ''
        if ($id -eq '7zip.install') {
            $binary = Join-Path $env:ProgramFiles '7-Zip\7z.exe'
            if (Test-Path -LiteralPath $binary) { $binaryVersion = [string](Get-Item $binary).VersionInfo.ProductVersion }
        } elseif ($id -eq 'git.install') {
            $binary = Join-Path $env:ProgramFiles 'Git\cmd\git.exe'
            if (Test-Path -LiteralPath $binary) { $binaryVersion = ((& $binary --version) -join '').Trim() -replace '^git version\s+','' }
        }
        $sequence = Get-DemoPackageSequence $packageHistory $id ([string]$older[0].version) ([string]$newer[0].version)
        $currentVerified = $installedVersion -eq [string]$newer[0].version -and $binaryVersion -eq [string]$newer[0].vendor_version
        $pkgStatus = if (-not $installedVersion -or $installedVersion -notin @([string]$older[0].version,[string]$newer[0].version) -or
            ($installedVersion -eq [string]$newer[0].version -and -not $currentVerified)) {'FAIL'}
            elseif ($currentVerified -and $sequence.status -eq 'PASS') {'PASS'} else {'WARN'}
        $evidence = @("Expected baseline: $($older[0].version); expected upgraded version: $($newer[0].version)",
            "Actual installed package: $installedVersion; actual executable version: $binaryVersion",$sequence.detail)
        if ($sequence.baseline) { $evidence += "Baseline observed: $($sequence.baseline.observed_utc) [$($sequence.baseline.source)]" }
        if ($sequence.upgrade) { $evidence += "Upgrade observed: $($sequence.upgrade.observed_utc) [$($sequence.upgrade.source)]" }
        $applications += @{id=$id;title=[string]$newer[0].title;status=$pkgStatus;installed_version=$installedVersion;
            binary_version=$binaryVersion;current_version_verified=$currentVerified;history=$sequence;evidence=$evidence}
    }
    $enabledSources = @()
    $sourceFile = Join-Path $chocoRoot 'config\chocolatey.config'
    if (Test-Path -LiteralPath $sourceFile) {
        $sourceXml = [xml](Get-Content -LiteralPath $sourceFile -Raw)
        $enabledSources = @($sourceXml.chocolatey.sources.source | Where-Object { [string]$_.disabled -ne 'true' } |
            ForEach-Object { [string]$_.value })
    }
    return @{
        schema_version=1;server=$env:COMPUTERNAME;assessed_utc=(Get-Date).ToUniversalTime().ToString('o');os_name=[string]$osInfo.Caption;
        execution_policy=[string](Get-ExecutionPolicy);installed_build=$installedBuild;baseline_name=[string]$Configuration.baseline_name;
        wsus=@{status=if($policyVerified -and $reachable){'PASS'}else{'FAIL'};policy_verified=$policyVerified;
            endpoint_reachable=$reachable;configured_url=$configuredUrl;expected_url=[string]$Configuration.wsus_url;
            managed_install_history=$managedHistory;evidence=$wsusEvidence};
        patching=@{status=$osStatus;comparison=$comparison;expected_build=[string]$baseline.build;expected_kb=[string]$baseline.kb;
            exact_kb_present=($baseline.kb -in $hotfixIds);installed_hotfix_ids=$hotfixIds;dotnet_kbs_present=$dotnet;
            reboot_pending=[bool]$pendingReboot;evidence=$patchEvidence};
        applications=$applications;enabled_package_sources=$enabledSources;package_history_events=$packageHistory;errors=$errors
    }
}

if ($FunctionsOnly) { return }
try {
    if (-not $ExpectedJson) {
        if (-not $ConfigPath) { $ConfigPath = Join-Path $PSScriptRoot 'expected.json' }
        $ExpectedJson = Get-Content -LiteralPath $ConfigPath -Raw -Encoding UTF8
    }
    $report = Get-WindowsDemoProof ($ExpectedJson | ConvertFrom-Json)
    if (Get-Variable Ansible -ErrorAction SilentlyContinue) {
        $Ansible.Changed = $false
        $Ansible.Result = $report
    } elseif ($AsJson) { $report | ConvertTo-Json -Depth 12 }
    else { Write-DemoProofConsole $report }
} catch {
    if (Get-Variable Ansible -ErrorAction SilentlyContinue) { throw }
    Write-Host ('[ERROR] ' + $_.Exception.Message) -ForegroundColor Red
    if ($AsJson) { throw }
}
