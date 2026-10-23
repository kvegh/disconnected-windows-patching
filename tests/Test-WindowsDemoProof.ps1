param([Parameter(Mandatory)][string]$ReporterPath)
$ErrorActionPreference = 'Stop'
. $ReporterPath -FunctionsOnly
$script:DemoProofCases = 0
function Assert-DemoEqual {
    param($Actual,$Expected,[string]$Message)
    if ($Actual -ne $Expected) { throw $Message }
    $script:DemoProofCases++
}
Assert-DemoEqual (Get-DemoBuildComparison '20348.5020' '20348.5020') 'exact' 'Exact April build was not recognized.'
Assert-DemoEqual (Get-DemoBuildComparison '20348.5139' '20348.5020') 'above' 'A newer build was incorrectly accepted as the exact cutoff.'
Assert-DemoEqual (Get-DemoBuildComparison '26100.32522' '26100.32690') 'below' 'An older build was incorrectly accepted.'
$lines = @(
    '2026-04-20 12:00:00,000 100 [INFO ] - 7zip.install v26.3.0 [Approved]',
    '2026-04-20 12:00:02,000 100 [INFO ] - The install of 7zip.install was successful.',
    '2026-04-20 13:00:00,000 100 [INFO ] - 7zip.install v26.4.0 [Approved]',
    '2026-04-20 13:00:02,000 100 [INFO ] - The upgrade of 7zip.install was successful.'
)
$events = @(ConvertFrom-DemoChocolateyHistory $lines)
Assert-DemoEqual $events.Count 2 'Successful package operations were not extracted.'
Assert-DemoEqual (Get-DemoPackageSequence $events '7zip.install' '26.3.0' '26.4.0').status 'PASS' 'A valid baseline-to-upgrade sequence failed.'
Assert-DemoEqual (Get-DemoPackageSequence @($events[1]) '7zip.install' '26.3.0' '26.4.0').status 'WARN' 'A current version without baseline history was treated as historical proof.'
Assert-DemoEqual (Get-DemoPackageSequence $events 'git.install' '2.55.0.5' '2.56.0.2').status 'WARN' 'Another package history was incorrectly accepted.'
$failed = @(ConvertFrom-DemoChocolateyHistory @(
    '2026-04-20 12:00:00,000 100 [INFO ] - git.install v2.55.0.5 [Approved]',
    '2026-04-20 12:00:02,000 100 [ERROR] - The install of git.install was NOT successful.'
))
Assert-DemoEqual $failed.Count 0 'A failed installation was incorrectly accepted.'
$unrelated = @(ConvertFrom-DemoChocolateyHistory @(
    '2026-04-20 12:00:00,000 100 [INFO ] - Downloading 7zip.install v26.3.0',
    '2026-04-20 12:00:02,000 100 [INFO ] - The install of 7zip.install was successful.'
))
Assert-DemoEqual $unrelated.Count 0 'A download mention was incorrectly accepted as installed-version evidence.'
$reversed = @(
    [pscustomobject]@{id='7zip.install';version='26.3.0';operation='install';observed_utc='2026-04-21T12:00:00Z'},
    [pscustomobject]@{id='7zip.install';version='26.4.0';operation='upgrade';observed_utc='2026-04-20T12:00:00Z'}
)
Assert-DemoEqual (Get-DemoPackageSequence $reversed '7zip.install' '26.3.0' '26.4.0').status 'WARN' 'Reversed chronology was incorrectly accepted.'
$Ansible.Changed = $false
$Ansible.Result = @{ CasesPassed=$script:DemoProofCases; MissingHistoryDoesNotPass=$true; FailedInstallDoesNotPass=$true; LaterBuildIsNotExactApril=$true }
