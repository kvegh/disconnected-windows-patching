# Purpose and language choice: [rationale](../docs/supporting-code.md#active-directory-and-aap-verification).
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
$retiredUsersRemoved = 0
$retiredGroupsRemoved = 0
$membershipsRemoved = 0
$additionalMembersPreserved = 0
function Get-OptionalDirectoryObject {
    param([string]$Kind,[string]$Identity)
    try {
        switch ($Kind) {
            'OU' { return Get-ADOrganizationalUnit -Identity $Identity -Properties Description -ErrorAction Stop }
            'Group' { return Get-ADGroup -Identity $Identity -Properties Description,Members,MemberOf -ErrorAction Stop }
            'User' { return Get-ADUser -Identity $Identity -Properties Description,Enabled,MemberOf,PrimaryGroupID -ErrorAction Stop }
            'PasswordPolicy' { return Get-ADFineGrainedPasswordPolicy -Identity $Identity -Properties Description -ErrorAction Stop }
        }
    } catch [Microsoft.ActiveDirectory.Management.ADIdentityNotFoundException] {
        return $null
    }
}
# Validate the complete cohort before removing legacy objects or changing a policy.
$roles = @('reader','executor','admin')
$actors = @('DK','NO','NZ','HU')
$accessByActor = @{ DK=@('DK','EU'); NO=@('NO','EU'); NZ=@('NZ'); HU=@('EU') }
$accessScopes = @('DK','NO','EU','NZ')
$baseDn = ($p.dns_domain.Split('.') | ForEach-Object { "DC=$_" }) -join ','
if ($p.root_dn -ne "OU=$($p.prefix),$baseDn") { throw 'Unexpected regional directory root.' }
$managedPrincipalDns = @{}
foreach ($actor in $actors) {
    foreach ($role in $roles) {
        $name = "$($p.prefix.ToLower())-$($actor.ToLower())-$role"
        $groupName = "$($p.prefix)-GG-$actor-$role"
        $path = "OU=$actor,$($p.root_dn)"
        $matches = @($p.users | Where-Object { $_.username -eq $name })
        if ($matches.Count -ne 1 -or $matches[0].region -ne $actor -or
            $matches[0].role -ne $role -or $matches[0].path -ne $path -or
            $matches[0].group -ne $groupName -or $name.Length -gt 20 -or
            $name -eq 'Administrator' -or $name -eq $p.bind_username) {
            throw 'Unexpected regional identity schema.'
        }
        $managedPrincipalDns[$name] = "CN=$name,$path"
        $managedPrincipalDns[$groupName] = "CN=$groupName,$path"
        $matches = @($p.groups | Where-Object { $_.name -eq $groupName })
        if ($matches.Count -ne 1 -or $matches[0].scope -ne 'Global' -or
            $matches[0].path -ne $path -or $matches[0].region -ne $actor -or
            $matches[0].role -ne $role -or @($matches[0].members).Count) {
            throw 'Unexpected country group schema.'
        }
    }
}
foreach ($access in $accessScopes) {
    foreach ($role in $roles) {
        $name = "$($p.prefix)-DL-$access-$role"
        $path = "OU=$access,$($p.root_dn)"
        $expectedMembers = @($actors | Where-Object { $access -in $accessByActor[$_] } |
            ForEach-Object { "$($p.prefix)-GG-$_-$role" })
        $matches = @($p.groups | Where-Object { $_.name -eq $name })
        if ($matches.Count -ne 1 -or $matches[0].scope -ne 'DomainLocal' -or
            $matches[0].path -ne $path -or $matches[0].region -ne $access -or
            $matches[0].role -ne $role -or
            @(Compare-Object -ReferenceObject $expectedMembers -DifferenceObject @($matches[0].members)).Count) {
            throw 'Unexpected regional access group schema.'
        }
        $managedPrincipalDns[$name] = "CN=$name,$path"
    }
}
if (@($p.users).Count -ne 12 -or @($p.groups).Count -ne 24 -or
    @($p.retired_users).Count -ne 3 -or @($p.retired_groups).Count -ne 3) {
    throw 'Unexpected active or retired directory cohort size.'
}
$retiredUserDns = @()
$retiredUsers = @()
$retiredGroups = @()
foreach ($role in $roles) {
    $path = "OU=EU,$($p.root_dn)"
    $name = "$($p.prefix.ToLower())-eu-$role"
    $groupName = "$($p.prefix)-GG-EU-$role"
    $dn = "CN=$name,$path"
    $groupDn = "CN=$groupName,$path"
    $matches = @($p.retired_users | Where-Object { $_.username -eq $name })
    if ($matches.Count -ne 1 -or $matches[0].path -ne $path -or
        $matches[0].region -ne 'EU' -or $matches[0].role -ne $role -or
        'password' -in @($matches[0].PSObject.Properties.Name)) {
        throw 'Unexpected retired identity metadata.'
    }
    $matches = @($p.retired_groups | Where-Object { $_.name -eq $groupName })
    if ($matches.Count -ne 1 -or $matches[0].path -ne $path -or
        $matches[0].region -ne 'EU' -or $matches[0].role -ne $role -or
        $matches[0].scope -ne 'Global') {
        throw 'Unexpected retired group metadata.'
    }
    $retiredUserDns += $dn
    $existing = Get-OptionalDirectoryObject -Kind User -Identity $name
    if ($existing) {
        if ($existing.DistinguishedName -ne $dn -or $existing.Description -ne $marker -or
            $existing.PrimaryGroupID -ne 513 -or
            @($existing.MemberOf | Where-Object { $_ -ne $groupDn }).Count) {
            throw 'Refusing to retire an unowned or unexpectedly used directory account.'
        }
        $retiredUsers += $existing
    }
    $existing = Get-OptionalDirectoryObject -Kind Group -Identity $groupName
    if ($existing) {
        $parentDn = "CN=$($p.prefix)-DL-EU-$role,$path"
        if ($existing.DistinguishedName -ne $groupDn -or $existing.Description -ne $marker -or
            [string]$existing.GroupScope -ne 'Global' -or [string]$existing.GroupCategory -ne 'Security' -or
            @($existing.Members | Where-Object { $_ -ne $dn }).Count -or
            @($existing.MemberOf | Where-Object { $_ -ne $parentDn }).Count) {
            throw 'Refusing to retire an unowned or unexpectedly used directory group.'
        }
        foreach ($parent in @($existing.MemberOf)) {
            $owner = Get-OptionalDirectoryObject -Kind Group -Identity $parent
            if (-not $owner -or $owner.Description -ne $marker -or
                [string]$owner.GroupScope -ne 'DomainLocal' -or [string]$owner.GroupCategory -ne 'Security') {
                throw 'Refusing to alter an unowned parent of a retired group.'
            }
        }
        $retiredGroups += $existing
    }
}
$subjects = @($p.users | ForEach-Object { "CN=$($_.username),$($_.path)" })
$policyName = "$($p.prefix)-DemoPasswordPolicy"
$policyMarker = "$marker; regional password policy"
$policy = Get-OptionalDirectoryObject -Kind PasswordPolicy -Identity $policyName
if ($policy) {
    $allowedSubjects = $subjects + $retiredUserDns
    if ($policy.Description -ne $policyMarker -or
        @($policy.AppliesTo | Where-Object { $_ -notin $allowedSubjects }).Count) {
        throw 'Refusing to modify an unowned or unexpectedly scoped password policy.'
    }
    # Unlink the obsolete cohort before enforcing the new twelve-user scope.
    $obsoleteSubjects = @($policy.AppliesTo | Where-Object { $_ -in $retiredUserDns })
    if ($obsoleteSubjects.Count) {
        Remove-ADFineGrainedPasswordPolicySubject -Identity $policyName -Subjects $obsoleteSubjects -Confirm:$false
        $changed = $true
    }
}
foreach ($user in $retiredUsers) {
    Remove-ADUser -Identity $user.DistinguishedName -Confirm:$false
    $retiredUsersRemoved++
    $changed = $true
}
foreach ($group in $retiredGroups) {
    Remove-ADGroup -Identity $group.DistinguishedName -Confirm:$false
    $retiredGroupsRemoved++
    $changed = $true
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
    } elseif ($existing.DistinguishedName -ne $dn -or $existing.Description -ne $marker -or
        [string]$existing.GroupScope -ne $g.scope -or [string]$existing.GroupCategory -ne 'Security') {
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
    $members = @(Get-ADGroupMember -Identity $g.name)
    # AD administrators own memberships for identities outside this seeded demo
    # cohort. Reconcile only validated demo principals and preserve all others.
    $managed = @($members | Where-Object { $managedPrincipalDns.ContainsKey([string]$_.SamAccountName) })
    foreach ($member in $managed) {
        if ($member.DistinguishedName -ne $managedPrincipalDns[$member.SamAccountName]) {
            throw 'A managed membership refers to an unexpected directory object.'
        }
    }
    $additionalMembersPreserved += @($members | Where-Object {
        -not $managedPrincipalDns.ContainsKey([string]$_.SamAccountName)
    }).Count
    $unexpected = @($managed | Where-Object { $_.SamAccountName -notin $desired })
    foreach ($member in $unexpected) {
        Remove-ADGroupMember -Identity $g.name -Members $member.DistinguishedName -Confirm:$false
        $membershipsRemoved++
        $changed = $true
    }
    $present = @($members | ForEach-Object { $_.SamAccountName })
    foreach ($member in $desired) {
        if ($member -notin $present) {
            Add-ADGroupMember -Identity $g.name -Members $member
            $changed = $true
        }
    }
    $present = @(Get-ADGroupMember -Identity $g.name |
        Where-Object { $managedPrincipalDns.ContainsKey([string]$_.SamAccountName) } |
        ForEach-Object { $_.SamAccountName })
    if (@(Compare-Object -ReferenceObject $desired -DifferenceObject $present).Count) {
        throw 'A regional group does not have exactly the expected managed direct members.'
    }
}
$recursive = @{}
foreach ($g in $p.groups | Where-Object { $_.scope -eq 'DomainLocal' }) {
    $recursive[$g.name] = @(Get-ADGroupMember -Identity $g.name -Recursive | ForEach-Object { $_.SamAccountName })
}
foreach ($u in $p.users) {
    $required = @($accessByActor[$u.region] | ForEach-Object { "$($p.prefix)-DL-$_-$($u.role)" })
    foreach ($name in $required) {
        $all = $recursive[$name]
        if ($u.username -notin $all) { throw 'A required nested membership was not established.' }
    }
    foreach ($g in $p.groups | Where-Object { $_.scope -eq 'DomainLocal' -and $_.name -notin $required }) {
        $all = $recursive[$g.name]
        if ($u.username -in $all) { throw 'Unexpected cross-region or cross-role nested membership.' }
    }
}
foreach ($user in $p.retired_users) {
    if (Get-OptionalDirectoryObject -Kind User -Identity $user.username) {
        throw 'An obsolete regional identity remains in the directory.'
    }
}
foreach ($group in $p.retired_groups) {
    if (Get-OptionalDirectoryObject -Kind Group -Identity $group.name) {
        throw 'An obsolete regional group remains in the directory.'
    }
}
$Ansible.Changed = $changed
$Ansible.Result = @{
    Users=$p.users.Count; Groups=$p.groups.Count; Regions=4; RolesPerRegion=3;
    NestedMembershipsVerified=$true; ScopedDemoPasswordPolicy=$simpleDemoPasswords;
    DemoPasswordsReset=$passwordsReset; DomainPasswordPolicyUnchanged=$true;
    RetiredUsersRemoved=$retiredUsersRemoved; RetiredGroupsRemoved=$retiredGroupsRemoved;
    ObsoleteMembershipsRemoved=$membershipsRemoved; RetiredIdentitiesVerified=$true
    AdditionalDirectMembersPreserved=$additionalMembersPreserved; ManagedMembershipsVerified=$true
}
