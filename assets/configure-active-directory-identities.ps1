param(
    [Parameter(Mandatory)][string]$ProfileJson,
    [Parameter(Mandatory)][PSCredential]$DomainCredential,
    [bool]$ResetDemoUserPasswords = $false
)
$ErrorActionPreference = 'Stop'
Import-Module ActiveDirectory
$PSDefaultParameterValues = @{'*-AD*:Credential'=$DomainCredential; '*-AD*:Server'='localhost'}
$p = $ProfileJson | ConvertFrom-Json
if ((Get-ADDomain).DNSRoot -ne $p.dns_domain) { throw 'Unexpected directory domain.' }
$marker = 'AAP Windows regional identity demo'
$changed = $false
$simpleDemoPasswords = $p.allow_simple_demo_passwords -eq $true
$newDemoAccounts = @()
$disabledDemoAccounts = @()
$passwordsReset = 0
function Get-OptionalDirectoryObject {
    param([string]$Kind,[string]$Identity)
    try {
        switch ($Kind) {
            'OU' { return Get-ADOrganizationalUnit -Identity $Identity -Properties Description -ErrorAction Stop }
            'Group' { return Get-ADGroup -Identity $Identity -Properties Description -ErrorAction Stop }
            'User' { return Get-ADUser -Identity $Identity -Properties Description,Enabled -ErrorAction Stop }
            'PasswordPolicy' { return Get-ADFineGrainedPasswordPolicy -Identity $Identity -Properties Description -ErrorAction Stop }
        }
    } catch [Microsoft.ActiveDirectory.Management.ADIdentityNotFoundException] {
        return $null
    }
}
foreach ($ou in $p.ous) {
    $dn = "OU=$($ou.name),$($ou.path)"
    $existing = Get-OptionalDirectoryObject -Kind OU -Identity $dn
    if (-not $existing) {
        New-ADOrganizationalUnit -Name $ou.name -Path $ou.path -Description $marker -ProtectedFromAccidentalDeletion $true
        $changed = $true
    } elseif ($existing.Description -ne $marker) { throw 'Refusing to adopt an unowned directory OU.' }
}
foreach ($g in $p.groups) {
    $dn = "CN=$($g.name),$($g.path)"
    $existing = Get-OptionalDirectoryObject -Kind Group -Identity $g.name
    if (-not $existing) {
        New-ADGroup -Name $g.name -SamAccountName $g.name -GroupScope $g.scope -GroupCategory Security -Path $g.path -Description $marker
        $changed = $true
    } elseif ($existing.DistinguishedName -ne $dn -or $existing.Description -ne $marker -or [string]$existing.GroupScope -ne $g.scope) {
        throw 'Refusing an unexpected existing directory group.'
    }
}
$accounts = @($p.users) + @([pscustomobject]@{
    username=$p.bind_username; password=$p.bind_password; path=$p.root_dn;
    email="$($p.bind_username)@$($p.dns_domain)"; region_label='Read-only LDAP'; role='bind'
})
foreach ($u in $accounts) {
    $dn = "CN=$($u.username),$($u.path)"
    $existing = Get-OptionalDirectoryObject -Kind User -Identity $u.username
    if (-not $existing) {
        $newUser = @{
            Name=$u.username; SamAccountName=$u.username;
            UserPrincipalName="$($u.username)@$($p.dns_domain)"; Path=$u.path;
            Enabled=$true; ChangePasswordAtLogon=$false;
            GivenName=$u.region_label; Surname=$u.role; EmailAddress=$u.email;
            Description=$marker
        }
        if ($simpleDemoPasswords -and $u.role -ne 'bind') {
            # Assign the scoped policy before setting a deliberately simple password.
            $newUser.Enabled = $false
            $newDemoAccounts += $u.username
        } else {
            $newUser.AccountPassword = ConvertTo-SecureString $u.password -AsPlainText -Force
        }
        New-ADUser @newUser
        $changed = $true
    } elseif ($existing.DistinguishedName -ne $dn -or $existing.Description -ne $marker) {
        throw 'Refusing an unexpected existing directory account.'
    } elseif (-not $existing.Enabled) {
        if ($simpleDemoPasswords -and $u.role -ne 'bind') {
            $disabledDemoAccounts += $u.username
        } else {
            Enable-ADAccount -Identity $existing
            $changed = $true
        }
    }
}
if ($simpleDemoPasswords) {
    $names = @($p.users | ForEach-Object { $_.username })
    $subjects = @($p.users | ForEach-Object { "CN=$($_.username),$($_.path)" })
    if ($names.Count -ne 12 -or @($names | Select-Object -Unique).Count -ne 12 -or
        $names -contains 'Administrator' -or $names -contains $p.bind_username) {
        throw 'The demo password policy must target exactly the twelve regional identities.'
    }
    $policyName = "$($p.prefix)-DemoPasswordPolicy"
    $policyMarker = "$marker; regional password policy"
    $defaultPolicy = Get-ADDefaultDomainPasswordPolicy
    $preservedProperties = @('MinPasswordLength','PasswordHistoryCount','MinPasswordAge',
        'MaxPasswordAge','LockoutThreshold','LockoutDuration','LockoutObservationWindow',
        'ReversibleEncryptionEnabled')
    $settings = @{ ComplexityEnabled=$false; Precedence=100 }
    foreach ($key in $preservedProperties) { $settings[$key] = $defaultPolicy.$key }
    $policy = Get-OptionalDirectoryObject -Kind PasswordPolicy -Identity $policyName
    if ($policy) {
        if ($policy.Description -ne $policyMarker -or
            @($policy.AppliesTo | Where-Object { $_ -notin $subjects }).Count) {
            throw 'Refusing to modify an unowned or unexpectedly scoped password policy.'
        }
        $drift = @($settings.Keys | Where-Object { $policy.$_ -ne $settings[$_] })
        if ($drift.Count) {
            Set-ADFineGrainedPasswordPolicy -Identity $policyName @settings
            $changed = $true
        }
    } else {
        New-ADFineGrainedPasswordPolicy -Name $policyName -Description $policyMarker @settings
        $changed = $true
    }
    $policy = Get-ADFineGrainedPasswordPolicy -Identity $policyName
    $missing = @($subjects | Where-Object { $_ -notin @($policy.AppliesTo) })
    if ($missing.Count) {
        Add-ADFineGrainedPasswordPolicySubject -Identity $policyName -Subjects $missing
        $changed = $true
    }
    $policy = Get-ADFineGrainedPasswordPolicy -Identity $policyName
    if (@(Compare-Object -ReferenceObject $subjects -DifferenceObject @($policy.AppliesTo)).Count) {
        throw 'The demo password policy does not have exactly the expected subjects.'
    }
    foreach ($u in $p.users) {
        $effective = Get-ADUserResultantPasswordPolicy -Identity $u.username
        if (-not $effective -or $effective.DistinguishedName -ne $policy.DistinguishedName -or $effective.ComplexityEnabled) {
            throw 'The scoped demo policy is not the effective password policy.'
        }
        if ($ResetDemoUserPasswords -or $u.username -in $newDemoAccounts -or $u.username -in $disabledDemoAccounts) {
            $password = ConvertTo-SecureString $u.password -AsPlainText -Force
            Set-ADAccountPassword -Identity $u.username -Reset -NewPassword $password
            $passwordsReset++
            $changed = $true
        }
        if ($u.username -in $newDemoAccounts -or $u.username -in $disabledDemoAccounts) {
            Enable-ADAccount -Identity $u.username
            $changed = $true
        }
    }
    $after = Get-ADDefaultDomainPasswordPolicy
    foreach ($key in (@('ComplexityEnabled') + $preservedProperties)) {
        if ($after.$key -ne $defaultPolicy.$key) { throw 'The domain-wide password policy changed unexpectedly.' }
    }
}
foreach ($g in $p.groups) {
    $desired = @($g.members)
    if ($g.scope -eq 'Global') {
        $desired += @($p.users | Where-Object { $_.group -eq $g.name } | ForEach-Object { $_.username })
    }
    $present = @(Get-ADGroupMember -Identity $g.name | ForEach-Object { $_.SamAccountName })
    foreach ($member in $desired) {
        if ($member -notin $present) {
            Add-ADGroupMember -Identity $g.name -Members $member
            $changed = $true
        }
    }
}
$recursive = @{}
foreach ($g in $p.groups | Where-Object { $_.scope -eq 'DomainLocal' }) {
    $recursive[$g.name] = @(Get-ADGroupMember -Identity $g.name -Recursive | ForEach-Object { $_.SamAccountName })
}
foreach ($u in $p.users) {
    $required = @("$($p.prefix)-DL-$($u.region)-$($u.role)")
    if ($u.region -in @('DK','NO')) { $required += "$($p.prefix)-DL-EU-$($u.role)" }
    foreach ($name in $required) {
        $all = $recursive[$name]
        if ($u.username -notin $all) { throw 'A required nested membership was not established.' }
    }
    foreach ($g in $p.groups | Where-Object { $_.scope -eq 'DomainLocal' -and $_.name -notin $required }) {
        $all = $recursive[$g.name]
        if ($u.username -in $all) { throw 'Unexpected cross-region or cross-role nested membership.' }
    }
}
$Ansible.Changed = $changed
$Ansible.Result = @{
    Users=$p.users.Count; Groups=$p.groups.Count; Regions=4; RolesPerRegion=3;
    NestedMembershipsVerified=$true; ScopedDemoPasswordPolicy=$simpleDemoPasswords;
    DemoPasswordsReset=$passwordsReset; DomainPasswordPolicyUnchanged=$true
}
