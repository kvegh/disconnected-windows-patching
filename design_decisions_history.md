# Design decisions history

## Align the automation with the deployed AAP runtime and document supporting code

Implementation commit: `09f570f` (version 1.0.3).

Review found three deprecated community IIS modules and a Chocolatey dependency
that requires a newer core than the deployed AAP-supported EE. Replace the IIS
modules with microsoft.iis 1.3.0, preserving the exact management binding through
the replacement module's binding schema. Pin Chocolatey 1.5.3 for the actual
ansible-core 2.16.19 baseline. The owner authorized the required collection
releases; publish and verify their unchanged artifacts in private automation hub
before consuming them in the isolated review environment.

Use microsoft.ad 1.12.1 for native forest creation and its reboot instead of the
custom Install-ADDSForest/shutdown block. Retain explicit Server 2025 functional
levels and the existing wrong-host/domain guards. The protected lab inputs use a
bare builtin Administrator account with matching bootstrap/future domain-admin
passwords. That supports the native action's reboot transition; fresh live
promotion still must verify it before acceptance. The owned identity batch and
readiness checks retain separately documented reasons and review obligations.

Wrap long YAML values without changing their parsed values; format embedded
diagnostics for readability. Host CA trust and Windows Update service changes
use handlers flushed before dependent checks. Keep a narrow documented
no-handler exception for the immediate Chocolatey connection reset. Explicit
empty mappings make argumentless reboot calls unambiguous to parsers.

Add a supporting-code inventory and rationale links in all remaining Python and
PowerShell assets and their Ansible execution points, plus a project TLDR.
Remove the unused legacy upstream remoting-script copy and its reference note;
no playbook referenced them. The separate scoped manual image-preparation
utility remains documented. Add native Ansible orchestration for all six mocked
PowerShell suites on both managed servers with temporary-source cleanup, and
include its Job Template in the existing reproducible template configurator.

Validation: strict production ansible-lint passed 115 files with zero failures
and warnings; all 103 Python tests passed in 25.152 seconds. The new Windows
test playbook passed syntax checking. Gitleaks found no leaks in the working
tree or 180 Git commits. An intermediate YAML formatting error was caught,
corrected and followed by a successful complete Python rerun. No live Windows
or AAP functionality result is claimed by this commit. Those tests, the full
review restart, accepted-deviation decisions and the final scoped end-to-end
test remain required before the dated completion report.

## Review the test implementations and document their language choices

Implementation commit: `bb7abd7` (version 1.0.2).

The owner asked whether the non-Ansible test directory had been checked. Review
covered all thirteen Python and six PowerShell test files, plus the three
JavaScript walkthrough test files. Retain these languages where they exercise
the real Python assets, Windows APIs, Ansible parsers/control flow or JavaScript
models without translating the behavior into another implementation. The test
guide records the rationale, commands, scope and limitations; every test file
links to its applicable rationale. Temporary mock action plugins remain isolated
test scaffolding rather than shipped runtime collections.

Two Python subprocess harnesses previously disabled Ansible deprecation warnings.
Enable them and reject any Ansible deprecation warning in captured output,
including the activation inventory preflight. The Server update-policy test
previously allowed an empty operation list to pass without an assertion; require
both the installation and final search. A negative check confirmed that removing
the update tasks now fails the regression.

Validation: all 103 Python tests passed in 21.264 seconds with ansible-core
2.16.19, and all fourteen JavaScript tests passed, with no skips. The existing
core dependency's Python crypt deprecation warning remains visible for separate
assessment. This patch did not rerun the PowerShell suites on Windows or live AAP
functionality. Those checks and the complete review/end-to-end cycle remain
pending; the offline results do not establish final acceptance.

## Use explicit builtin Windows privilege escalation and file retrieval

Implementation commit: `4fdfd7f` (version 1.0.1).

The first review patch replaces seven short runas privilege-escalation
references with ansible.builtin.runas so strict schema checks resolve the
explicit plugin. Nexus first-start password retrieval uses the Windows-capable
ansible.builtin.slurp module rather than the collection-qualified alias.
The operations, protected inputs, and logging defaults remain the same.

Both builtin interfaces resolve in ansible-core 2.16.19, matching the actual AAP
execution environment. All 103 existing Python tests pass after the changes.
These checks do not establish live AAP functionality; targeted job validation
and the final complete review/end-to-end cycle remain pending.

## Continue the review directly on main from version 1.0.0

Implementation commit: `6aa81e6`.

The owner explicitly requested working directly on main rather than a review
branch and starting at version 1.0.0. The initial review-branch metadata commits
were fast-forwarded into main, VERSION now records 1.0.0, and subsequent cleanup
implementations increment the patch version. This owner instruction supersedes
the earlier branching/prerelease choice for this project.

The version marks the review baseline, not completed acceptance. A dated review
report still requires resolved or accepted findings, functionality confirmation,
and the complete scoped AAP end-to-end test. Pending source edits were preserved
and remain separate from the version metadata commit.

## Start the first tracked major review release

Implementation commit: `11c3a25`.

The owner requested a new major version representing the code review. The
repository had no existing release tags or version file, so the first tracked
major release line is 1.0.0. VERSION records 1.0.0-rc.1 while review and
validation are in progress. A stable release requires resolved findings or
documented accepted deviations, functionality confirmation, a successful final
AAP end-to-end test in the agreed scope, and the dated review report.

The review proceeds on a dedicated branch and covers the current codebase and
its declared environment rather than adding every possible platform or scenario.
The owner authorized recreation of Windows demo VMs only; unrelated VMs and
base images must be preserved. This version marker introduces no runtime change
and does not claim completed review or testing.

## Query live Windows proof from desktops and AAP

Implementation: `291ffd2`; retained-history and patch-comparison fix: `5694fe0`.

The operator requested a clickable report on both managed servers and an AAP
job that queries the same evidence and displays both results together. Use one
read-only PowerShell collector for registry policy, the internal WSUS endpoint,
local Windows Update Agent history, current builds/hotfixes, installed package
and executable versions, and successful retained Chocolatey operations. Expected
values are comparison inputs rather than reported installed state. Distinguish
an April minimum from the exact April cutoff and distinguish current versions
from proof that a baseline preceded an upgrade.

Real Chocolatey operation headers span multiple lines. Preserve their context
when matching successful operations, reject download mentions and failed
installs, and require baseline-before-upgrade chronology. Sanitize diagnostic
fragments rather than exposing arbitrary command lines. Future successful
Ansible application stages also write receipts bound to the actual machine
identity; do not backfill historical receipts on current nodes.

Deploy an administrator-writable script and a public desktop shortcut with
PowerShell `-NoExit`; preserve execution policy without a bypass. Existing
application stages deliver the reporter on future rollouts. Two utility Job
Templates separately install it or query both nodes, keeping the existing
workflow graph unchanged. The private CaC capture includes both definitions.

Both live queries passed, with actual WSUS evidence and four proven application
sequences. The servers already had September builds, so they correctly report
newer-than-April warnings. Label server and controller times separately; one
server's clock was approximately nine hours ahead and was not changed. Desktop
deployment passed eleven native evidence checks per node, normal file execution
and shortcut inspection confirming `-NoExit`. No interactive GUI click, patch
installation, application upgrade or full infrastructure rollout was performed.

## Preserve additional AD members across identity reconciliation

Implementation: `85fcb22`.

The operator wanted newly created AD users to receive existing AAP permissions
through group membership and remain usable when setup is rerun. Review found
that the reconciler rejected group members outside the twelve generated test
identities. Reconcile only known demo principals, validate their expected DNs,
and preserve additional users and nested groups maintained by AD administrators.
Continue verifying the generated identities' country and role boundaries.

The opt-in Windows integration test creates a temporary additional user and
global group, adds direct and nested access, reconciles twice, and verifies both
objects and their memberships survive. The second reconciliation must be
unchanged. Cleanup checks the original object GUIDs, DNs and ownership marker
before removing its own fixtures, including after a failed test. Native testing
passed: both objects and memberships were preserved, the second run made no
changes, the generated-user password exception was not extended, and temporary
objects were removed. Existing passwords and domain password policy were
unchanged. All sixty local AD tests passed. The full AAP regression also passed:
twelve LDAP logins, seventy-five scoped grants, 360 primary access checks,
108 admin-only description PATCH checks, 48 exact resource lists and 24 team
membership checks. All 36 mock jobs completed and executed on localhost.

