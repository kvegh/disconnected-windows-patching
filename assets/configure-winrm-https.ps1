# Run in Windows PowerShell as Administrator.
# Creates a self-signed certificate, an HTTPS WinRM listener and a scoped firewall rule.
# Configure certificate trust in AAP separately. Does not change remote UAC policy.
$ErrorActionPreference = 'Stop'

$managementSource = Read-Host 'AAP execution node IP allowed to connect'
if ([string]::IsNullOrWhiteSpace($managementSource)) {
    throw 'An AAP execution node IP address is required.'
}
$parsedAddress = $null
if (-not [System.Net.IPAddress]::TryParse($managementSource, [ref]$parsedAddress)) {
    throw 'Enter a valid IP address.'
}

if (Get-NetFirewallRule -Name 'AAP-WinRM-HTTPS' -ErrorAction SilentlyContinue) {
    throw 'AAP-WinRM-HTTPS firewall rule already exists. Review it before changing it.'
}

Set-Service WinRM -StartupType Automatic
Start-Service WinRM

$cert = New-SelfSignedCertificate `
    -DnsName $env:COMPUTERNAME `
    -CertStoreLocation Cert:\LocalMachine\My

New-Item -Path WSMan:\localhost\Listener `
    -Transport HTTPS -Address '*' `
    -CertificateThumbPrint $cert.Thumbprint -Force

New-NetFirewallRule `
    -Name 'AAP-WinRM-HTTPS' `
    -DisplayName 'AAP WinRM HTTPS' `
    -Direction Inbound -Action Allow `
    -Protocol TCP -LocalPort 5986 `
    -RemoteAddress $managementSource -Profile Any

winrm enumerate winrm/config/listener
Write-Host "Certificate thumbprint: $($cert.Thumbprint)"
Write-Host 'Configure certificate trust and hostname matching in AAP before connecting.'
