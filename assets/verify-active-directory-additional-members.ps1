param(
    [Parameter(Mandatory)][ValidateSet('prepare','verify','cleanup')][string]$Action,
    [Parameter(Mandatory)][string]$ProfileJson,
    [Parameter(Mandatory)][PSCredential]$DomainCredential,
    [string]$ProbePassword,
    [string]$FixtureJson = '{}'
)
$ErrorActionPreference = 'Stop'
Import-Module ActiveDirectory
$PSDefaultParameterValues = @{'*-AD*:Credential'=$DomainCredential; '*-AD*:Server'='localhost'}
$p = $ProfileJson | ConvertFrom-Json
if ((Get-ADDomain).DNSRoot -ne $p.dns_domain) { throw 'Unexpected test directory domain.' }
$marker = 'AAP Windows regional identity demo; temporary membership test'
$ownerMarker = 'AAP Windows regional identity demo'
$path = "OU=DK,$($p.root_dn)"
$userName = "$($p.prefix.ToLower())-probe"
$groupName = "$($p.prefix.ToLower())-probe-gg"
$userDn = "CN=$userName,$path"
$groupDn = "CN=$groupName,$path"
$fixture = $FixtureJson | ConvertFrom-Json
function Get-ProbeObject {
    param([string]$Kind,[string]$Name)
    try {
        if ($Kind -eq 'User') {
            return Get-ADUser -Identity $Name -Properties Description,Enabled,MemberOf,PasswordLastSet -ErrorAction Stop
        }
        return Get-ADGroup -Identity $Name -Properties Description,MemberOf,Members -ErrorAction Stop
    } catch [Microsoft.ActiveDirectory.Management.ADIdentityNotFoundException] { return $null }
}
function Assert-OwnedProbe {
    param($Object,[string]$Dn,[string]$Guid)
    if ($Object -and ($Object.DistinguishedName -ne $Dn -or $Object.Description -ne $marker -or
        -not $Guid -or [string]$Object.ObjectGUID -ne $Guid)) {
        throw 'Refusing to use or remove an unowned membership-test object.'
    }
}
$Ansible.Changed = $false
if ($Action -eq 'prepare') {
    if ($userName.Length -gt 20 -or (Get-ProbeObject User $userName) -or
        (Get-ProbeObject Group $groupName)) { throw 'Membership-test names are already in use or invalid.' }
    foreach ($name in @("$($p.prefix)-GG-DK-reader", "$($p.prefix)-DL-EU-reader")) {
        $g = Get-ADGroup -Identity $name -Properties Description
        if ($g.Description -ne $ownerMarker -or $g.DistinguishedName -notlike "CN=*,OU=*,$($p.root_dn)") {
            throw 'A membership-test target is not an owned demo group.'
        }
    }
    if (-not $ProbePassword) { throw 'A protected temporary-user password is required.' }
    $createdUser = $null
    $createdGroup = $null
    try {
        $createdUser = New-ADUser -Name $userName -SamAccountName $userName -Path $path `
            -UserPrincipalName "$userName@$($p.dns_domain)" -Description $marker `
            -GivenName 'Additional' -Surname 'Reader' -Enabled $true -ChangePasswordAtLogon $false `
            -AccountPassword (ConvertTo-SecureString $ProbePassword -AsPlainText -Force) -PassThru
        $createdGroup = New-ADGroup -Name $groupName -SamAccountName $groupName -Path $path `
            -GroupScope Global -GroupCategory Security -Description $marker -PassThru
        Add-ADGroupMember -Identity "$($p.prefix)-GG-DK-reader" -Members $createdUser
        Add-ADGroupMember -Identity $createdGroup -Members $createdUser
        Add-ADGroupMember -Identity "$($p.prefix)-DL-EU-reader" -Members $createdGroup
        $Ansible.Changed = $true
        $Ansible.Result = @{ Created=$true; UserGuid=[string]$createdUser.ObjectGUID; GroupGuid=[string]$createdGroup.ObjectGUID }
    } catch {
        if ($createdGroup) { Remove-ADGroup -Identity $createdGroup.ObjectGUID -Confirm:$false }
        if ($createdUser) { Remove-ADUser -Identity $createdUser.ObjectGUID -Confirm:$false }
        throw
    }
    return
}
$user = Get-ProbeObject User $userName
$group = Get-ProbeObject Group $groupName
Assert-OwnedProbe $user $userDn ([string]$fixture.UserGuid)
Assert-OwnedProbe $group $groupDn ([string]$fixture.GroupGuid)
if ($Action -eq 'cleanup') {
    if ($group) { Remove-ADGroup -Identity $group.ObjectGUID -Confirm:$false; $Ansible.Changed = $true }
    if ($user) { Remove-ADUser -Identity $user.ObjectGUID -Confirm:$false; $Ansible.Changed = $true }
    if ((Get-ProbeObject User $userName) -or (Get-ProbeObject Group $groupName)) {
        throw 'A temporary membership-test object remains after cleanup.'
    }
    $Ansible.Result = @{ TemporaryObjectsRemoved=$true }
    return
}
if (-not $user -or -not $group -or -not $user.Enabled -or -not $user.PasswordLastSet) {
    throw 'An additional membership-test account or group was not preserved.'
}
if ($userDn -notin @(Get-ADGroupMember -Identity "$($p.prefix)-GG-DK-reader" | ForEach-Object DistinguishedName) -or
    $userDn -notin @(Get-ADGroupMember -Identity $groupName | ForEach-Object DistinguishedName) -or
    $groupDn -notin @(Get-ADGroupMember -Identity "$($p.prefix)-DL-EU-reader" | ForEach-Object DistinguishedName)) {
    throw 'An additional direct user or group membership was not preserved.'
}
foreach ($scope in @('DK','NO','EU','NZ')) {
    foreach ($role in @('reader','executor','admin')) {
        $members = @(Get-ADGroupMember -Identity "$($p.prefix)-DL-$scope-$role" -Recursive | ForEach-Object SamAccountName)
        $expected = $role -eq 'reader' -and $scope -in @('DK','EU')
        if (($userName -in $members) -ne $expected) { throw 'Unexpected additional-user nested permissions.' }
    }
}
$policy = Get-ADUserResultantPasswordPolicy -Identity $userName
if ($policy -and $policy.Name -eq "$($p.prefix)-DemoPasswordPolicy") {
    throw 'The generated-user password policy was unexpectedly extended to an additional account.'
}
$Ansible.Result = @{
    AdditionalUserPreserved=$true; AdditionalGroupPreserved=$true;
    DirectMembershipsPreserved=$true; NestedReaderMembershipsVerified=$true;
    GeneratedPasswordPolicyNotExtended=$true; ReconciliationsPassed=2
}