Update the presenter guides to remove the former extra-member limitation and
provide the Windows new-user steps and one-group/many-permissions explanation.
Use hyphenated presentation labels and retain a current-key lookup for deployed
AAP names and Ansible inputs. The operator excluded a separate access-removal
demonstration and another fresh end-to-end Windows rollout from this work.

## Separate country ownership from EU-approved access and add Hungary

Implementation: `ac5fd54` (directory/profile), `75289ca` (AAP resources,
migration, verifier and presenter guides), `5020a24` (migration label lookup),
`75c8714` (fresh domain Administrator password selection), `d118c25` (bounded
native API retries and guarded resource-stage resume).

The operator clarified that every customer resource belongs to a country.
Replace the generic EU resource pool with DKlocal, NOlocal, DKEUapproved,
NOEUapproved and NZlocal. Each set has a separate Project, inventory, synthetic
credential and two inert jobs. Denmark and Norway can access their own strict
local set and both approved sets; Hungary can access only both approved sets;
New Zealand can access only its own local set. Each country retains distinct
reader, executor and resource-admin identities. EU is a shared access scope,
not another user cohort or resource owner.

Keep twelve country global groups and twelve domain-local access groups, add
Hungary and retire only the three owned EU-only accounts and global groups.
Preserve the shared EU access groups and OU. The native script validates owned
objects, handles obsolete scoped-policy subjects before retirement, reconciles
managed memberships and verifies the entire nested access graph. The encrypted
profile preserves existing credentials and PKI, adds the three new identities
and five independent mock-credential values, and contains password-free
retirement metadata. Fresh profile generation supports protected password
derivation only with the explicitly selected account-scoped demo policy.

Rename existing owned AAP objects while preserving IDs. A read-only inspector
rejects ambiguous or foreign resources and checks remaining references before
retiring the shared source Project. Native Ansible modules apply all changes.
Twelve access teams receive 75 object-scoped grants. Readers can view; executors
can use inventory/credentials and execute fixed jobs with view-only Project
access; scoped admins can manage assigned resources. Explicitly disable surveys
and launch prompts. LDAP maps nested domain-local membership to existing teams.

The independent verifier checks the exact five-set matrix, both job operations,
direct and inherited team membership, visible resource lists, admin-only edits,
retired account absence and actual localhost task statistics. It drains every
launched job even after an access failure. All 60 local AD/model, migration,
resource and verifier tests passed, along with Ansible syntax checks. The
identity-only live run passed: twelve users, twenty-four groups, three retired
users and three retired global groups, expected nesting and unchanged default
domain password policy. A later resource run hit the collection's hard-coded
five-second connection-manager startup deadline after earlier stages passed.
Bound idempotent native API retries and allow a selected resource-stage resume
only after all final owned objects and references pass inspection. This skips
successful Project/team preparation while retaining cleanup, authentication
and full independent verification. The focused resume succeeded, followed by
the complete live verifier: twelve LDAP logins, seventy-five scoped grants,
360 primary access checks, 108 admin-only description PATCH checks, 48 exact
resource-list checks and 24 gateway/controller team-membership checks. All 36
mock jobs completed and executed on localhost. The legacy shared Project and
all three EU-only AAP accounts are absent; fourteen LDAP maps remain enabled.
The detailed guide now consolidates all twelve group-to-team mappings,
resource scopes and exact object-role permissions into explicit tables.
At the operator's explicit request, presenter tables use the twelve actual demo
usernames. Split the access matrix into four short country tables and replace
single-letter permission codes with View, Run/use and Admin to reduce lookup
and scanning effort. Passwords and privileged connection details stay protected.

The operator also requested original-image Administrator passwords on all five
Windows demo VMs. Read-only authentication checks passed for the four standalone
Administrators and domain Administrator; protected values match the existing
image password in CaC. No reset or credential replacement was necessary. Fresh
profile generation now selects that same protected image password rather than
generating a different domain Administrator password.
No VM redeployment or full combined infrastructure workflow was launched.

## Apply approved demo passwords with an account-scoped AD policy

Implementation: `a03b2b6`; matching encrypted rollout profile: `784c0c9`.

The operator requested easier demo account passwords and explicitly approved the
necessary complexity exception. Keep the selected values in the encrypted
profile. A marked fine-grained policy applies directly to exactly the twelve
regional users, preserves the other domain-policy settings and excludes the
built-in administrator and LDAP bind account. Reject unexpected policy ownership
or subjects and verify that the domain-wide policy stays unchanged.

Fresh users are created disabled, assigned the scoped policy, given their
protected password and then enabled. Existing users receive updated passwords
only on an explicitly requested reset. The existing AD template supports an
identity-only run that skips role installation, forest promotion, reboots, DNS
changes and time synchronization while retaining target and AD-readiness guards.

Five group-model checks and actual Ansible rendering of the connection wait
passed. The native identity-only run reset all twelve passwords and verified the
24-group nesting. Independent LDAP reads confirmed the scoped exception on all
twelve users while domain-wide complexity remained enabled. Full live validation
with the updated credentials passed twelve LDAP logins, 48 scoped grants, 192
regional access checks and twelve completed inert jobs. No full rollout was
launched. The source/runtime profile and private encrypted backup are identical.

## Verify the documented AD-controlled entitlement model and shorten the demo

Documentation: `4d04796`; existing identity-verification implementation:
`60a8531`.

The operator wanted access controlled from AD and a brief presentation that
assumes familiarity with AAP but no AD knowledge. Review of the local AAP 2.7
security documentation and current Red Hat mapping/team documentation confirmed
the implemented group-to-team-to-resource-role pattern. AD group membership
selects entitlement; AAP defines and enforces the corresponding resource roles.
Ordinary AD-controlled access requires no custom permission-policy translator.

The five-minute guide gives exact Windows console steps, traces a Denmark
executor's nested EU membership and compares country isolation, shared EU and
New Zealand access. Fresh read-only checks on 2026-10-22 verified all twelve
identities' expected teams and exact visible inventories, credentials and job
templates. No test user had an individual controller resource-role grant.
Documentation links and whitespace checks passed. No directory memberships,
resource grants, templates or encrypted capture definitions changed.

## 2026-10-22 — Document a live Windows upgrade demonstration over VNC

Implementation: `91a6108`. The user requested a presenter guide showing the
actual Windows results: internal WSUS policy and reachability, the installed
patch level, and working Chocolatey applications before and after an upgrade.
Put the guide in `docs/` and link it from the README and remote-access guide.
Use individual job templates so the presenter can inspect each intermediate
state; the full deployment workflow proceeds automatically without these pauses.

Pair each stage with expected results and suggested narration. Distinguish the
OS build from supporting hotfix evidence, applicability checks from installation,
and package revisions from vendor application versions. Include local Git file
staging and 7-Zip archive creation/testing as functional evidence. Explain the
need for a prepared starting state and the actual waits involved in a live run.

Clarify that the existing hypervisor VNC console differs from Windows RDP.
Document laptop prerequisites, display-number conversion, SSH forwarding and
Windows sign-in without publishing private environment connection details.
Read-only inspection confirmed the four existing loopback VNC consoles; temporary
SSH-forwarded connections to both managed consoles returned VNC protocol banners.
Close those test tunnels and preserve all hypervisor and guest settings.

Local links, code fences, source-policy names, application version pins and
April OS build/KB targets were checked against repository sources. The Windows
GUI and presenter commands still require an interactive rehearsal; this work
did not patch, redeploy or install applications on the guests. Preserve the
separate Active Directory documentation edits already in progress.

## Initialize and verify each signed-in service identity

Implementation: `60a8531`.

Inspection found a valid LDAP user with gateway team memberships but no
provisioned controller user. A successful controller identity read was followed
by the expected controller account, teams and inventory access. The verifier
now reads the user's own identity on both services before checking resource
access, matching the browser's service initialization, and rejects a mismatched
or superuser identity on either service. It changes no role assignments or
access policies. All twelve users subsequently had their expected controller
teams and could read their own regional inventory. Fresh-user provisioning and
the complete effective-access matrix are distinct checks. A subsequent complete
live run passed all twelve LDAP logins, 48 scoped grants, 192 regional access
checks and twelve inert job executions. The full combined infrastructure
workflow and live membership revocation remain separate validation.

## Explain the AD-to-AAP relationship through a presenter walkthrough

Documentation: `0b46f96`.

