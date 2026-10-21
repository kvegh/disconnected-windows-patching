# Design decisions history

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
