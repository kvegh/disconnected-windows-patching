[CmdletBinding(SupportsShouldProcess)]
param([string]$ManifestPath, [int]$ReserveGB)
$ErrorActionPreference = 'Stop'
$Ansible.Changed = $false
$manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
if ($manifest.schemaVersion -ne 1 -or $manifest.express -or @($manifest.languages).Count -eq 0 -or
    $manifest.snapshot -notmatch '^snapshot-[0-9]{8}T[0-9]{6}-[a-f0-9]{32}$' -or
    $manifest.metadata.path -ne "$($manifest.snapshot)/metadata.xml.gz" -or
    $manifest.metadata.sha256 -notmatch '^[a-f0-9]{64}$' -or $manifest.metadata.length -le 0 -or
    @($manifest.files).Count -eq 0 -or @($manifest.updates).Count -eq 0) {
    throw 'Invalid export manifest.'
}
Import-Module UpdateServices
$server = Get-WsusServer
$config = $server.GetConfiguration()
if ($config.IsReplicaServer -or $config.HostBinariesOnMicrosoftUpdate -or
    [string]$server.GetSubscription().GetSynchronizationStatus() -ne 'NotProcessing') {
    throw 'Internal WSUS must be autonomous, locally storing files and not synchronizing.'
}
$content = (Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Update Services\Server\Setup').ContentDir.TrimEnd('\')
if ((Split-Path $content -Leaf) -ne 'WsusContent') { $content = Join-Path $content 'WsusContent' }
if (-not (Test-Path -LiteralPath $content)) { throw 'Internal update content directory is missing.' }
$paths = @{}
$directories = @{}
$requiredBytes = [long]$manifest.metadata.length
foreach ($file in $manifest.files) {
    if ($file.relativePath -notmatch '^[A-Za-z0-9_.-]+(/[A-Za-z0-9_.-]+)*$' -or
        @($file.relativePath.Split('/') | Where-Object { $_ -in @('.', '..', 'web.config') }).Count -gt 0 -or
        $file.sha256 -notmatch '^[a-f0-9]{64}$' -or $file.length -lt 0 -or
        $paths.ContainsKey($file.relativePath)) { throw 'Invalid or duplicate content path/checksum in manifest.' }
    $paths[$file.relativePath] = $true
    $destination = [IO.Path]::GetFullPath((Join-Path $content $file.relativePath))
    if (-not $destination.StartsWith($content + '\', [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Content path escapes the WSUS directory.'
    }
    $directory = Split-Path $file.relativePath -Parent
    if ($directory) { $directories[$directory.Replace('\', '/')] = $true }
    $matching = (Test-Path -LiteralPath $destination) -and
        (Get-Item $destination).Length -eq $file.length -and
        (Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash.ToLowerInvariant() -eq $file.sha256
    if (-not $matching) { $requiredBytes += [long]$file.length }
}
$drive = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='$([IO.Path]::GetPathRoot($content).TrimEnd('\'))'"
if ($requiredBytes + ($ReserveGB * 1GB) -gt $drive.FreeSpace) {
    throw 'Internal disk cannot hold the missing update files and configured reserve.'
}
if (-not $Ansible.CheckMode) {
    if ($config.DownloadExpressPackages -or $config.AllUpdateLanguagesEnabled -or
        ((@($config.GetEnabledUpdateLanguages() | Sort-Object) -join ',') -ne
         (@($manifest.languages | Sort-Object) -join ','))) {
        $config.DownloadExpressPackages = $false
        $config.AllUpdateLanguagesEnabled = $false
        $config.SetEnabledUpdateLanguages([string[]]$manifest.languages)
        $config.Save()
        $Ansible.Changed = $true
    }
    $subscription = $server.GetSubscription()
    if ($subscription.SynchronizeAutomatically) {
        $subscription.SynchronizeAutomatically = $false
        $subscription.Save()
        $Ansible.Changed = $true
    }
}
$Ansible.Result = @{
    ContentPath = $content
    Directories = @($directories.Keys | Sort-Object)
    RequiredBytes = $requiredBytes
    Files = @($manifest.files).Count
}