The operator requested a demonstration guide that assumes no AD or LDAP
knowledge and uses VNC access to the Windows servers. The guide follows a
Denmark reader through the directory's direct and nested memberships, the two
AAP team maps, actual login and the resulting resource boundaries. It includes
exact console/browser steps, suggested narration and executor, administrator
and New Zealand contrasts. Setup details are separate from the presentation.
It distinguishes Ansible-created teams and permissions from login-driven
membership, and explicitly qualifies unfinished full-matrix and revocation
validation. Local file links and Markdown fences passed inspection; the VNC
walkthrough has not been rehearsed end to end by this agent.

## Resume LDAP configuration after independently checking existing resources

Implementation: `36a307d`.

Authentication-only recovery verifies the exact twelve teams, all 48 scoped
grants and fixed mock inputs before skipping resource reconciliation. This
allows a focused retry after an interrupted configuration without relaxing the
normal fresh-deployment checks. Native configuration API calls use a
configurable 60-second timeout. Live recovery configured the authenticator and
all fourteen maps successfully.

## Allow a bounded wait for first-login controller access

Implementation: `a823f23`.

The first directory login produced the expected gateway teams before the
controller exposed its permitted resources. The verifier allows a shared
60-second convergence interval per identity for expected access, while
unexpected cross-region access still fails immediately. Subsequent runs found
additional users whose controller access did not converge within that bound;
the change therefore does not establish that the full live matrix passes.
Independent login checks verified all twelve users' expected gateway teams.

## Apply Microsoft's Server update eligibility and report unsupported UI offers

Implementation: `41c251d`; Ansible offer-count rendering: `570a3b7`.

Microsoft documents KB5007651's Windows Security UI package for Windows 11 only.
The Server-2025-guarded update play therefore excludes that exact unsupported
offer from installation while retaining every other software category, optional
update and Defender package. It does not hide Windows Update metadata. The
unsupported offer is reported separately, and the final applicable-update count
must still be zero. The live check passed with zero applicable updates, one
separately reported Windows 11 offer and no required reboot. Eight focused tests
and actual Ansible template rendering passed. The earlier manual UI-installer
diagnostic was removed because it was not a supported Server repair.

## Provision permitted directory users at their first AAP login

Implementation: `be56260`.

The LDAP authenticator enables object creation, which Red Hat documents as
required for first-login creation of organizations, users and teams. Ansible
creates the fixed organization, teams and scoped grants before activation; the
allow map admits only users in the owned regional groups. This permits new AD
identities to receive AAP accounts without granting unscoped resource access.

## Surface access-verification errors without exposing credential input

Implementation: `6e0d225`.

The verifier command's input contains passwords and remains protected. A
following assertion reports only the script's controlled failure reason, so a
live access failure can be diagnosed without making command inputs visible.

## Verify the forest-root controller's time authority

Implementation: `a71d6a4`, `933a391`.

Explicit UTC inspection found a nine-hour offset and a local CMOS time source.
The deployment now keeps Windows Time available, selects the existing configured
NTP peer as the root controller's manual source and verifies synchronization
against the automation runtime before managing identities. It preserves the
peer and correction limits rather than changing global host time or weakening
the time service's controls. Live synchronization passed with an approximately
four-second offset, followed by successful verification of all regional identities.

## Diagnose regional grant and time-service failures without logging passwords

Implementation: `a7a3a4f`.

A development run failed during scoped-grant reconciliation, while a separate
project sync failed to resolve an already-pinned collection. Optional diagnostics
now expose grant and time-service results for focused retries. The native API
module masks password/token fields; identity, credential and LDAP-secret tasks
remain protected, and the normal diagnostic defaults remain disabled.

## Verify graceful shutdown before starting the recovered controller

Implementation: `f9df241`.

The guest did not complete the ACPI reboot event and had no configured QEMU
agent. The recovery alternative requests ACPI shutdown, verifies the domain is
fully shut off, starts it and waits for management connectivity. This live path
passed without destroying or forcibly resetting a running VM. AD readiness and
identity setup then resumed separately.

## Complete promotion restarts across the Windows identity transition

Implementation: `1d61dc2`, `0ed66ba`, `e7081ab`.

Live forest creation succeeded, but the following local-identity command was
rejected before it could request the required restart. New promotions schedule
their restart inside the original command. Recovery can use a controlled guest
restart or an explicitly selected graceful hypervisor path after verifying the
clone's ownership and network attachment. The hypervisor path requires an
observed management-listener stop and return; an accepted request alone does
not establish success. ACPI did not pass that check in the live recovery.
The existing-guest-agent alternative and management-identity diagnostics allow
focused investigation without changing access policy or forcing power off.

## Match the gateway's normalized LDAP group identifiers

Implementation: `0bfe669`.

Login, organization and team triggers now use lowercase full distinguished
names. Red Hat's gateway mapping documentation requires lowercase group
identifiers. This preserves the intended group scope and nested AD membership
while avoiding case-sensitive trigger mismatches.

## Keep the repair option and its runtime result separate

Implementation: `d485251`.

The optional installer result has its own variable so a launch-time Boolean
cannot shadow the result used to decide whether a restart is required. The
repair include also has a distinct task name for clear job diagnostics.

## Repair a diagnosed Security platform registration with the signed cached installer

Implementation: `1f65f00`.

An optional repair verifies Microsoft's signature and the exact offered version
of the cached installer, then runs it with the administrator's loaded profile.
The normal installation and final update scan still follow the repair. This
does not hide an offered update or change security policy. Live validation is
still in progress.

## Preserve nested security-platform inspection evidence

Implementation: `2b51ccd`.

The inspection result now preserves nested file and application metadata and
includes the installed service executable's version. The live inspection
confirmed that the cached installer and installed service had different
versions, so an installer file alone was not treated as proof of installation.

## Inspect security-platform versions after a Windows Update loop

Implementation: `d787853`.

The cumulative OS update installed successfully, but Windows Update repeatedly
offered the same Security platform package after success events. The inspector
now reads the installed service, app, file versions and platform registration
to diagnose that discrepancy. This gathers evidence before changing installed
software or deciding whether an offer represents a missing package.

## Reset management authentication after selecting the administrator password

Implementation: `4c83ea9`.

Promotion selects the protected administrator password before installing roles.
Resetting the WinRM connection at that point ensures subsequent commands use
the current credential rather than relying on an older authenticated session.
The playbook YAML passed validation; live promotion follows the successful
completion of the Microsoft update stage.

## Pin configuration collections and use existing reviewed PAH sources

Implementation: `6e9246f`.

The regional organization initially had no Galaxy credential associations.
Configuration now reuses the target's existing certified, validated and
community PAH associations before syncing its project, rejects unexpected
source layouts and copies no tokens. Its local reconciliation passed with all
four regions and 48 scoped grants. Project collection pins match the locally
validated versions already available in the reviewed shared PAH catalog, so the
encrypted use-case manifest and project requirements stay consistent.

## Inspect update-agent state and provide explicit recovery reboot control

Implementation: `2a8fb67`.

The inspector records agent busy/restart information when readable and matching
Ansible scheduled-task states. Unavailable agent access remains explicit rather
than being reported as idle. Preparation exposes an optional controlled reboot
for recovery after a failed update operation has stopped. It remains disabled
in normal runs. The diagnostic retry later showed active cumulative-update
installation, so its running installer was left to complete.

## Diagnose failed Microsoft update installations with protected defaults

Implementation: `0cc9c1a`.

The focused patch retry returned a Windows Update failure. A separate read-only
inspection now includes System update events, which supplied the installation
error codes without exposing credentials. An explicit diagnostic choice can
show the update module's result for a focused retry; connection and profile
tasks remain protected and normal update logging stays hidden.

## Allow long WinRM operations during servicing and startup

Implementation: `5915d8e`.

The initial update run installed a prerequisite OS update and rebooted, then
stalled while sending WinRM input. An independent scan still found two offered
updates. The dedicated AD guest plays now use a 120-second operation timeout,
using the stock connection option that also sets an appropriate read timeout.
The original stalled job was canceled before a focused preparation retry.

## Independently inspect remaining Microsoft updates

Implementation: `923cf11`.

An optional inspection mode searches every offered software update category
without installing updates or rebooting. Its live run succeeded and found two
additional updates after the prerequisite cumulative update and reboot. This
distinguishes an updated OS build from an empty current Microsoft update scan
while diagnosing the initial job's stalled WinRM polling.

## Inspect servicing progress during long Windows updates

Implementation: `23862c9`.

