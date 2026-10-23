# Five-minute demo: AD-controlled regional access

AD group membership selects a person's country and reader/executor/admin
role. AAP maps those memberships to teams and enforces their permissions on
inventories, credentials, job templates and Projects. This follows Red Hat's
documented [authenticator team mapping](https://docs.redhat.com/en/documentation/red_hat_ansible_automation_platform/2.7/secure-assembly_gw_mapping)
and [team permission inheritance](https://docs.redhat.com/en/documentation/red_hat_ansible_automation_platform/2.7/get_started-assembly_gs_platform_admin).
AD controls who receives each entitlement; AAP defines what it permits.

Country ownership and EU approval are separate. `DKlocal` and `NOlocal` are
strictly local. `DKEUapproved` and `NOEUapproved` still belong to those countries,
but DK, NO and HU identities can access both. NZ identities see only `NZlocal`.
HU has no resources of its own, and there are no EU-only users. This demonstrates
identity-based regional clearance, not detection of a user's physical location.

The tables use the deployed demo usernames. For group and team placeholders,
replace `<prefix>` with the prefix visible in the deployment. Obtain passwords
privately from the encrypted demo profile before presenting. Rerun the access
verifier after configuration changes before demonstrating the results.

## Complete access matrix

The same cell applies to that set's inventory, credential, Project and both
job templates. **View** = read only; **Run/use** = view and execute/use;
**Admin** = view, execute/use and manage the scoped resources;
**—** = **no access**. Credential
visibility never reveals its stored password. Executor Project access is
view-only. A scoped admin is not an AAP platform or AD domain administrator.

### Denmark

| AD username | DKlocal | NOlocal | DKEUapproved | NOEUapproved | NZlocal |
| --- | --- | --- | --- | --- | --- |
| `geo-dk-reader` | **View** | — | **View** | **View** | — |
| `geo-dk-executor` | **Run/use** | — | **Run/use** | **Run/use** | — |
| `geo-dk-admin` | **Admin** | — | **Admin** | **Admin** | — |

### Norway

| AD username | DKlocal | NOlocal | DKEUapproved | NOEUapproved | NZlocal |
| --- | --- | --- | --- | --- | --- |
| `geo-no-reader` | — | **View** | **View** | **View** | — |
| `geo-no-executor` | — | **Run/use** | **Run/use** | **Run/use** | — |
| `geo-no-admin` | — | **Admin** | **Admin** | **Admin** | — |

### New Zealand

| AD username | DKlocal | NOlocal | DKEUapproved | NOEUapproved | NZlocal |
| --- | --- | --- | --- | --- | --- |
| `geo-nz-reader` | — | — | — | — | **View** |
| `geo-nz-executor` | — | — | — | — | **Run/use** |
| `geo-nz-admin` | — | — | — | — | **Admin** |

### Hungary

| AD username | DKlocal | NOlocal | DKEUapproved | NOEUapproved | NZlocal |
| --- | --- | --- | --- | --- | --- |
| `geo-hu-reader` | — | — | **View** | **View** | — |
| `geo-hu-executor` | — | — | **Run/use** | **Run/use** | — |
| `geo-hu-admin` | — | — | **Admin** | **Admin** | — |

Each set has its own names: for example, `DKlocal Inventory`,
`DKlocal Credential`, Project `DKlocal`, and `DKlocal Read` / `DKlocal Simulate Change`.
All five Projects use the same public demo Git source. Their visibility shows
AAP object permissions, not private Git repository protection.

## 1. Find the user on Windows

1. Open VNC to the domain controller. Sign in with the protected domain-qualified
   administrator account.
2. Press **Win+R**, enter **`dsa.msc`**, and press Enter. This opens **Active
   Directory Users and Computers**.
3. Expand the domain, then the **`<prefix>`** folder, then **DK**.
4. Double-click **`geo-dk-executor`**. On **Account**, the short username
   appears under **User logon name (pre-Windows 2000)**.
5. Select **Member Of**. Show **`<prefix>-GG-DK-executor`**. Close the properties
   window without changing anything.

Say: **“AD says this person is a Denmark executor.”**

## 2. Show the nested access groups

1. In **DK**, open **`<prefix>-GG-DK-executor`**.
2. Select **Members** to show the user belongs to it.
3. Select **Member Of** to show its two parent groups:
   **`<prefix>-DL-DK-executor`** and **`<prefix>-DL-EU-executor`**.
4. In **EU**, open **`<prefix>-DL-EU-executor` → Members**. Show the DK, NO
   and HU global executor groups; NZ is absent.

Say: **“The country group gives local access. The EU access group gives access
to both countries' EU-approved resources, at the same executor level.”**

`GG` is a global group containing people. `DL` is a domain-local access group
used by the AAP mapping. The user's **Member Of** tab shows direct memberships;
follow the global group's parents to see the inherited access. DL names keep
the codes DK/NO/EU/NZ; HU needs only global groups because it receives shared
EU-approved access.

## 3. Show the matching AAP rules

As the AAP administrator, open **Access Management → Authentication Methods →
`<prefix> Active Directory` → Mapping**. Show:

- **DK executor membership** → **`<prefix> DKlocal executor`** team.
- **EU executor membership** → **`<prefix> EUapproved executor`** team.

Each rule matches the corresponding AD DL group's full directory address.
Under **Access Management → Teams**, show those teams' **Roles**: the local
team has five scoped grants; the EU-approved team has ten across the two
approved sets. Executors receive inventory/credential Use, template Execute
and view-only Project access.

## 4. Demonstrate the result as the AD user

1. Open a private browser window and sign into the dedicated test AAP as the
   Denmark executor, using its AD password.
2. Show `DKlocal`, `DKEUapproved` and `NOEUapproved`: three inventories, three
   credentials, three Projects and six mock job templates. `NOlocal` and
   `NZlocal` resources must be absent.
3. Launch **`DKlocal Read`** and wait for **Successful**. Both **Read** and
   **Simulate Change** are inert local jobs; neither changes real infrastructure.
4. In the administrator window, show the user's **Teams**: **DKlocal executor**
   and **EUapproved executor**, with the deployment prefix. Their permissions
   come from team grants, without individual resource grants.

The inventory list may show **Disabled**. That status means no synchronization
source is configured. These static inventories contain an enabled local host
and jobs can use them normally. See the
[AAP inventory status definitions](https://docs.redhat.com/en/documentation/red_hat_ansible_automation_platform/2.7/get_started-assembly_gs_auto_op).

## 5. Show the contrasts

Sign out of the private window between accounts. Use these comparisons to
explain the full matrix above:

| AD username | Sets visible | Demonstration |
| --- | --- | --- |
| `geo-hu-executor` | DKEUapproved, NOEUapproved | Launch an approved mock job. Both strict-local sets and NZlocal are absent. |
| `geo-no-reader` | NOlocal, DKEUapproved, NOEUapproved | Show NOlocal and both approved sets; DKlocal and NZlocal are absent. |
| `geo-nz-admin` | NZlocal only | Show scoped Edit, then Cancel; all DK/NO sets are absent. |
| `geo-dk-reader` | DKlocal, DKEUapproved, NOEUapproved | View resources; launch and editing are unavailable. |
| `geo-dk-admin` | DKlocal, DKEUapproved, NOEUapproved | Show scoped Edit, then Cancel; NOlocal and NZlocal stay absent. |

Say: **“AD controls who receives each access role. AAP maps those groups to
teams and enforces their resource permissions.”**

## Validation and preparation

Live validation of this model passed on 2026-10-23: **12 LDAP logins, 12 teams,
75 scoped grants, 360 primary resource-read/launch checks and 36 successful
mock jobs**, exercising both job-template operations and proving localhost
execution. It also passed 108 admin-only description PATCH checks, 48 exact-list
checks and 24 gateway/controller membership checks. All three retired EU-only
accounts are absent from both services. Use the successful **Verify AD AAP
Access** run with `ad_verify_ldap_logins: true` as the automated evidence.

This script uses the configured memberships. It does not demonstrate live
membership removal or claim an end-to-end VNC/browser rehearsal. A new AD group
alone does not appear in AAP: its mapping and resource grants must be declared
in Ansible. Existing mappings evaluate nested membership when users authenticate.
An enabled new user inside the searched demo OU can use an existing mapped
country group immediately: set a valid AD password, add the membership, then
sign in to AAP. No manual AAP account is needed.

For the full explanation, setup and troubleshooting, see the
[detailed presenter guide](active-directory-demo-guide.md).
