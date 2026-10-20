# Pure selection helpers and read-only WSUS/file inspection shared by the jobs.
function Get-WsusTitleMonth {
    param([string]$Title)
    if ($Title -match '^(?<month>20[0-9]{2}-(0[1-9]|1[0-2]))(?:\s|$)') {
        return $Matches.month
    }
    return $null
}

function Test-WsusRegularCumulativeUpdate {
    param($Update, [string]$Product, [string[]]$Classifications)
    return ($Product -in @($Update.ProductTitles) -and
        $Update.UpdateClassificationTitle -in $Classifications -and
        $Update.Title -match '(?i)cumulative update' -and
        $Update.Title -notmatch '(?i)\b(preview|dynamic|hotpatch|arm64|x86|itanium)\b')
}

function Get-WsusPatchMonthPlan {
    param($Server, [string]$Month, [string[]]$Products,
        [string[]]$Classifications, [hashtable]$PrerequisiteMonths = @{})
    if ($Month -notmatch '^2026-(0[1-9]|1[0-2])$') {
        throw 'A supported 2026 release month in YYYY-MM format is required.'
    }
    $all = @($Server.GetUpdates() | Where-Object IsLatestRevision)
    $roots = @{}
    foreach ($product in $Products) {
        $regular = @($all | Where-Object {
            (Test-WsusRegularCumulativeUpdate $_ $product $Classifications) -and
            (Get-WsusTitleMonth $_.Title) -and
            (Get-WsusTitleMonth $_.Title) -le $Month
        })
        $os = @($regular | Where-Object {
            $_.Title -notmatch '(?i)\.NET' -and (Get-WsusTitleMonth $_.Title) -eq $Month
        })
        if ($os.Count -eq 0) {
            throw "The catalogue has no regular OS cumulative update for $product in $Month."
        }
        # .NET does not publish every month: retain its newest release <= ceiling.
        $dotnet = @($regular | Where-Object { $_.Title -match '(?i)\.NET' })
        if ($dotnet.Count -eq 0) {
            throw "The catalogue has no .NET cumulative baseline at or before $Month for $product."
        }
        $dotnetMonth = @($dotnet | ForEach-Object { Get-WsusTitleMonth $_.Title } |
            Sort-Object -Descending)[0]
        foreach ($update in @($os) + @($dotnet | Where-Object {
            (Get-WsusTitleMonth $_.Title) -eq $dotnetMonth
        })) { $roots[[string]$update.Id.UpdateId] = $update }
    }
    $allowed = @{}
    $explicit = @{} + $roots
    $queue = New-Object 'System.Collections.Generic.Queue[object]'
    foreach ($update in $roots.Values) { $queue.Enqueue($update) }
    while ($queue.Count -gt 0) {
        $update = $queue.Dequeue()
        $id = [string]$update.Id.UpdateId
        if ($allowed.ContainsKey($id)) { continue }
        if ([string]$update.PublicationState -ne 'Published') {
            throw "A selected update is not published and cannot be approved safely: $id."
        }
        $release = Get-WsusTitleMonth $update.Title
        if (-not $release -and $PrerequisiteMonths.ContainsKey($id)) {
            $release = [string]$PrerequisiteMonths[$id]
        }
        if ($release -notmatch '^20[0-9]{2}-(0[1-9]|1[0-2])$' -or $release -gt $Month) {
            throw "A prerequisite has an unknown or later release month: $id. Audit its identity before continuing."
        }
        $allowed[$id] = $update
        foreach ($required in $update.GetRelatedUpdates(
            [Microsoft.UpdateServices.Administration.UpdateRelationship]::UpdatesRequiredByThisUpdate)) {
            if (@($required.GetInstallableItems()).Count -gt 0) {
                $explicit[[string]$required.Id.UpdateId] = $required
            }
            $queue.Enqueue($required)
        }
        foreach ($child in $update.GetRelatedUpdates(
            [Microsoft.UpdateServices.Administration.UpdateRelationship]::UpdatesBundledByThisUpdate)) {
            $queue.Enqueue($child)
        }
    }
    $blocked = @($all | Where-Object { -not $allowed.ContainsKey([string]$_.Id.UpdateId) })
    # Decline recursively declines bundled children, including shared children.
    # Reject an ambiguous graph before mutation rather than undoing a decline later.
    foreach ($update in $blocked) {
        $seen = @{}
        $queue.Enqueue($update)
        while ($queue.Count -gt 0) {
            $parent = $queue.Dequeue()
            $key = [string]$parent.Id.UpdateId
            if ($seen.ContainsKey($key)) { continue }
            $seen[$key] = $true
            foreach ($child in $parent.GetRelatedUpdates(
                [Microsoft.UpdateServices.Administration.UpdateRelationship]::UpdatesBundledByThisUpdate)) {
                if ($allowed.ContainsKey([string]$child.Id.UpdateId)) {
                    throw "A blocked bundle shares an allowed child ($($child.Id.UpdateId)); inspect the graph before changing policy."
                }
                $queue.Enqueue($child)
            }
        }
    }
    return @{ Month = $Month; All = $all; Roots = $roots; Allowed = $allowed;
        Explicit = $explicit; Blocked = $blocked }
}