The operator needs progress evidence while the all-category patch run is active.
The inspector reads free disk space, servicing-process counters, available
download counters and recent CBS log metadata without changing servicing state.
The live inspection passed and confirmed the updated OS build and completed
reboot while the update job's management connection was still being monitored.

## Pass the target CA bundle as a private credential file

Implementation: `1ef21c9`.

The existing complete target trust bundle exceeds the operating system limit for
one environment variable. AAP's native credential file injector supplies it as
a private file while the remaining protected connection fields use environment
injection. The required-target guard checks the file reference before managed
stages proceed. Actual AAP executions passed gateway trust and the independent
48-grant verification with the file-based credential. The encrypted capture's
native CoP rendering preserves all injector expressions for job launch.

## Require a complete protected target credential for managed AD stages

Implementation: `8f4775e`.

Managed stages stop before using fallback validation settings if their target
credential fields are missing. The native Ansible guard was tested with an
absent credential and prevented API access. The workflow configuration also
attaches the appropriate Vault and machine credentials to its two utilities.
Seven regional and workflow tests passed and live reconciliation preserved the
existing Windows graph.

## Publish explicit LDAPS DNS and declare the existing configuration runtime

Implementation: `125617c`.

The initial DHCP reservation did not make the LDAPS hostname resolve from the
operator host. Address configuration now publishes an explicit network DNS
record after conflict checks. Separate requirements document the configuration
collections already present in the supported execution image, while preserving
guest job collection requirements. The README explains that AD membership maps
to AAP teams and AAP role grants remain managed by Ansible.

## Add AD to fresh Windows provisioning and keep its AAP target separate

Implementation: `bfb5110`.

The existing Windows workflow gains an independent eight-stage AD branch with
updates before promotion and successful TLS verification before LDAP activation.
An encrypted credential supplies API and SSH target settings at job launch so
fresh imports can address their receiving platform. The validation profile
remains available for dedicated testing. Live configuration preserved all 21
existing Windows nodes and edges and created the eight new nodes without
launching the workflow. Seven regional-model and workflow tests passed.

## Reconnect across promotion and wait for directory readiness

Implementation: `3091664`.

Preparation and promotion try the protected bootstrap, local administrator and
domain administrator identities so a partial promotion can be rerun safely.
Identity creation waits for AD Web Services and SYSVOL. AD cmdlets use explicit
protected credentials rather than relying on WinRM delegation. Regional model
tests and YAML validation passed before publication; live promotion follows the
successful Microsoft patch stage.

## Verify regional grants and discover the deployed gateway runtime

Implementation: `fb2db7b`.

An independent verifier checks all 48 scoped team grants and the fixed mock
launch inputs before LDAP activation, then supports positive and negative login
tests after activation. Gateway trust discovers the actual non-proxy container
and runs rootless container commands from a readable working directory. This
fixed the initial container inspection failure; the focused trust retry passed.

## Inspect runtime dependencies without installing agent-side software

Implementation: `7a3d176`.

The AD guest inspector records collection versions from the actual execution
environment. This distinguishes available runtime dependencies from the local
agent's Python packages and avoids assuming a missing local package requires a
new installation. The inspection remains read-only and keeps detailed metadata
in authenticated artifacts.

## Install a dedicated LDAPS identity and verify gateway trust

Implementation: `0233c61`.

The dedicated CA issues a hostname-bound LDAPS certificate. Only its public CA
and leaf key reach the DC; issuing keys and target-platform credentials are
excluded from directory task payloads. The gateway trust playbook preserves the
existing bind-mounted bundle and verifies inside the actual container, using
previously verified SSH host keys and normal certificate validation. The target
API connection accepts explicit protected overrides for fresh deployments.

## Reserve the controller address and inspect Windows without changing it

Implementation: `19e35b3`.

The domain controller needs stable addressing across boots and fresh deployment.
The reservation playbook verifies clone ownership, exact NIC topology and
conflicting address assignments before adding one live/persistent DHCP record.
A separate inspection playbook reads servicing and certificate evidence and
parses the identity script. A regression also protects Norway's NO identifier
from YAML 1.1 boolean conversion.

## Scope regional mock resources and LDAP membership maps

Implementation: `ce8d3bf`.

The operator requested inventories, credentials and job templates for each
region. Each region receives independent synthetic credentials and inert jobs
with fixed inputs. Readers receive custom view-only roles; executors receive
use and execute roles; admins receive resource administration. No team receives
an organization-wide administrator grant. LDAP maps use full group DNs, explicit
ordering and revocation. Activation requires verified LDAPS and gateway trust.
The operator clarified that periodic memory reports belong in chat, so the
briefly created AAP schedule and reporting template were removed.

## Define nested regional identities and protect the deployment profile

Implementation: `6fce88b`.

The operator selected a separate Server 2025 DC and reader, executor and admin
identities for Denmark, Norway, EU and New Zealand. Country role groups nest
into the corresponding EU access group without granting access to the other
country. New Zealand remains separate. The model tests these effective grants
and denies role escalation. A one-time Ansible initializer creates and encrypts
the credentials and dedicated LDAPS PKI; existing profiles cannot be silently
regenerated. The Windows-native AD cmdlets use the existing declared runtime.

## Prepare the dedicated domain-controller clone before promotion

Implementation: `5e3cabb`.

The operator requested a separate Server 2025 clone and every currently offered
Microsoft patch. Preparation uses a dedicated single-host inventory, changes
only that guest's update-source policies, includes optional software updates,
handles installer reboots and requires an empty final scan. The existing
disconnected hosts retain their own update-source configuration.

## Measure current swap traffic alongside KSM savings

Implementation: `7583775`.

The operator requested the hypervisor memory and KSM report from an earlier
session and recurring measurements during deployment. The report samples swap
traffic for five seconds because allocated swap alone cannot establish current
memory pressure. It distinguishes gross KSM savings from the kernel's net-profit
counter, reports unavailable counters honestly, and avoids adding KSM savings to
MemAvailable a second time. Detailed snapshots remain in authenticated artifacts.

## Start the dedicated AD integration test platform

Implementation: `8ee617b`.

The operator selected an existing separate test AAP for LDAP and regional RBAC
validation and explicitly authorized starting it after reviewing host memory.
The startup playbook requires an exact protected VM name and address, accepts
only running or shut-off states, and waits for the SSH listener. It changes no
other domains and does not claim that SSH readiness proves AAP readiness.

## 2026-10-21 — Repeat the inside-out cue before every internal action

Implementation: `a470e3c`. The user requested an arrow from the internal
execution node to external AAP before each internal action. Animate and
highlight that outward path, then show job dispatch back to the node before
local execution. Apply the sequence to both internal-only and mixed actions;
connected-only actions keep the internal mesh idle.

Preserve the actual connection model: the first internal action establishes
outbound mesh, and subsequent actions reuse the bidirectional connection.
The repeated outward cue reminds the audience which node initiated the
connection; it does not represent a fresh connection or task polling. Update
phase explanations, node statuses, the accessible diagram description and both
applicable README files to make that distinction clear.

All fourteen checks passed across both editions, covering every internal action,
connected-only actions and cancellation during the repeated cue. Static checks
verified SVG references, arrow direction, motion handling and unchanged original
demo assets. Browser visual QA remains unavailable in the authoring environment.
This change affects the illustration only; no deployed automation was changed.

## 2026-10-21 — Show deployment ownership with four direct arrows

Implementation: `75d9a83`. The user requested a simpler deployment explanation
in the AAP edition, without SSH or virtualization details. Show external AAP
deploying its external repository first. Then show the internal execution node
deploying the internal repository and the two managed Windows VMs. One external
and three internal arrows express that ownership; they remain visible after the
deployment action finishes.

The external server appears after its deployment animation. Establish outbound
mesh and dispatch the internal job before animating the three internal deployment
arrows and revealing those VMs. Later jobs reuse this connection. Reset also
clears a partially illustrated external deployment and cancels the remaining
phases. Update the mock code and explanatory text to match this abstraction.

Preserve the proposed-node disclosure, actual deployed automation and original
demo assets. Both applicable README files describe the revised sequence.
All eight AAP-edition checks passed, including deployment ordering and reset
after the external stage. Static checks verified the four arrow destinations,
absence of low-level provisioning references in this edition, valid SVG and
unchanged original demo assets. Browser visual QA remains unavailable.

## 2026-10-21 — Add a separate AAP orchestration architecture edition

Implementation: `71735be`. The user requested a second, independent edition in
`demo-with-aap/`, with connected AAP and an internal execution node preceding
Windows actions. Preserve the original page and its assets. Publish the new
edition at its own `/demo-with-aap/` URL through the existing Pages workflow;
the original remains at the project Pages root. Separate source copies allow
the two visualizations to evolve independently.

