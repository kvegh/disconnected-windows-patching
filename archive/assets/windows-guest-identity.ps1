# Purpose and language choice: [rationale](../docs/supporting-code.md#windows-inspection-and-evidence).
$ErrorActionPreference = 'Stop'
$computer = Get-CimInstance Win32_ComputerSystem
$product = Get-CimInstance Win32_ComputerSystemProduct
$os = Get-CimInstance Win32_OperatingSystem
$interfaces = @(Get-NetAdapter | Where-Object Status -eq 'Up' | ForEach-Object {
    $adapter = $_
    $addresses = @(Get-NetIPAddress -InterfaceIndex $adapter.ifIndex -AddressFamily IPv4 |
        Where-Object AddressState -eq 'Preferred' | Select-Object -ExpandProperty IPAddress | Sort-Object)
    @{ mac = $adapter.MacAddress.ToLower().Replace('-', ':'); addresses = $addresses }
})
$updateSettings = Get-ItemProperty 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate' -ErrorAction SilentlyContinue
$urls = @($updateSettings.WUServer, $updateSettings.WUStatusServer) |
    Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | Select-Object -Unique
$Ansible.Changed = $false
$Ansible.Result = @{
    computer_name = $computer.Name
    computer_uuid = $product.UUID
    part_of_domain = [bool]$computer.PartOfDomain
    domain = $computer.Domain
    os_product_type = [int]$os.ProductType
    os_build = $os.BuildNumber
    interfaces = $interfaces
    update_urls = @($urls)
}
