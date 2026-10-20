# Run with Windows PowerShell 5.1 or PowerShell 7; no WSUS service is required.
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '..\assets\wsus-patch-month-functions.ps1')
if (-not ('Microsoft.UpdateServices.Administration.UpdateRelationship' -as [type])) {
    Add-Type @'
namespace Microsoft.UpdateServices.Administration {
    public enum UpdateRelationship { UpdatesRequiredByThisUpdate, UpdatesBundledByThisUpdate }
}
'@
}
function Assert-True {
    param([bool]$Condition, [string]$Message)
    if (-not $Condition) { throw $Message }
    $script:Assertions++
}
function Assert-Throws {
    param([scriptblock]$Action, [string]$Pattern)
    $message = $null
    try { & $Action | Out-Null } catch { $message = $_.Exception.Message }
    Assert-True ($message -and $message -match $Pattern) "Expected failure matching: $Pattern; actual: $message"
}
function New-TestUpdate {
    param([string]$Title, [string]$Product, [object[]]$Required = @(), [object[]]$Bundled = @())
    $update = [pscustomobject]@{
        Title = $Title; ProductTitles = @($Product); UpdateClassificationTitle = 'Security Updates'
        IsLatestRevision = $true; PublicationState = 'Published'
        Id = [pscustomobject]@{ UpdateId = [guid]::NewGuid(); RevisionNumber = 200 }
        Required = $Required; Bundled = $Bundled
    }
    $update | Add-Member ScriptMethod GetRelatedUpdates {
        param($Relationship)
        if ([string]$Relationship -eq 'UpdatesRequiredByThisUpdate') { return @($this.Required) }
        return @($this.Bundled)
    }
    $update | Add-Member ScriptMethod GetInstallableItems { return @('test-payload') }
    return $update
}
function New-TestServer {
    param([object[]]$Updates)
    $server = [pscustomobject]@{ Updates = $Updates }
    $server | Add-Member ScriptMethod GetUpdates { return @($this.Updates) }
    return $server
}
$script:Assertions = 0
$products = @('Microsoft Server operating system-21H2', 'Microsoft Server operating system-24H2')
$classes = @('Security Updates', 'Critical Updates')
$os2022 = New-TestUpdate '2026-04 Cumulative Update for server x64 (KB1111111)' $products[0]
$os2025 = New-TestUpdate '2026-04 Cumulative Update for server x64 (KB2222222)' $products[1]
$net2022 = New-TestUpdate '2025-10 Cumulative Update for .NET Framework x64 (KB3333333)' $products[0]
$net2025 = New-TestUpdate '2026-03 Cumulative Update for .NET Framework x64 (KB4444444)' $products[1]
$newer = New-TestUpdate '2026-05 Cumulative Update for server x64 (KB5555555)' $products[0]
$unknown = New-TestUpdate 'Unclassified package without a release marker' $products[0]
$preview = New-TestUpdate '2026-04 Cumulative Update Preview for server x64 (KB6666666)' $products[0]
$arm = New-TestUpdate '2026-04 Cumulative Update for .NET Framework arm64 (KB7777777)' $products[1]
$updates = @($os2022, $os2025, $net2022, $net2025, $newer, $unknown, $preview, $arm)
$server = New-TestServer $updates
$plan = Get-WsusPatchMonthPlan $server '2026-04' $products $classes
Assert-True ($plan.Roots.Count -eq 4) 'Select both OS and latest eligible .NET releases.'
Assert-True ($plan.Allowed.ContainsKey([string]$net2022.Id.UpdateId)) '.NET fallback must allow an older release month.'
foreach ($blocked in @($newer, $unknown, $preview, $arm)) {
    Assert-True (-not $plan.Allowed.ContainsKey([string]$blocked.Id.UpdateId)) 'Unknown, later and unsuitable packages must be blocked.'
}
Assert-Throws { Get-WsusPatchMonthPlan $server '2026-13' $products $classes } 'YYYY-MM'
Assert-Throws { Get-WsusPatchMonthPlan $server 'April 2026' $products $classes } 'YYYY-MM'
Assert-Throws { Get-WsusPatchMonthPlan $server '2026-03' $products $classes } 'no regular OS'
$oldPrerequisite = New-TestUpdate '2025-09 Servicing Stack Update for x64' $products[0]
$os2022.Required = @($oldPrerequisite)
$plan = Get-WsusPatchMonthPlan $server '2026-04' $products $classes
Assert-True ($plan.Allowed.ContainsKey([string]$oldPrerequisite.Id.UpdateId)) 'Include older file-bearing prerequisites.'
$os2022.Required = @($unknown)
Assert-Throws { Get-WsusPatchMonthPlan $server '2026-04' $products $classes } 'unknown or later'
$os2022.Required = @($newer)
Assert-Throws { Get-WsusPatchMonthPlan $server '2026-04' $products $classes } 'unknown or later'
$os2022.Required = @($unknown)
$audited = @{ ([string]$unknown.Id.UpdateId) = '2026-03' }
$plan = Get-WsusPatchMonthPlan $server '2026-04' $products $classes $audited
Assert-True ($plan.Allowed.ContainsKey([string]$unknown.Id.UpdateId)) 'Accept an explicitly audited prerequisite month.'
$os2022.Required = @()
$os2022.Bundled = @($oldPrerequisite)
$plan = Get-WsusPatchMonthPlan $server '2026-04' $products $classes
Assert-True ($plan.Allowed.ContainsKey([string]$oldPrerequisite.Id.UpdateId)) 'Include bundled children in the allowed graph.'
Assert-True (-not $plan.Explicit.ContainsKey([string]$oldPrerequisite.Id.UpdateId)) 'Bundle-only child approvals belong to the parent.'
$summary = Get-WsusPatchMonthSummary $plan @{ MissingBytes = 0 }
$actualIds = @($summary.selected_updates | ForEach-Object { $_['id'] })
$sortedIds = @($actualIds | Sort-Object)
Assert-True (($actualIds -join ',') -eq ($sortedIds -join ',')) 'Selected identities must have canonical ordering on Windows PowerShell 5.1.'
$newer.Bundled = @($oldPrerequisite)
Assert-Throws { Get-WsusPatchMonthPlan $server '2026-04' $products $classes } 'shares an allowed child'
$newer.Bundled = @()
$os2022.PublicationState = 'Expired'
Assert-Throws { Get-WsusPatchMonthPlan $server '2026-04' $products $classes } 'not published'
Write-Output "Passed $Assertions WSUS month-selection assertions."