Show AAP scheduling before changes appear. Connected execution handles external
work and initial VM provisioning through the existing virtualization host over
SSH. The connected AAP card groups control and connected execution rather than
implying that a controller-only node runs playbooks. Internal execution is a
proposed Linux node, explicitly labelled as not deployed in this lab.

Follow the AAP 2.7 mesh model: the internal node initiates outbound peering, then
AAP dispatches jobs over the established bidirectional connection. Reuse that
connection for later internal work. Show local Windows management through WinRM.
Keep job delivery distinct from the existing internal-initiated HTTP pull of
export data; update payloads still flow directly between repositories.

Apply illustrated Windows changes after the scheduling/dispatch/execution phases.
Reset cancels unfinished playback so old callbacks cannot repopulate a reset
diagram. Preserve the existing controls, hover examples, source links, enlarged
typography and palette. Production deployment and existing automation are outside
this change. The edition README explains required future job routing, execution
content and review of existing delegated external manifest reads.

All twelve focused checks passed across both editions, including phase order,
mesh reuse and cancellation. Static checks verified SVG structure and references,
request/data directions and unchanged original page assets. Browser visual QA
remains unavailable in the authoring environment.

## 2026-10-21 — Make the internal export pull explicit

Implementation: `4dea4f5`. The user required the export transfer to be clearly
presented as a pull initiated by the internal repository. Source inspection
confirmed that both existing import playbooks already target internal WSUS and
run their HTTP download tasks there. Their transfer behavior needs no change.

Show two directions in the walkthrough: the internal repository sends an HTTP
GET request to the external repository, then the external repository returns the
export data. Animate the request before the returning package. Preserve both
labelled arrows after the action, and restore the earlier management-link view
when stepping backwards. Update the action name, explanation, example play and
server details so the initiator remains clear outside the animation too.

Both README files describe the pull. Syntax checks and the four existing focused
tests passed. Source parsing confirmed three WSUS download tasks and one
application archive download task execute on the internal target; diagram checks
confirmed the request and response point in opposite, correct directions.
Browser visual QA remains unavailable in the authoring environment.

## 2026-10-21 — Brighten the walkthrough and increase text size

Implementation: `6e423d6`. The user found the original muted green palette too
subdued and requested a livelier appearance and text enlarged by 20%. Use clear
blue accents, light cyan network areas and warm amber export details. Retain
green for final verification rather than as the overall visual theme.

Increase text throughout the page, including diagram labels, responsive sizes
and Ansible previews. Make the action button, preview panel and close controls
roomier to accommodate the larger text. Preserve the existing workflow, motion
and interactions. Both README files describe the updated presentation.

All four existing focused checks passed. A comparison against the preceding
stylesheet verified every font-size value at exactly 120% of its original size.
Browser visual QA remains unavailable in the authoring environment.

## 2026-10-21 — Add an interactive, presenter-paced Windows walkthrough

Implementation: `452c2db`. Keep the browser demo in `demo/` and publish its public
assets through GitHub Pages. The user requested three synchronized sections:
Next/Previous controls, a workflow that grows with each action, and a datacenter
architecture that gains servers and features. Rewind restores the corresponding
earlier architecture and versions, making the sequence useful for audience
exploration as well as a presenter-led demonstration.

Use a warm, restrained visual style with quick drop/pop transitions and motion
on the selected data path. Show Microsoft acquisition, external IIS publication,
direct internal transfer and internal client delivery. Represent WSUS metadata
as compressed `.xml.gz` plus separate update files; the application ZIP remains a
different Nexus pipeline. This preserves the implemented transfer distinction
instead of implying one WSUS archive or a physical air gap.

Workflow items offer in-page, explicitly illustrative Ansible examples and links
to the actual playbooks. Server details show the state of the selected step.
This initial version changes visualization state only; it neither launches AAP
jobs nor claims to report current infrastructure. Real execution would require
a separate authenticated integration and result-verification design.

Use dependency-free HTML, CSS, JavaScript and SVG so the page works without
package installation or external assets. The Pages workflow runs syntax and
focused state/source-integrity checks, then uploads only the page and assets.
Keep environment configuration, Vault material, documentation and tests out of
the deployed artifact. Local syntax checks and all four focused tests passed;
browser visual QA was unavailable in the authoring environment.

## 2026-10-21 — Complete the fresh workflow and verify post-application reboot state

Implementation: `95e29f1`; workflow ordering and teardown efficiency: `07e1200`.
Fresh workflow 2303 passed all 21 stages in 3h48m50s. Controller timestamps verify
both imports converged before April selection, disjoint patch jobs ran together,
and both finished before baseline applications and upgrades. The fresh Server
2025 evaluation began unlicensed, activated and returned to its original topology;
that closes the earlier unlicensed-path live-validation gap. Both clients were
created with 4096 MiB and reached their April OS/.NET baselines. Independent
preservation checks passed before and after redeployment for the seven unrelated
VMs and both base images.

Post-run inspection found the standalone assessment template lacked credentials.
Configure it alongside the update template using the existing protected Windows
Machine and Vault references. Its diagnostic error identified a missing NTLM
password; attaching the correct existing credential restored read-only inspection.
Keep detailed diagnostics protected by default.

The later assessment also found a Server 2025 reboot marker after the workflow's
patch stages had reported clean completion. This does not establish which later
operation set the marker. Application stages previously checked installer exit
codes alone; they now also honor explicit reboot flags and Windows CBS/WU markers,
complete a required reboot and wait for both markers to clear before reporting
application success. Five tests exercise seven scenarios through the production
Ansible conditions with remote calls mocked, including clean skips and refusal
of uncleared state. Production lint passed; focused live rerun evidence is recorded
in the end-to-end report. Preserve the original successful workflow results and
record follow-up corrections separately rather than rerunning destructive setup.

Corrected application job 2346 passed with one changed task, the required Server
2025 reboot; Server 2022 skipped it. Final assessment 2349 confirmed both April
builds and no pending reboot. Server 2025 Check job 2351 verified the managed
source, zero applicable updates, no pending licenses and no reboot requirement
after that restart. Both package versions and the sole selected source remained
correct. A separate catalogue audit confirmed that only internal WSUS was capped:
external metadata retained newer undeclined releases through October 2026.

## 2026-10-20 — Run the complete demo in the requested order without redundant disk reads

Implementation: `07e1200`. The operator authorized an end-to-end test that removes
only the four Windows demo clones and their owned disks, preserves other VMs and
base images, then rebuilds and verifies the entire pipeline. Managed servers use
the existing 4096 MiB default. The original workflow installed baseline and current
applications immediately after Chocolatey import and did not include OS patching.

Reproduce the requested sequence with native controller modules: both content
imports must succeed before applying the April 2026 internal ceiling; independent,
disjoint host-limited OS patch jobs run next; both must succeed before baseline
application installation and then upgrade. Keep existing deployment, activation,
repository and synchronization stages. Read back and assert the changed edges and
both convergence settings. Protected inputs select only the existing Windows
workflow and exact host limits. Configuration passed live read-back verification
and an unchanged second application; production lint passed for all three changed
Ansible files.

The first teardown exposed an unrelated cost in the existing file inspection:
`stat` calculated a whole-disk checksum although deletion authorization only uses
regular-file/symlink metadata. Disable checksums and MIME reads for those checks.
Retain the exact allowlist, ownership marker, sole writable disk, shared-reference,
NVRAM and standalone-qcow2 guards. The initial external-server teardown completed;
the queued remaining jobs were canceled to refresh this focused fix before reuse.

## 2026-10-20 — Verify completed April patching and apply memory at safe reboot boundaries

Memory implementation: `7e206ce`; payload-serving repair: `f9883a8`;
completed-state documentation: `a6934ae`. Both managed servers now meet the
internal April OS and .NET baseline with no applicable updates or pending
reboot. Server 2022's initial verified installation took about 39m49s;
its post-maintenance verification took 2m00s. Server 2025's successful job 2258
took 1h38m52s including its failed HTTP retries before the MIME repair.

The operator explicitly authorized complete VM restarts for 4 GiB allocation.
Server 2022 received a clean stop/start after patch completion. For Server 2025,
use one Windows-requested reboot boundary to stop and start QEMU with the
persistent 4 GiB allocation; do not forcibly power off an active install.
The one-time live reboot action ended at startup, restoring the persistent
restart policy. Verify both the running libvirt allocation and Windows memory.
Event record order confirms two patch restarts on Server 2022 and four on
Server 2025; guest clock offsets prevent direct timestamp comparisons.

