[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$ArchivePath,
    [Parameter(Mandatory)][string]$ManifestSha256,
    [Parameter(Mandatory)][string]$ExpectedPackagesJson
)
$ErrorActionPreference = 'Stop'
$Ansible.Changed = $false
Add-Type -AssemblyName System.IO.Compression.FileSystem
$expected = @(ConvertFrom-Json -InputObject $ExpectedPackagesJson)
$archive = [System.IO.Compression.ZipFile]::OpenRead($ArchivePath)
try {
    $manifestEntry = $archive.GetEntry('manifest.json')
    if (-not $manifestEntry -or $manifestEntry.Length -gt 1MB) { throw 'Missing or oversized export manifest.' }
    $sha = [System.Security.Cryptography.SHA256]::Create()
    $stream = $manifestEntry.Open()
    try {
        $actual = ([BitConverter]::ToString($sha.ComputeHash($stream))).Replace('-', '').ToLowerInvariant()
    } finally { $stream.Dispose(); $sha.Dispose() }
    if ($actual -ne $ManifestSha256) { throw 'Export manifest differs from the trusted AAP descriptor.' }
    $reader = New-Object System.IO.StreamReader($manifestEntry.Open())
    try { $manifest = ConvertFrom-Json -InputObject $reader.ReadToEnd() } finally { $reader.Dispose() }
    if ($manifest.schema -ne 1 -or @($manifest.packages).Count -ne $expected.Count) {
        throw 'Unexpected export manifest schema or package count.'
    }
    $names = @('manifest.json')
    foreach ($package in $manifest.packages) {
        $matching = @($expected | Where-Object { $_.id -eq $package.id -and $_.version -eq $package.version })
        if ($matching.Count -ne 1 -or $matching[0].track -ne $package.track -or
            $matching[0].installer_sha256 -ne $package.installer_sha256) {
            throw 'Export contains an unexpected package release.'
        }
        $filename = "$($package.id).$($package.version).nupkg"
        if ($package.filename -ne $filename -or $filename -notmatch '^[a-z0-9][a-z0-9.-]*\.nupkg$' -or
            $package.sha256 -notmatch '^[a-f0-9]{64}$') { throw 'Invalid package metadata.' }
        $name = "packages/$filename"
        $entry = $archive.GetEntry($name)
        if (-not $entry -or $entry.Length -gt 200MB) { throw 'Missing or oversized exported package.' }
        $sha = [System.Security.Cryptography.SHA256]::Create()
        $stream = $entry.Open()
        try {
            $actual = ([BitConverter]::ToString($sha.ComputeHash($stream))).Replace('-', '').ToLowerInvariant()
        } finally { $stream.Dispose(); $sha.Dispose() }
        if ($actual -ne $package.sha256) { throw 'Exported package checksum mismatch.' }
        $names += $name
    }
    if (@($names | Select-Object -Unique).Count -ne $names.Count -or $archive.Entries.Count -ne $names.Count) {
        throw 'Duplicate or unexpected archive entries.'
    }
    foreach ($entry in $archive.Entries) {
        if ($entry.FullName -cnotin $names) { throw 'Unsafe or unexpected archive entry path.' }
    }
    $Ansible.Result = @{ Manifest = $manifest }
} finally { $archive.Dispose() }
