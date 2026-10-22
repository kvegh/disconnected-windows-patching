# Five-minute demo: AD-controlled regional access

AD group membership selects each person's region and reader/executor/admin
role. AAP maps that membership to teams and enforces the teams' permissions on
inventories, credentials and job templates. This follows Red Hat's documented
[authenticator team mapping](https://docs.redhat.com/en/documentation/red_hat_ansible_automation_platform/2.7/secure-assembly_gw_mapping)
and [team permission inheritance](https://docs.redhat.com/en/documentation/red_hat_ansible_automation_platform/2.7/get_started-assembly_gs_platform_admin).
The application-specific role definitions and resource grants remain in AAP;
the user's entitlement to those grants comes from their AD groups.

Use the existing demo prefix in place of `<prefix>`. Account names use its
lowercase form. Prepare the test account passwords from the encrypted demo
profile privately before presenting.

## 1. Find the user on Windows

1. Open VNC to the domain controller and sign in with the protected domain
   administrator account.
2. Press **Win+R**, enter **`dsa.msc`**, and press Enter. This opens **Active
   Directory Users and Computers**.
3. Expand the domain, then the **`<prefix>`** folder, then **DK**.
4. Double-click **`<prefix>-dk-executor`**. On **Account**, the short username
   appears under **User logon name (pre-Windows 2000)**.
5. Select **Member Of**. Show **`<prefix>-GG-DK-executor`**. Close the properties
   window without changing anything.

Say: **“AD says this person is a Denmark executor.”**

## 2. Show why that user also gets EU access

1. In the same **DK** folder, double-click **`<prefix>-GG-DK-executor`**.
2. Select **Members** to show the user belongs to it.
3. Select **Member Of** to show its two parent groups:
   **`<prefix>-DL-DK-executor`** and **`<prefix>-DL-EU-executor`**.

Say: **“This AD group grants the Denmark and shared EU entitlements.”**

The user properties show direct membership. EU is inherited through this group
nesting, so it need not appear in the user's own Member Of tab.

## 3. Show the matching AAP rules

As the AAP administrator, open **Access Management → Authentication Methods →
`<prefix> Active Directory` → Mapping**. Show:

- **DK executor membership** → **`<prefix> Denmark executor`** team.
- **EU executor membership** → **`<prefix> EU executor`** team.

Each rule matches the full directory address of the corresponding AD `DL`
group. Under **Access Management → Teams**, show those teams' **Roles**:
their regional inventory/credential Use and job-template Execute grants.

## 4. Demonstrate the result as the AD user

1. Open a private browser window and sign into the test AAP as the Denmark
   executor, using its AD password.
2. Show the **Denmark** and **EU** mock inventories and their four mock job
   templates. **Norway** and **New Zealand** resources must be absent.
3. Launch **`<prefix> Denmark read`** and wait for **Successful**. This is an
   inert local job; it contacts no real regional infrastructure.
4. In the administrator window, show that the user now belongs to the Denmark
   executor and EU executor teams. No individual resource grants were needed.

## 5. Repeat with the comparison accounts

Sign out of the private window before each comparison. The same visibility
boundaries apply to inventories, credentials and job templates.

| AD account pattern | Regions visible | Demonstration |
| --- | --- | --- |
| `<prefix>-no-executor` | Norway and EU | Launch a Norway mock job; Denmark and New Zealand are absent. |
| `<prefix>-nz-executor` | New Zealand only | Launch a New Zealand mock job; EU and both countries are absent. |
| `<prefix>-dk-reader` | Denmark and EU | View resources; job launch and configuration editing are unavailable. |
| `<prefix>-dk-admin` | Denmark and EU | Show resource Edit, then Cancel; other regions remain absent. |

Say: **“AD controls who receives each regional role. AAP automatically maps
those AD groups to teams and enforces the corresponding resource permissions.”**

## Verified behavior

Read-only inspection on 2026-10-22 verified all twelve users' AD login, expected
team memberships and exact regional resource lists. None had individual
controller resource-role grants. The complete live verifier also passed twelve
logins, 48 scoped team grants, 192 access checks and twelve successful mock jobs.
This short script uses the existing memberships; it does not demonstrate live
membership removal or change the directory configuration.

For the full explanation, setup and troubleshooting, see the
[detailed presenter guide](active-directory-demo-guide.md).