Activation implementation and review fixes: `88b307b`, `f198c25`, `62d501e`,
`a99cf7a`. Native Ansible controller configuration created the activation
template and inserted it between Windows basics and repository preparation.
Live Check job 2283 passed on all four existing licensed clones after correcting
inventory alias selection and generated libvirt source attributes. These
integration fixes retain the ownership, network and license guards. Normal
job 2286 also passed on all four with zero changes, verifying the licensed skip
path and final topology/license checks. Twenty
regression tests pass. Fresh unlicensed activation remains an explicit
end-to-end validation limit; do not treat existing licensed-clone checks as
proof of that path.

## 2026-10-20 — Compare declared virtual-network identity without generated live metadata

Fix: `a99cf7a`. The next deployed activation Check passed initial configuration,
guest inspection and libvirt reads, then rejected the first clone's topology.
A read-only audit of all four clones found ownership, identity, running state,
MACs and links valid. Only live/persistent interface equality failed: every live
network source added libvirt's generated port UUID and resolved host bridge,
while inactive sources declared only the network name.

Exclude only those generated source fields for virtual-network interfaces.
Keep the network name, portgroup and unknown source attributes in the comparison,
along with interface type, MAC, model and link state. Bridge-type interfaces
retain their actual bridge source identity. Ownership and protected-network
mapping guards remain unchanged. This corrects false mismatches without admitting
a different declared network or losing checks for unexpected source attributes.

Validation: twenty tests pass, including runtime-only source normalization and
refusal of real network, source attribute, bridge, model, MAC, type and link
changes. Replaying the protected read-only capture through the production parser
makes all four expected live/persistent comparisons equal. README was reviewed;
the root task retains its pending README and live verification reconciliation.
No live object was changed by this fix; the controller Check must be repeated
after project synchronization.

## 2026-10-20 — Accept a hypervisor host alias during activation preflight

Fix: `62d501e`. The first deployed Check run stopped at the activation
configuration assertion, before reaching a guest or changing anything. Protected
inventory inspection confirmed a hypervisor host alias exists but no same-named
group exists; approval, credentials and the four unique clone mappings were
present. The assertion wrongly counted group members even though the play's
host pattern correctly matched the host alias.

Validate that the resolved play contains exactly one hypervisor instead of
requiring a particular group structure. Keep approval and protected configuration
guards unchanged. Fifteen tests pass, including real Ansible preflight checks
for a host-only alias, rejection of a group resolving to multiple hosts, and
continued rejection without explicit activation approval. YAML lint passes.
Root will repeat the deployed Check run after project synchronization; source
regression validation alone is not a live deployment result.

## 2026-10-20 — Establish the managed WSUS source before activation connectivity

Fix: `f198c25`. Review identified Microsoft's documented prerequisite for the
Internet-update-location restriction: the client must be configured for an
intranet WSUS source. Fresh clones reach activation before WSUS setup, so the
restriction alone is insufficient evidence of source isolation. Unlicensed
managed clients now fill missing source URLs from the existing encrypted
internal WSUS URL and enable that source before temporary connectivity. Preserve
matching URLs and reject explicitly conflicting URLs before any policy write or
network change. Already-licensed guests retain their read-only skip path.
Repository roles preserve their existing OS update source and use the automatic
updates policy as their automatic-update guard.

Treat an existing default route as connected access only when the protected
permanent adapter mapping also includes the approved connected libvirt network.
An arbitrary route on an isolated adapter does not skip temporary NIC handling.

Validation: twelve Python tests pass, including fresh managed source setup before
exposure, conflict refusal without writes, matching-source preservation, and
connected-network classification, alongside the existing failure and unreachable
cleanup cases. YAML lint and syntax checking in the existing supported execution
environment pass. No live guest or workflow was changed for this review fix.

## 2026-10-20 — Activate each evaluation clone before disconnected deployment continues

Implementation: `88b307b`. The operator requested that both Windows versions
temporarily gain connected access, activate and verify their evaluation license,
then return to their original isolated topology. Activating the base image is
insufficient evidence for a generalized clone, so licensing is checked on every
deployed guest. Keep the existing single parameterized VM creation playbook and
insert a dedicated activation stage after Windows basics establishes permanent
management access, before repository preparation.

Reuse the existing Hypervisor SSH Machine and Vault credentials. Store the
existing Windows login, approved connected network and four exact clone mappings
in a separate encrypted activation record. Build temporary in-memory WinRM
connections rather than duplicating the hypervisor private key or weakening
access controls. Already-licensed guests remain read-only. Repository roles
retain all permanent adapters and may reuse their existing connected route;
isolated guests gain only a live temporary adapter while their original NIC
remains attached.

Block automatic Windows updating before an unlicensed guest receives access.
Activate only the installed evaluation SKU, verify licensed state and remaining
time, then verify the original guest addresses, DNS, routes and live/persistent
libvirt topology after cleanup. Convert WinRM-unreachable results to normal task
failures so Ansible's unconditional cleanup runs. A prearmed hypervisor deadline
also lowers and detaches this operation's temporary MAC if the controller is
canceled or lost. Never change product keys, reset licensing timers, convert
editions or accept license terms.

Validation: eight Python tests cover topology evidence and real Ansible
success/failure/unreachable cleanup control flow with remote operations mocked;
nineteen PowerShell assertions pass on each repository server with all licensing
and network calls mocked. Syntax checks pass in the existing supported execution
environment and for controller configuration; YAML and controller configuration
lint pass. No current guest activation, topology mutation, fresh clone deployment
or live workflow change was performed by this implementation task. Apply the
reproducible controller configuration and validate a controlled fresh deployment
before treating the new stage as operationally verified.

## 2026-10-20 — Serve modern update payloads from existing WSUS content

Fix: `f9883a8`. A managed client stayed at zero bytes while downloading the
April Server 2025 cumulative update. The exact 1,559,987,208-byte MSU existed
on both repository servers with the expected length, but HTTP HEAD requests
returned 404 and server-level IIS configuration lacked the MSU and WIM MIME
entries required by Microsoft for on-premises UUP. File presence alone did
not establish that IIS could serve it.

Add idempotent server-level MIME mappings through Ansible and the existing
WebAdministration PowerShell module. A dedicated setup tag repairs only these
entries through the normal Setup WSUS Job Template; it does not rerun setup
or change update approvals. PowerShell WhatIf validation passed on both servers.
Keep the mapping inherited by WSUS, as Microsoft's deployment guidance requires.

Live application through the focused normal Setup WSUS Job Template succeeded
in 31 seconds. The client's exact payload changed from HTTP 404 to 200 with
its expected length; both repository servers also passed HTTP verification.
The original download retried and completed, then entered Windows servicing.
Delivery Optimization had automatically fallen back to its offline mode;
no additional cloud-mode policy change was needed.

## 2026-10-20 — Give managed Windows VMs 4 GiB of memory

Implementation: `7e206ce`. The operator requested increasing both managed
Windows VMs from 2 GiB to 4 GiB after investigating slow patching. Increase
the deployment default and both existing persistent libvirt memory limits.
Apply existing-VM changes through a clean shutdown and a fresh VM start after
the affected client's update operation has safely finished. A guest reboot
alone keeps the old QEMU allocation. Verify both libvirt's running allocation
and Windows-visible memory. The operator explicitly authorized this full VM
restart. The extra memory does not establish that RAM caused every delay;
Windows servicing and download progress need separate evidence.

After Server 2022 reached the April OS and .NET baseline, its full clean VM
stop/start applied 4 GiB, verified in libvirt and Windows. A separate normal
targeted patch job succeeded in two minutes with no remaining updates and no
pending reboot. Initial installation took approximately 39 minutes 49 seconds;
the shorter run verifies the settled result and is not an installation benchmark.

## 2026-10-20 — Review all Microsoft-required and recommended reboots

Planning update: `5e19299`. The operator requested an explicit TODO to verify
that patching performs every required or recommended reboot for the selected
updates and prerequisites. Review pre-install, within-batch and post-install
requirements against Microsoft guidance on both supported Windows versions,
including native module behavior and the outer rescan/reboot passes.
Record KBs, reboot triggers/counts and final pending-reboot evidence; add focused
regressions for any gaps discovered. This records a future review, not a claim
that every update-specific Microsoft recommendation has already been audited.

