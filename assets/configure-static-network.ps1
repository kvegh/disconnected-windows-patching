param(
    [Parameter(Mandatory)][string]$ConfigurationJson,
    [bool]$DisableForwarding = $false,
    [bool]$ValidateOnly = $false
)
$ErrorActionPreference = 'Stop'
$Ansible.Changed = $false
$configs = @($ConfigurationJson | ConvertFrom-Json)
$adapters = @(Get-NetAdapter)
$resolved = @()
# Validate every interface before changing any networking.
foreach ($config in $configs) {
    $mac = $config.mac -replace '[:-]', ''
    $matches = @($adapters | Where-Object { ($_.MacAddress -replace '[:-]', '') -eq $mac })
    if ($matches.Count -ne 1) { throw 'A configured MAC must match exactly one Windows adapter.' }
    $adapter = $matches[0]
    $collision = @($adapters | Where-Object { $_.Name -eq $config.name -and $_.InterfaceIndex -ne $adapter.InterfaceIndex })
    if ($collision.Count) { throw 'A desired adapter name belongs to another NIC.' }
    $ip = [Net.IPAddress]::Parse($config.ipv4_address)
    if ($ip.AddressFamily -ne [Net.Sockets.AddressFamily]::InterNetwork) { throw 'IPv4 address required.' }
    if ([int]$config.prefix_length -lt 1 -or [int]$config.prefix_length -gt 32) { throw 'Invalid IPv4 prefix.' }
    if ($config.gateway) {
        $gateway = [Net.IPAddress]::Parse($config.gateway)
        if ($gateway.AddressFamily -ne [Net.Sockets.AddressFamily]::InterNetwork) { throw 'IPv4 gateway required.' }
    }
    foreach ($dns in @($config.dns_servers)) { $null = [Net.IPAddress]::Parse($dns) }
    $resolved += @{ Config = $config; Index = $adapter.InterfaceIndex }
}
if (@($resolved.Index | Select-Object -Unique).Count -ne $resolved.Count) { throw 'Duplicate adapters in network configuration.' }
if ($ValidateOnly) { return }
# Allow the async launcher to return before changing the address used by WinRM.
Start-Sleep -Seconds 10
foreach ($entry in $resolved) {
    $config = $entry.Config
    $index = $entry.Index
    $adapter = Get-NetAdapter -InterfaceIndex $index
    if ($adapter.Name -ne $config.name) {
        Rename-NetAdapter -InputObject $adapter -NewName $config.name
        $Ansible.Changed = $true
    }
    $interface = Get-NetIPInterface -InterfaceIndex $index -AddressFamily IPv4
    if ($interface.Dhcp -ne 'Disabled') {
        Set-NetIPInterface -InterfaceIndex $index -AddressFamily IPv4 -Dhcp Disabled
        $Ansible.Changed = $true
    }
    # These NICs are owned by the demo: replace other IPv4 addresses explicitly.
    $addresses = @(Get-NetIPAddress -InterfaceIndex $index -AddressFamily IPv4 -ErrorAction SilentlyContinue)
    foreach ($address in $addresses) {
        if ($address.IPAddress -ne $config.ipv4_address -or $address.PrefixLength -ne [int]$config.prefix_length) {
            Remove-NetIPAddress -InputObject $address -Confirm:$false
            $Ansible.Changed = $true
        }
    }
    $desired = @(Get-NetIPAddress -InterfaceIndex $index -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object { $_.IPAddress -eq $config.ipv4_address -and $_.PrefixLength -eq [int]$config.prefix_length })
    if (-not $desired.Count) {
        New-NetIPAddress -InterfaceIndex $index -IPAddress $config.ipv4_address -PrefixLength ([int]$config.prefix_length) | Out-Null
        $Ansible.Changed = $true
    }
    # Remove obsolete defaults from both active and persistent stores.
    foreach ($store in @('PersistentStore', 'ActiveStore')) {
        $routes = @(Get-NetRoute -InterfaceIndex $index -AddressFamily IPv4 -DestinationPrefix '0.0.0.0/0' -PolicyStore $store -ErrorAction SilentlyContinue)
        foreach ($route in $routes) {
            if (-not $config.gateway -or $route.NextHop -ne $config.gateway) {
                Remove-NetRoute -InputObject $route -Confirm:$false
                $Ansible.Changed = $true
            }
        }
    }
    if ($config.gateway) {
        $route = @(Get-NetRoute -InterfaceIndex $index -AddressFamily IPv4 -DestinationPrefix '0.0.0.0/0' -ErrorAction SilentlyContinue |
            Where-Object { $_.NextHop -eq $config.gateway })
        if (-not $route.Count) {
            New-NetRoute -InterfaceIndex $index -DestinationPrefix '0.0.0.0/0' -NextHop $config.gateway | Out-Null
            $Ansible.Changed = $true
        }
    }
    $currentDns = @((Get-DnsClientServerAddress -InterfaceIndex $index -AddressFamily IPv4).ServerAddresses)
    $desiredDns = @($config.dns_servers)
    if (($currentDns -join ',') -ne ($desiredDns -join ',')) {
        # An empty list on a DHCP-disabled NIC clears configured DNS servers.
        if ($desiredDns.Count) {
            Set-DnsClientServerAddress -InterfaceIndex $index -ServerAddresses $desiredDns
        } else {
            Set-DnsClientServerAddress -InterfaceIndex $index -ResetServerAddresses
        }
        $Ansible.Changed = $true
    }
}
if ($DisableForwarding) {
    Get-NetIPInterface | Where-Object Forwarding -eq 'Enabled' | ForEach-Object {
        Set-NetIPInterface -InterfaceIndex $_.InterfaceIndex -AddressFamily $_.AddressFamily -Forwarding Disabled
        $Ansible.Changed = $true
    }
    $path = 'HKLM:\SYSTEM\CurrentControlSet\Services\Tcpip\Parameters'
    if ((Get-ItemProperty $path).IPEnableRouter -ne 0) {
        Set-ItemProperty -Path $path -Name IPEnableRouter -Value 0
        $Ansible.Changed = $true
    }
}
