# Task Scheduler supplies the SYSTEM session; no runas token or policy changes.
$ErrorActionPreference = 'Stop'
$Ansible = [pscustomobject]@{ Changed = $false; CheckMode = $false; Result = @{} }
$result = @{ success = $false; changed = $false }
$exitCode = 1
try {
    $configuration = Get-Content -LiteralPath "$PSScriptRoot\configuration.json" -Raw | ConvertFrom-Json
    & "$PSScriptRoot\configure-static-network.ps1" `
        -ConfigurationJson (ConvertTo-Json -InputObject @($configuration.interfaces) -Depth 10 -Compress) `
        -DisableForwarding ([bool]$configuration.disable_forwarding)
    $result.success = $true
    $result.changed = $Ansible.Changed
    $exitCode = 0
}
catch {
    $result.error = $_.Exception.Message
    $result.stack = $_.ScriptStackTrace
}
# Atomic publication lets the controller distinguish completion from partial output.
[IO.File]::WriteAllText("$PSScriptRoot\result.json.tmp", ($result | ConvertTo-Json -Depth 10), [Text.UTF8Encoding]::new($false))
Move-Item -LiteralPath "$PSScriptRoot\result.json.tmp" -Destination "$PSScriptRoot\result.json" -Force
exit $exitCode