## 2026-10-20 — Run independent per-server patch jobs concurrently

Implementation and timing analysis: `476f4e8`. The operator selected separate
Job Template launches for each Windows version instead of changing the
playbook's sequential client strategy. Enable launch-time limits and simultaneous
jobs. Each limit includes one managed host plus the shared internal WSUS group
so read-only preflight facts remain available. Managed-host targets must not
overlap. Existing running jobs retain their original target list and strategy.
The applied Controller settings and a targeted launch were independently verified
through MCP; update/reboot guards and collection pins are unchanged.

The ten latest successful Windows jobs were analyzed using AAP per-host event
timestamps. Three WSUS runs accounted for about 91% of execution time. They
predate the checksum cleanup and combined real synchronization, downloads,
verification and import work. Record measured phases and startup/launch delays
without attributing combined verification/import time to one unmeasured cause.
The guide documents that a repeat import checked unchanged content, and that
current code removes redundant verification and skips unnecessary transfer.
Detailed environment-specific event captures remain outside Git.

## 2026-10-20 — Preserve native action types and observed update identities

Fix: `ce142d4`. Live installation job 2249 reached native win_updates after
successful source, approval and license guards, then stopped before installing
anything. The action plugin compared an integer counter with a templated string;
Windows-side argument validation had converted its separate copy, but could not
repair the controller-side value. Require an integer configuration value and
preserve the direct scalar's type when passing it to the action plugin.

The same result exposed that the pinned native module concatenates a title
string and KB array before filtering. Strict title-only end anchors therefore
excluded the intended updates. Build anchored patterns during the read-only WUA
scan for the observed title and its exact native title-plus-KB representation.
Retain rejection of extra title text and unobserved KBs. This does not broaden
the month ceiling or accept new license terms.

The actual Ansible templating engine reproduced the string conversion and
confirmed the fixed integer argument. Eight Python checks passed, and all
fifty-one PowerShell assertions plus eleven script parses passed on each
repository server, including native filtering representation regressions.

## 2026-10-20 — Keep managed update assessment compatible with WinRM

Fix: `a47bd1c`. After both clients became reachable, live Check job 2238 completed
the managed-source update search but failed creating WUA's SystemInfo COM object.
Microsoft explicitly excludes ISystemInformation from remote interfaces. Read
the same Windows Update and Component Based Servicing reboot registry markers
as the existing installed-state inspector instead. Keep read-only searches and
license guards; no COM permissions or remote security settings are changed.

Eight new mock assertions reproduce restricted COM access, preserve managed
source selection and unaccepted licenses, verify both reboot markers and reject
incomplete searches. All forty-seven PowerShell assertions and eleven script
parses passed on each repository server. The operator then authorized actual
OS installation on both managed endnodes through the existing Job Template.

## 2026-10-20 — Activate the existing evaluation with temporary connectivity

Recovery documentation: `a47bd1c`. The operator explicitly authorized placing
Server 2025 temporarily on the connected network and returning it to isolation.
A live-only additional adapter provided DNS and an Internet route while keeping
the original isolated adapter. Windows automatically activated the installed
evaluation; read-only Ansible WinRM checks reported licensed status and 180 days
remaining. No key replacement, edition conversion or timer reset was needed.

Remove the temporary adapter immediately after verification. Follow-up checks
confirmed the original single adapter in both live and persistent VM definitions,
no default route and valid evaluation status after isolation. Both clients'
internal WSUS policies remained correct. Environment-specific evidence and
network identifiers remain outside Git.

## 2026-10-20 — Prepare evaluation activation before isolation

Documentation: `8f8539f`. The operator reported repeated Server 2025 shutdowns
after installing downloaded media without manual activation. A read-only Ansible
WinRM audit confirmed that both endnodes already use Datacenter Evaluation;
Server 2022 has valid evaluation time, while Server 2025 has expired activation
grace and WLMS explicitly initiates hourly shutdowns. How Server 2022 initially
activated was not established.

Document Microsoft's Internet activation prerequisite separately from WSUS
patching. Activation connectivity and any recovery action need a separate
authorized decision for an isolated guest. No activation, grace reset, licensing
service change or network exception was performed. The same audit confirmed both
endnodes' existing internal WSUS source policies. Full client Check completion
and actual OS installation remain unverified; private guest evidence stays
outside Git.

## 2026-10-20 — Keep policy-only changes on internal WSUS

Implementation: `257f5bf`. When all selected baseline files already exist at the
expected lengths internally, skip external preparation, export and replication.
Only reconcile the internal approval policy. Missing or incomplete payloads still
use the existing verified transfer pipeline. This avoids unnecessary repository
hashing when merely selecting an already available month.

The native Ansible expression engine verified that complete content skips all
three transfer stages and missing content enables them. The first live April
publish, using the earlier implementation, also completed successfully: both OS
and .NET baselines were ready, four bundles were offered, the remaining catalogue
entries were declined, automatic approvals were disabled and no payloads were
missing. This did not install updates on managed endnodes.

## 2026-10-20 — Remove redundant full-payload checksum passes

Implementation: `63f4f1f`. The operator requested removal of excessive checksumming
after repeated reads delayed baseline preparation. Remove payload hashing from
monthly selection, ceiling application and client preflight. Keep WSUS readiness,
file existence/length, update identity, approval and source-policy checks.
This supersedes the earlier SHA1 preflight and Check-mode hashing decisions.

Keep SHA256 integrity checks at the transfer boundary. Export records hashes;
internal preparation verifies existing files once and sends only missing or
mismatched entries to the native verified downloader. Metadata import checks
presence/length without rehashing payloads already verified by that pipeline.
Preserve authenticated manifest anchoring and metadata verification. Active
snapshot files must remain unchanged during transfer, as already documented.

Eight new mock assertions cover hash-free policy checks, missing/truncated files,
same-length corrupt files, transfer queues and disk budgeting. They passed on
both repository servers alongside eighteen selection and thirteen source-policy
assertions; ten PowerShell scripts parsed and seven Python filter tests passed.

## 2026-10-20 — Verify existing files during a real Ansible dry run

Fix: `5062c74`. AAP Check mode incorrectly counted existing WSUS files as missing.
A targeted Windows test reproduced the issue under the actual Ansible Check
context: `Get-FileHash` returned no hash despite valid files and expected SHA1s.
Read file streams through .NET for SHA1 verification instead, retaining file
length and filename-hash checks without changing WhatIf settings. Real Ansible
Check-mode probes passed on both repository servers and changed no WSUS state.

## 2026-10-20 — Keep repeated client preflights practical and stable

Fix: `d490042`. Windows PowerShell 5.1 does not sort hashtable keys using a named
property, so explicitly sort selected identities by key before drift comparisons.
Add a Windows-executed regression assertion for canonical ordering.

Hash the full baseline once at client preflight, then revalidate identities,
approvals, declines, file lengths and WSUS readiness between passes without
rereading the entire baseline each time. Ceiling mutations and transfer stages
still require full content hashes. Allow a bounded readiness wait after approval;
read-only client checks reject content that WSUS has not marked ready.
Windows parsing and all eighteen selection plus thirteen client-policy assertions
passed on both repository servers after these changes.

## 2026-10-20 — Publish subsequent WSUS manifests atomically

Fix: `9d7c082`. Preparing the historical baseline completed its external downloads
and metadata export, then exposed a failure when replacing an existing manifest:
Windows PowerShell bound the null backup argument to an invalid empty path.
Supply a real `current.previous.json` backup path to the atomic replacement API.
Keep the previous manifest recoverable and leave downloaded update content intact.
The first publication still uses a same-directory move.

## 2026-10-20 — Follow managed updates through intermediate reboots

Implementation: `5e401ac`. The operator requested a separate client patching
playbook and Job Template using the currently served WSUS ceiling, with repeated
installation and reboot cycles. Validate the internal policy and every client's
existing source before installation, then process clients serially with bounded
passes. Native Ansible handles update installation, rebooting and reconnection.

Use read-only Windows Update Agent searches through Ansible PowerShell for
applicability checks: the pinned native update module can accept update licenses
even during search. Freeze each pass to the exact observed client titles after
license checks, and rescan before admitting newly applicable prerequisites.
This also accommodates .NET component titles that differ from WSUS bundle titles.
Stop for unaccepted terms rather than accepting them automatically.

