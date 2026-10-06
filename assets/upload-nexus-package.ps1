[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$PackagePath,
    [Parameter(Mandatory)][string]$ExpectedSha256,
    [Parameter(Mandatory)][string]$Repository,
    [Parameter(Mandatory)][PSCredential]$Credential
)
$ErrorActionPreference = 'Stop'
$Ansible.Changed = $false
if ($Repository -notmatch '^[A-Za-z0-9][A-Za-z0-9._-]*$') { throw 'Invalid repository name.' }
if ((Get-FileHash -LiteralPath $PackagePath -Algorithm SHA256).Hash -ne $ExpectedSha256) {
    throw 'Package bytes changed before upload.'
}
Add-Type -AssemblyName System.Net.Http
$handler = New-Object System.Net.Http.HttpClientHandler
$handler.AllowAutoRedirect = $false
$client = [System.Net.Http.HttpClient]::new($handler)
$client.Timeout = [TimeSpan]::FromMinutes(5)
$multipart = New-Object System.Net.Http.MultipartFormDataContent
try {
    $pair = $Credential.UserName + ':' + $Credential.GetNetworkCredential().Password
    $encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($pair))
    $client.DefaultRequestHeaders.Authorization = [System.Net.Http.Headers.AuthenticationHeaderValue]::new('Basic', $encoded)
    $file = [System.Net.Http.StreamContent]::new([IO.File]::OpenRead($PackagePath))
    $file.Headers.ContentType = [System.Net.Http.Headers.MediaTypeHeaderValue]::new('application/octet-stream')
    $multipart.Add($file, 'nuget.asset', [IO.Path]::GetFileName($PackagePath))
    $url = 'http://localhost:8081/service/rest/v1/components?repository=' + [Uri]::EscapeDataString($Repository)
    $response = $client.PostAsync($url, $multipart).GetAwaiter().GetResult()
    try {
        if ([int]$response.StatusCode -ne 204) {
            throw "Nexus package upload failed with HTTP $([int]$response.StatusCode)."
        }
    } finally { $response.Dispose() }
    $Ansible.Changed = $true
} finally { $multipart.Dispose(); $client.Dispose() }