function Get-WsusPatchMonthContent {
    param([hashtable]$Plan)
    $content = (Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Update Services\Server\Setup').ContentDir.TrimEnd('\')
    if ((Split-Path $content -Leaf) -ne 'WsusContent') { $content = Join-Path $content 'WsusContent' }
    $files = @{}
    foreach ($update in $Plan.Allowed.Values) {
        foreach ($item in $update.GetInstallableItems()) {
            foreach ($file in $item.Files) {
                if ([string]$file.Type -eq 'Express') { continue }
                $relative = ([uri]$file.FileUri).AbsolutePath -replace '(?i)^/Content/', ''
                if ($relative -notmatch '^[A-Fa-f0-9]{2}/(?<hash>[A-Fa-f0-9]{40})\.[A-Za-z0-9]+$') {
                    throw 'An unexpected WSUS content path cannot be verified safely.'
                }
                $path = Join-Path $content $relative.Replace('/', '\')
                $matching = (Test-Path -LiteralPath $path -PathType Leaf) -and
                    (Get-Item -LiteralPath $path).Length -eq [long]$file.TotalBytes
                # WSUS readiness and transfer verification establish integrity.
                # Policy and disk-budget checks only need existence and length.
                $files[$relative] = @{ Path = $path; Bytes = [long]$file.TotalBytes; Present = [bool]$matching }
            }
        }
    }
    if ($files.Count -eq 0) { throw 'The selected baseline has no verifiable full update files.' }
    $missing = [long](($files.Values | Where-Object { -not $_.Present } |
        ForEach-Object { $_.Bytes } | Measure-Object -Sum).Sum)
    $drive = Get-CimInstance Win32_LogicalDisk -Filter (
        "DeviceID='" + [IO.Path]::GetPathRoot($content).TrimEnd('\') + "'")
    return @{ Files = $files; MissingBytes = $missing; FreeBytes = [long]$drive.FreeSpace }
}

function Get-WsusPatchMonthSummary {
    param([hashtable]$Plan, [hashtable]$Content)
    return @{
        schema_version = 1
        patch_month = $Plan.Month
        selected_updates = @($Plan.Allowed.Values | ForEach-Object {
            @{ id = [string]$_.Id.UpdateId; revision = $_.Id.RevisionNumber; title = $_.Title;
                kb = @($_.KnowledgebaseArticles); products = @($_.ProductTitles) }
        } | Sort-Object { $_['id'] })
        blocked_updates = $Plan.Blocked.Count
        missing_content_bytes = $Content.MissingBytes
        pending_license_updates = @($Plan.Allowed.Values | Where-Object RequiresLicenseAgreementAcceptance |
            ForEach-Object { [string]$_.Id.UpdateId })
    }
}

function Get-WsusPatchMonthPolicyViolations {
    param($Server, [hashtable]$Plan, [hashtable]$Content)
    $problems = New-Object 'System.Collections.Generic.List[string]'
    $allComputersId = [guid]'a0a08746-4dbe-4a37-9adf-9e7652c0b421'
    foreach ($update in @($Server.GetUpdates() | Where-Object IsLatestRevision)) {
        $id = [string]$update.Id.UpdateId
        if (-not $Plan.Allowed.ContainsKey($id)) {
            if (-not $update.IsDeclined) { $problems.Add("not-declined:$id") }
        } elseif ($update.Id.RevisionNumber -ne $Plan.Allowed[$id].Id.RevisionNumber) {
            $problems.Add("revision-changed:$id")
        }
    }
    foreach ($update in $Plan.Allowed.Values) {
        $update.Refresh()
        if ($update.IsDeclined) { $problems.Add("allowed-declined:$($update.Id.UpdateId)") }
        if ($update.RequiresLicenseAgreementAcceptance) { $problems.Add("license-pending:$($update.Id.UpdateId)") }
    }
    foreach ($update in $Plan.Explicit.Values) {
        $update.Refresh()
        if ([string]$update.State -ne 'Ready') { $problems.Add("not-ready:$($update.Id.UpdateId)") }
        $approvals = @($update.GetUpdateApprovals() | Where-Object { [string]$_.Action -ne 'Bundle' })
        $wanted = @($approvals | Where-Object {
            [string]$_.Action -eq 'Install' -and $_.ComputerTargetGroupId -eq $allComputersId -and
            $_.UpdateId.RevisionNumber -eq $update.Id.RevisionNumber -and
            $_.UpdateId.UpdateId -eq $update.Id.UpdateId -and $_.Deadline -eq [datetime]::MaxValue
        })
        if ($wanted.Count -ne 1 -or $approvals.Count -ne 1) {
            $problems.Add("approval-mismatch:$($update.Id.UpdateId)")
        }
    }
    $config = $Server.GetConfiguration()
    if ($config.AutoRefreshUpdateApprovals -or $config.AutoApproveWsusInfrastructureUpdates) {
        $problems.Add('automatic-revision-or-infrastructure-approval')
    }
    if (@($Server.GetInstallApprovalRules() | Where-Object Enabled).Count -gt 0) {
        $problems.Add('automatic-approval-rule')
    }
    if ($Server.GetSubscription().SynchronizeAutomatically) { $problems.Add('scheduled-synchronization') }
    if ($Content.MissingBytes -gt 0) { $problems.Add('missing-or-incomplete-content') }
    return @($problems.ToArray())
}