Require the official monthly OS build floor, no remaining applicable updates
and no pending reboot before claiming completion. Record before/after evidence
and report already newer clients honestly. Check mode performs no installation
or reboot. Seven filter/completion regression checks and Windows PowerShell
parsing/source-policy tests passed; actual OS installation needs a normal run.
Keep controller configuration reproducible with native Ansible modules and
environment references protected outside plaintext Git.

## 2026-10-20 — Validate the existing offline WSUS role

Fix: `569a0fd`. The first deployed ceiling preview rejected the internal WSUS
because the existing offline setup retains the Microsoft upstream-selection
flag on both autonomous servers. Determine the internal role from the protected
inventory and retain local-content, autonomous-mode and active-sync checks.
Do not change the existing upstream configuration merely to satisfy the new
guard. The policy continues to disable scheduled internal synchronization.
The corrected AAP preview passed without host changes.

## 2026-10-20 — Offer named monthly Windows baselines

Implementation: `eae5cbd`. The operator requested a survey-driven internal WSUS
ceiling and reproducible Ansible automation. Use month names in the survey and
canonical release months internally. Prepare exact OS cumulative releases,
the latest eligible .NET releases and their prerequisites before approving them
internally. Existing export and verified internal pull/import stages are reused.
Budget missing files rather than all files, preserving downloaded content.

Decline unselected catalogue entries server-wide so later updates are not
offered for evaluation, and disable automatic approval paths. Save the verified
policy and reconcile it after later imports because WSUS has no native durable
month-filter setting. Unknown release identities, expired content, ambiguous
bundles, missing files and unaccepted license agreements stop the operation.
Check mode provides a read-only plan; this stage never patches endnodes.

Keep the Job Template, credential associations and named-month survey in an
Ansible controller configuration playbook. Its controller collection dependency
is separate from the Windows runtime dependencies. Add a TODO to review every
non-native-module dependency and whether supported Ansible content can replace
it. Windows execution validated the PowerShell parser and selection regression
checks before deployment; live policy validation is recorded separately.

## 2026-10-20 — Compare WSUS approvals with Satellite content lifecycles

Documentation: `578bedd`. The operator requested a public comparison of patching,
repository management, Content Views and promotion. Add a sourced guide and
README link, using Microsoft's WSUS documentation and Satellite 6.19 guidance.
Distinguish mutable WSUS group approvals from published Content View versions,
and explain why promotion does not install or downgrade host packages. Include
the rolling-view exception, disconnected transfer choices and separate Ansible
stages for content preparation, policy, installation and verification.

Use generic examples without deployed identities or connection details. The
comparison describes conceptual equivalents and does not add OS-installation
or approval automation. The same documentation change records successful
read-only assessment and artifact collection on both supported Windows versions;
no host changes were reported. Sources, relative links and whitespace were
reviewed before publication.

## 2026-10-20 — Make installed patch assessment repeatable

Implementation: `1d05660`. The operator requested reproducible Ansible tasks and
a check of both managed endnodes against April 2026. Add a dedicated read-only
playbook and PowerShell reader, using the installed OS build and revision as
the primary cumulative-update evidence. Compare against Microsoft's published
April monthly builds and retain exact installed hotfix identifiers separately,
because supersedence can remove an older KB from the installed list.

Report April .NET component KB matches without inferring absence of their fixes
when an exact KB is missing. Preserve pending-reboot evidence, distinguish a
newer OS revision from the exact requested baseline, and fail on unsupported
OS builds or inaccessible nodes. Protect detailed results by default and retain
them in authenticated AAP artifacts for before-and-after comparisons. This stage
does not scan, approve, install, reboot or start VMs. Applicability assessment,
older-baseline content selection and internal approval remain separate work.

## 2026-10-20 — Suggest SSH-tunneled VNC for demonstration access

Documentation: `e8d1665`. The operator requested a saved suggestion for reaching
the Windows GUI from a Linux laptop and showing that upgrades worked. Recommend
the existing loopback VNC consoles through the operator's authorized SSH route.
This builds on the VNC deployment choice in `fc8ac60` and reaches the guest
display independently of its isolated network.

The guide resolves console endpoints at demonstration time because ports are
assigned automatically. Read-only hypervisor inspection verified the console
configuration and an active endpoint. The end-to-end laptop connection, SSH
forwarding permission and Desktop Experience installation remain unverified.
The suggestion does not enable RDP or deploy a browser console.

Show OS builds and Windows Update installation events as patch evidence, since
Settings history can omit updates installed through Windows Update Agent APIs.
Show application versions separately. Proposed OS levels X and X+1 use pinned
cumulative updates and expected builds for repeatability; date-based selection
must distinguish metadata revision dates from local arrival dates. The older
baseline and its prerequisites may need explicit download and retention.
These are documented suggestions; client assessment, approval and OS patch
installation automation remain future work.

## 2026-10-06 — Approved Nexus onboarding

Keep EULA acceptance in the Nexus installation playbook. Check the existing
acceptance state and use the supported API only when approval for the pinned
distribution is recorded in the encrypted configuration. This makes repeated
setup safe and avoids silently accepting terms for a future distribution.
Implementation: `4c83c87`. Both repository servers passed live onboarding.

## 2026-10-06 — Native conditional path validation

Validate Windows paths using Ansible's actual conditional parser and full-string
matching. Escaping that worked in a rendered expression failed in task assertions.
Implementation: `89cd9fc` (Nexus paths), `aac60dd` (internal transfer path).
The regression suite checks both forms of deployment input.

## 2026-10-06 — Targeted synchronization diagnostics

Expose a protected-by-default logging survey for external package publication,
so development failures can be diagnosed without changing the normal default.
Implementation: `62feaaf`. External synchronization and archive publication
passed live execution after approved onboarding.

## 2026-10-06 — Windows JSON array handling

Assign the converted JSON package array directly before counting and filtering it.
Wrapping the conversion in an array expression can retain a nested array on
Windows PowerShell and report one expected package instead of four. Keep all
manifest, package checksum and archive-path checks in place and report harmless
schema/count details when validation fails.
Implementation: `95cbd03`. Live import verification passed, including checksum
verification and publication to the two internal release feeds.
Baseline installation and upgrades subsequently passed on both Windows client
versions, including exact installed versions and the sole enabled source check.
Fresh-environment workflow 1252 passed all 17 nodes on 2026-10-07 after guarded
Windows-only teardown and independent preservation verification. This validates
the combined implementation, including `4c83c87`, `aac60dd` and `95cbd03`, in a
complete run rather than only targeted recovery jobs.

## Retrospective — Deployment and isolation

These entries reconstruct significant decisions from session requirements and
the corresponding Git changes; they summarize the history rather than every fix.

- `81595b7`: deploy one VM per launch, with role and Windows-version inputs, so
  AAP can compose four independent deployments and run them in parallel.
- `91e0f4e`: select BIOS or UEFI from verified image partition layouts rather
  than assuming all Windows images boot the same way.
- `4475c21`, `efcab6a`: configure permanent guest networking and fixed deployment
  MAC addresses so management remains predictable across repeated cloning.
- `fc8ac60`: keep environment-specific WSUS settings encrypted; use VNC because
  the hypervisor does not support SPICE.
- `f888b68`, `b9342a2`, `d3d8db5`: restrict teardown to explicitly allowed demo
  VMs and their marked clone disks, and independently verify unrelated domains
  and base images against a captured baseline.

## Retrospective — Modular service and content lifecycle

- `a69418f`: separate Windows basics, WSUS installation and Chocolatey/Nexus
  installation so progress is visible and failed stages can be rerun separately.
- `5160e70`: prepare features and reboots before parallel service setup; separate
  WSUS readiness, synchronization, export and internal import into distinct jobs.
- `d9729d5`: download pinned installers during deployment, verify their checksums,
  and keep independent repository account credentials in Vault.
- `d6149aa`: build self-contained packages for two pinned versions each of 7-Zip
  and Git. Separate external synchronization/export, internal import, baseline
  installation and upgrades; expose distinct immutable release feeds instead of
  making disconnected clients fetch installers from the Internet.

## Retrospective — Network bootstrap reliability

- `a6638d1`: use native Ansible Windows modules for DNS and routing registry
  settings where they can express the desired state.
- `8b5795e`: launch NIC changes through native Task Scheduler so changes can
  complete despite interrupting the WinRM session and without SYSTEM run-as
  process creation on the affected image.
- `57f35d8`: reconnect after temporary WinRM interruption while polling scheduled
  completion, with bounded waits and explicit result validation. This prevents
  a successful network change from being misreported as a permanent failure.
