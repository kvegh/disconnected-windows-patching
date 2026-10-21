# Disconnected Windows Patching

AAP, WSUS, Chocolatey and Nexus demo for Windows patching and application deployment
in a simulated disconnected environment.

## Active Directory extension

The AD extension uses a separate Windows Server 2025 VM and a separate test AAP
for regional identity and permission validation. Implementation is in progress.
`start_active_directory_test_platform.yml` starts only an explicitly approved,
existing test AAP VM and waits for SSH. Supply `ad_start_test_platform_approved`,
`ad_test_vm_name` and `ad_test_aap_address` through protected configuration.
It accepts running or shut-off domains and refuses unexpected states.

`report_hypervisor_memory.yml` reads memory and KSM counters and samples actual
swap-in/out activity for five seconds. Detailed results stay in authenticated
AAP job artifacts. Available RAM already includes KSM's benefit; do not add KSM
savings again. Gross deduplication savings and kernel-reported net savings are
reported separately. Missing kernel counters are reported as unavailable.

`prepare_active_directory_guest.yml` targets exactly one guest in a dedicated
inventory, verifies Server 2025 and disk space, sets its protected hostname and
installs every offered software update category, including optional updates,
directly from Microsoft. It completes update reboots and requires an empty final
scan. This does not change update sources on the disconnected demo's other hosts.
Pass `ad_windows_hostname` and `ad_direct_microsoft_updates_approved` as protected
inputs. Windows Update does not provide third-party application or driver updates
through this module.

`initialize_active_directory_profile.yml` creates the initial identities,
passwords and dedicated LDAPS CA/certificate from protected seed inputs. It
requires the existing Python `cryptography` package and Ansible Vault. It refuses
to replace an existing encrypted profile, and removes its temporary plaintext.
Keep the profile and its issuing private key encrypted and reuse it on reruns.

`deploy_active_directory.yml` installs AD DS/DNS, promotes the selected patched
guest and creates the regional directory. Its Windows-native AD cmdlets run
through `ansible.windows.win_powershell`, using the existing declared runtime.
The encrypted `vars/active_directory_vault.yml` supplies deployed identities.
Denmark and Norway receive their matching role in EU through nested groups;
New Zealand has separate reader/executor/admin access and no EU inheritance.
Existing unrelated directory objects are refused. Four focused model tests check
the effective group graph, including cross-region and privilege-escalation cases.

`configure_aap_ad_regions.yml` creates a separate test organization with four
regional inventories, four independent synthetic credentials, eight inert job
templates and twelve teams. Reader teams get explicit view-only resource roles;
executors get inventory/credential use and job execution; admins get resource
administration. Each grant targets its own region's resources. Mock templates
have fixed inventories, credentials and variables and contact no external hosts.
The optional LDAP stage requires verified LDAPS and gateway trust inputs before
it creates ordered login, organization and nested-group team maps with revocation.
Local authentication remains available. Use the separately pinned configuration
collections; Windows guest jobs retain their existing runtime dependencies.

Hypervisor statistics are reported in the active operator chat every 30 minutes,
including KSM full-scan count. An AAP schedule was briefly created and removed
after the operator clarified that chat reporting was intended; no recurring
memory-report job or template remains deployed.

## Interactive demo

[`demo/`](demo/README.md) contains a presenter-paced browser walkthrough with
Next/Previous controls, a workflow that grows after each action, and a datacenter
architecture that gains servers, services and content. Directional animations
show Microsoft downloads, internal-initiated HTTP pulls over the management
connection, export data returning from external IIS, and internal delivery.
Workflow items expose in-page illustrative Ansible previews and links to the
real playbooks. This is a visual walkthrough; it does not execute AAP jobs or
represent live environment state. Clear blue and cyan accents, amber export
details and text enlarged by 20% improve presentation readability.
The GitHub Actions Pages workflow publishes
only the page and its public assets. See the demo README for local use and checks.

[`demo-with-aap/`](demo-with-aap/README.md) is a separate architecture edition at
the `/demo-with-aap/` Pages URL. It adds connected AAP and a clearly labelled,
proposed Linux execution node in the secure network. Before every internal action,
an inside-out arrow highlights the node-initiated mesh connection, followed by
job dispatch and local execution. Later actions reuse the established mesh; the
repeated arrow is a visual reminder rather than a new connection or task poll. The
deployment arrows show external AAP creating the external repository and internal
execution creating the internal repository and two managed Windows VMs. The
existing demo URL and assets remain independent. Both editions are illustrative;
the new execution node has not been deployed in this lab.

## VM deployment

`01-win-vm-setup.yml` creates one VM per launch on the inventory's `hypervisor`
target. This may be a host alias or a group; activation requires the target to
resolve to exactly one hypervisor.
The hypervisor needs libvirt, `virsh`, `virt-install`, `qemu-img`, the selected
libvirt network, suitable firmware, and osinfo IDs `win2k22` / `win2k25`.
The AAP execution environment needs `ansible-core`; attach a machine credential
for SSH and privilege escalation to the hypervisor.

Base images on the hypervisor:

- `/opt/images/windows-server-2022.qcow2`: 40 GiB virtual capacity.
- `/opt/images/windows-server-2025.qcow2`: 64 GiB virtual capacity.

Boot mode is selected from the verified base image layout: BIOS for the 2022
image (MBR/NTFS), UEFI for the 2025 image (EFI System Partition). This mapping
is specific to these images, not a Windows-version requirement. OVMF firmware
and both Windows osinfo IDs must be available on the hypervisor. If the base images change,
review `windows_boot_modes` in `vars/main.yml`.

Cloning uses `qemu-img convert -S 4k` to create independent sparse qcow2 disks.
There are no backing-file dependencies or disk resizing. Every VM receives
2 vCPUs; `managed` gets 4096 MiB RAM and `wsus` gets 8192 MiB.
An existing VM or destination disk causes the launch to stop rather than overwrite it.

For existing managed VMs with a 2 GiB maximum, change both the persistent
maximum and current memory allocation to 4 GiB with libvirt. Use a clean,
coordinated Windows shutdown or a Windows-requested reboot boundary, confirm the
VM is off, then start it again. Never interrupt active servicing. An ordinary
Windows reboot does not restart QEMU and therefore
does not apply this persistent memory change. Verify the running allocation
and the memory visible inside Windows after startup.

## AAP survey / extra variables

Set the Job Template playbook to `disconnected-windows-patching/01-win-vm-setup.yml`
when using the parent project, or `01-win-vm-setup.yml` with this repository directly.
`assets/deploy-vm-survey.json` contains a survey specification to apply to that
Job Template. Enable the survey; alternatively enable launch-time extra variables.
The demo controller has the deployment template and workflow configured.

Required inputs:

| Variable | Values |
|---|---|
| `vm_role` | `managed`, `wsus` |
| `windows_version` | `2022`, `2025` (string or integer) |
| `vm_name` | Unique VM name; letters, numbers and hyphens, starting with a letter |
| `vm_network` | Primary existing libvirt network; default `windows-isolated` |
| `vm_management_network` | Optional second libvirt network, allowed for `wsus` only; default empty |

For the four-VM demo, launch the template four times (or chain these launches in
an AAP workflow), supplying the appropriate networks:

| VM purpose | Deployment role | Windows version | Primary NIC | Second NIC |
|---|---|---|---|---|
| External repository server | `wsus` | `2022` | `internal` | None |
| Internal repository server | `wsus` | `2022` | `windows-isolated` | `internal` |
| `win2022-managed` | `managed` | `2022` | `windows-isolated` | None |
| `win2025-managed` | `managed` | `2025` | `windows-isolated` | None |

The Server 2022 WSUS choice is intended to serve both client versions. Select
Windows Server 2025 products during WSUS configuration and validate actual
synchronization and client scanning before the demo.

Example CLI launch:

```bash
ansible-playbook -i inventory.ini 01-win-vm-setup.yml \
  -e vm_role=managed -e windows_version=2022 \
  -e vm_name=win2022-managed -e vm_network=windows-isolated
```

The initial hardware uses Q35, SATA storage and an emulated e1000e NIC to avoid
requiring VirtIO drivers at first boot. Validate these devices with the actual
images. A local VNC console supports initial Windows setup. The role input
selects sizing; it does not install WSUS or configure Windows credentials,
hostnames, WinRM, or SSH. The base images must already contain working credentials
and WinRM; guest configuration is handled by the separate configuration playbooks.

Both versions use this same parameterized creation playbook. After Windows
basics establishes permanent management access, `activate_windows_evaluations.yml`
checks each clone's license. An unlicensed evaluation retains its isolated
primary adapter, temporarily gains a connected adapter, activates its installed
evaluation license, verifies licensed state, and loses the temporary adapter
again. It verifies the original guest routes, addresses, DNS and live/persistent
libvirt NIC topology before deployment continues. Already-licensed clones skip
activation and connectivity changes; repository servers keep their permanent NICs.

Microsoft requires Internet activation within ten days even for the 180-day
evaluation. Activating a base image does not guarantee activation after cloning
and generalization. The new stage uses the Hypervisor SSH and Vault credentials;
Windows login and topology inputs are in `vars/windows_activation_vault.yml`.
Automatic Windows updates are disabled before an unlicensed clone gains access;
managed clones are first assigned their protected internal WSUS source, with
conflicting existing sources rejected before connectivity changes.
Ansible cleans up on failure, and a hypervisor deadline removes the temporary
adapter if the controller is lost. See
[per-clone activation and workflow configuration](docs/windows-evaluation-activation.md).

The activation template and workflow handoff are deployed. Live Check job 2283
and normal job 2286 passed on all four existing, already-licensed clones without
host changes, verifying the normal licensed skip path as well as inspection.
Twenty regression tests cover the activation guards and cleanup paths. Fresh
workflow 2303 subsequently verified the unlicensed path: Server 2025 activated
and returned to its original topology before repository preparation.

`wait_for_dhcp` defaults to `false` because initial setup or the network layout
may prevent immediate DHCP. Enable it to wait up to five minutes and discover
IPv4 by MAC on a libvirt network providing DHCP. A lease does not establish that
Windows is ready for AAP management. Configure management connectivity and
isolation separately; this playbook does not create networks or firewall rules.

## Layout and validation

Decision explanations and implementation commit IDs are recorded in
[design_decisions_history.md](design_decisions_history.md). Pending reviews,
including Microsoft-required and recommended reboots, are tracked in
[TODO.md](TODO.md). Nexus onboarding is
part of `setup_chocolatey.yml`: existing acceptance is retained, and initial EULA
acceptance requires encrypted approval for the pinned distribution. External
package synchronization, export, internal import, baseline installation and
upgrades have passed live execution on both Windows endnodes. Baseline packages
were 7-Zip `26.3.0` and Git `2.55.0.5`; verified upgrades were 7-Zip `26.4.0`
and Git `2.56.0.2`, using only the selected internal feed.
Application completion honors installer reboot codes/flags and Windows CBS/WU
reboot markers, and verifies those markers clear before reporting success.
On 2026-10-07, workflow 1252 passed all 17 nodes after guarded teardown and
verification of the four Windows clones. This validates the complete fresh
environment deployment and both content pipelines, including application
upgrades. Windows update installation on the endnodes is a separate step.

The new [fresh end-to-end test](docs/end-to-end-test-2026-10-20.md) runs the
expanded 21-stage workflow through April OS patching before application baseline
installation and upgrade. Workflow 2303 passed all 21 stages in 3h48m50s,
finishing on 2026-10-21 at 01:01 UTC. Preservation checks passed before and after
redeployment: seven unrelated VM definitions/states and both base images were
unchanged. Both managed guests were created with 4096 MiB and verified from Windows.
Follow-up application job 2346 finished a later Server 2025 reboot requirement;
final assessment 2349 confirmed both April builds with no pending reboot, and
Check job 2351 found zero applicable updates on Server 2025 after that reboot.
The test report records these corrections separately from the original workflow.

On 2026-10-20, live publication verified the internal April 2026 ceiling with
both OS and .NET baselines ready. A client Check run using the lighter validation
passed internal policy and Server 2022 source checks, then stopped because the
Server 2025 endnode was unreachable. A subsequent read-only WinRM audit reached
both endnodes and confirmed their existing internal WSUS source policies. It
identified expired evaluation activation grace as the Server 2025 shutdown cause.
After authorized temporary connectivity, its existing evaluation activated
automatically with 180 days remaining. The temporary adapter was removed,
isolation was restored and both clients retained their internal WSUS policies.
The subsequent client Check run exposed a remote-incompatible Windows Update
reboot-status API call. Searches now read the same Windows Update/CBS registry
markers as the existing client inspection, preserving remote security controls.
The install pass preserves integer retry arguments and exact-title matching
through the pinned native module's title-plus-KB filtering representation.
Normal installation has now upgraded Server 2022 to April build `20348.5020`
and Server 2025 to `26100.32690`, including their applicable .NET updates.
Both passed the final internal-source, baseline, empty-update and pending-reboot
guards. Server 2022's initial verified result took about 39m49s; its settled
verification run took 2m00s. Server 2025 took 1h38m52s including the IIS download
retry/recovery period. System event order confirms two patch restarts for Server
2022 and four for Server 2025. Both now have 4 GiB allocated, confirmed in
libvirt and Windows after clean full VM restarts at safe servicing boundaries.
See the [live verification details](docs/windows-os-patching.md#references-and-verification).

- `01-win-vm-setup.yml`: VM deployment playbook.
- `activate_windows_evaluations.yml`: verify or activate each clone and restore its exact original topology.
- `configure_windows_activation_template.yml`: add the activation template between Windows basics and repository preparation.
- `configure_windows_end_to_end_workflow.yml`: join both imports, enforce April 2026, patch hosts independently, then install baseline applications and upgrade them.
- `configure_windows_server_basics.yml`: static networking, DNS, hostnames and reboots.
- `setup_wsus.yml`: WSUS installation, initialization and client update policies.
- `setup_chocolatey.yml`: Nexus services, hosted feeds, and Chocolatey clients.
- `synchronize_external_chocolatey_repo.yml`: four pinned offline packages (two 7-Zip and two Git versions).
- `export_external_chocolatey_repo.yml`: verified ZIP export served through external Nexus HTTP.
- `replicate_and_import_chocolatey.yml`: internal-server pull/import into baseline and current feeds.
- `deploy_baseline_applications.yml`: install older pinned versions on endnodes.
- `upgrade_applications.yml`: switch feeds and upgrade to newer pinned versions.
- `prepare_repository_servers.yml`: feature/MSI installation and reboot barrier before parallel setup.
- `check_wsus_prerequisites.yml`: read-only external WSUS readiness and PowerShell syntax checks.
- `assess_windows_patch_level.yml`: read-only installed OS build and hotfix evidence on managed endnodes.
- `set_internal_wsus_patch_month.yml`: prepare a named monthly baseline and enforce its internal WSUS ceiling.
- `configure_wsus_patch_ceiling_template.yml`: reproduce the ceiling Job Template and month-name survey with Ansible.
- `update_managed_windows.yml`: install the current internal WSUS baseline with guarded install, reboot and rescan passes.
- `configure_windows_patching_template.yml`: reproduce update and read-only assessment Job Templates with their existing Windows credentials.
- `sync_external_wsus.yml`: Microsoft metadata synchronization and selected file downloads.
- `export_external_wsus.yml`: WSUS metadata export and management-only IIS publication.
- `replicate_and_import.yml`: direct external-to-internal HTTP transfer and offline WSUS import.
- `docs/wsus-data-flow.md`: inputs, workflow, integrity checks, module use and live validation status.
- [WSUS vs Satellite](docs/wsus-vs-satellite.md): patching, repository management, Content Views and staged content promotion.
- [Monthly Windows patching](docs/windows-os-patching.md): named-month selection, content preparation, approval policy and repeatable Job Template configuration.

For concurrent OS patching, launch the Update Managed Windows Job Template once
per managed server. Include that server and `wsus_internal` in each launch limit
so the shared read-only preflight runs, for example `HOST_A:wsus_internal` and
`HOST_B:wsus_internal`. Simultaneous launches are enabled; the playbook retains
sequential client processing within a launch. Keep managed-host targets disjoint
and the internal WSUS ceiling stable until both jobs finish. Measured historical
runtimes are recorded in the patching guide.

- `collections/requirements.yml`: pinned Ansible collection dependencies.
- `docs/application-deployment.md`: application architecture, inputs, and remaining work.
- `windows-remote-access.md`: suggested Linux-laptop console access over SSH/VNC, demo evidence, and proposed staged OS patch levels.
- `vars/main.yml`: base images and sizing configuration.
- `assets/deploy-vm-survey.json`: AAP survey specification.

The internal WSUS role comes from the protected inventory. Its autonomous,
locally stored content and manual-import policy are enforced independently of
the upstream-selection flag retained by the existing offline setup.
WSUS export atomically publishes `current.json` and retains the previous pointer
as `current.previous.json` when replacing an existing manifest.
Selected update identities use canonical ordering on Windows PowerShell 5.1 so
policy drift comparisons remain stable between reads.
Monthly ceiling selection and client patching use WSUS readiness, policy,
identities, file existence and lengths without hashing update payloads.
Integrity checks stay at the transfer boundary: export records SHA256 hashes;
internal preparation checks existing files once and only missing/mismatched files
go through the verified downloader. Metadata import does not rehash payloads.
When the internal baseline files are already present, the monthly cutoff job
skips external preparation, export and transfer and only reconciles internal policy.

Install `ansible-core` in the execution environment. Validate without deployment:

```bash
ansible-playbook -i 'hypervisor,' 01-win-vm-setup.yml --syntax-check
```

Use standard Ansible YAML formatting (two-space indentation). VM creation, Windows
basics, WSUS configuration, the Nexus/Chocolatey pipeline and managed OS patching
have been exercised against the demo guests. Client OS update installation uses
its separate normal Job Template; code tests and Check mode do not prove installation.

## Network prerequisites

Create `windows-isolated` separately with an isolated subnet, no forwarding
or NAT, and DHCP. Keep actual subnet values in AAP inventory or Vault. This playbook verifies that selected networks exist and are
active; it never creates or changes networks. Use `vm_network=internal` for external WSUS, and
`vm_management_network=internal` for internal WSUS. The existing `internal`
network is the existing management LAN. DHCP discovery uses the primary NIC.

The second NIC alone does not enforce isolation. Internal WSUS still needs
guest configuration with no default gateway, routing disabled, and firewall
rules allowing the intended AAP and external WSUS traffic. Windows NIC addresses
and these rules are separate from this VM deployment playbook.

## Modular Windows configuration

Run these job templates independently or through the deployment workflow:

| Stage | Playbook | AAP job template |
| --- | --- | --- |
| Windows basics | `configure_windows_server_basics.yml` | Disconnected Windows Patching - Configure Windows Server Basics |
| Evaluation activation and topology verification | `activate_windows_evaluations.yml` | Disconnected Windows Patching - Activate Windows Evaluations |
| Preparation and reboots | `prepare_repository_servers.yml` | Disconnected Windows Patching - Prepare Repository Servers |
| WSUS | `setup_wsus.yml` | Disconnected Windows Patching - Setup WSUS |
| Application repositories and clients | `setup_chocolatey.yml` | Disconnected Windows Patching - Setup Chocolatey |

The existing **Deploy Windows + WSUS environment** workflow creates four VMs in
parallel and waits for all four to succeed before Windows basics. Evaluation
activation and topology verification then run before the preparation stage
completes feature/MSI installation and reboots. WSUS setup and Chocolatey/Nexus
setup then run in parallel. The Chocolatey branch proceeds through external package
synchronization, HTTP export and internal import.
The WSUS branch continues through prerequisite checks,
synchronization, export, and replication/import. Both imports converge before the
April 2026 internal ceiling. Two disjoint host-limited patch jobs run in parallel;
both must succeed before baseline application installation and the subsequent
upgrade. Each transition requires success. Reproduce this handoff with
`configure_windows_end_to_end_workflow.yml`, supplying protected workflow/template
references and two exact `HOST:wsus_internal` limits. Managed clones default to
4096 MiB RAM; deployment and guest inspection verify the actual allocation.
See [WSUS data flow](docs/wsus-data-flow.md) for the full graph and inputs.
Use an individual configuration template to reconfigure existing VMs; rerunning
the deployment workflow attempts creation and its existing-VM guard will stop it.

Guest configuration templates use WinRM and a Windows Machine credential.
The activation template instead combines Hypervisor SSH and Vault credentials,
with existing encrypted Windows credentials for its in-memory WinRM connections.
Their execution environment needs `pywinrm` and the pinned Ansible collections.
Required disjoint inventory groups are `wsus_external`, `wsus_internal`, and
`windows_managed`. Keep environment assignments protected and out of plaintext Git.

### Assess installed Windows patch levels

Run `assess_windows_patch_level.yml` against `windows_managed` before and after
OS patching. The **Disconnected Windows Patching - Assess Windows Patch Level**
Job Template uses this playbook; select the existing Windows Machine credential
at launch. It reads the OS build, installed hotfix identifiers and Windows Update
and component-servicing pending-reboot indicators. It does not perform an update
scan, approve updates, install packages or reboot.

The default comparison is the April 2026 monthly OS cumulative update:

| OS | KB | Expected OS build |
| --- | --- | --- |
| Server 2022 | KB5082142 | 20348.5020 |
| Server 2025 | KB5082063 | 26100.32690 |

Live read-only AAP runs exercised the assessment and artifact collection on both
Windows versions, with no host changes. This validates the assessment, not OS
patch installation.

Apply `configure_windows_patching_template.yml` with the existing Windows Machine
and Vault credential references to configure both the update and standalone
assessment templates. An assessment template without its Windows credential
cannot authenticate even when WinRM is healthy. Diagnostic logging remains
protected by default.

Sources: [Server 2022 release](https://support.microsoft.com/en-us/servicing/os/windows-server/2026/04/april-14-2026-kb5082142-os-build-20348-5020)
and [Server 2025 release](https://support.microsoft.com/en-us/servicing/os/windows-server/2026/04/april-14-2026-kb5082063-os-build-26100-32690).
Override `windows_patch_baseline_name` and `windows_patch_baselines` together
through launch-time variables for another explicitly pinned baseline.

`below`, `at` and `above` compare the installed revision within the configured
OS build. An exact KB may disappear from the installed-hotfix list after
supersedence, so use the build comparison for the OS patch level. The report
also lists exact April .NET KB matches: Server 2022 installs the applicable
component KB5082427 or KB5082425 under the WSUS bundle KB5084071; Server 2025
uses KB5082417. Missing exact .NET identifiers do not establish whether a newer
.NET update superseded them. This assessment does not certify an entire
date-stamped security baseline or include later April out-of-band releases.

Detailed evidence is protected by `windows_patch_no_log: true` by default and
saved under `windows_patch_assessments` in authenticated AAP job artifacts. A
short summary shows the build comparison. Store exported artifacts outside Git.
A powered-off or unreachable node fails the assessment rather than reporting
it as compliant. No VM is started by this playbook.

For local use with an existing protected inventory and credential configuration:

```bash
ansible-playbook -i YOUR_PROTECTED_INVENTORY assess_windows_patch_level.yml
```

`configure_windows_server_basics.yml` owns permanent NIC settings, DNS, forwarding,
hostnames and their reboots. It validates MAC assignments before changes, uses an
one-shot Windows scheduled task, and reconnects at each host's permanent address.
Supply `windows_network_interfaces`, `windows_connection_address` and optional
`windows_hostname` through protected per-host inventory variables. This playbook
has no WSUS URL dependency and performs no WSUS or Chocolatey installation.

`setup_wsus.yml` installs WSUS with Windows Internal Database on the two repository
servers, initializes local content storage, configures manual synchronization and
internal client firewall access, and configures Windows Update policies on managed
servers. It verifies the internal client web service from both managed servers.
It does not change Windows networking or hostnames. `wsus_internal_url` and
`wsus_client_sources` are loaded from `vars/wsus_environment_vault.yml`; attach the
matching Vault credential to this template. Optional `wsus_content_path` defaults
to `C:\WSUS`. Existing initialized content locations are protected against moves.

Setup also adds Microsoft's required server-level IIS MIME mappings for UUP:
`.msu` as `application/octet-stream` and `.wim` as `application/x-ms-wim`.
Without these mappings, an update file can exist on disk while IIS returns
HTTP 404 and newer Windows clients remain at zero download progress.
Run the Setup WSUS Job Template with the `wsus_uup_mime` job tag to repair
only these inherited mappings on existing repository servers, without rerunning
installation, synchronization or client policy tasks. See
[Microsoft's WSUS deployment requirements](https://learn.microsoft.com/en-us/windows-server/administration/windows-server-update-services/plan/plan-your-wsus-deployment#manually-add-the-required-mime-types-for-uup).

Both WSUS servers are standalone and synchronization is manual. Managed guests
use internal WSUS with Internet update locations blocked and automatic updating
disabled, leaving patch installation to AAP. Product selection, synchronization, download-only
approvals, metadata export/import and update binary transfer are implemented in
the separate [WSUS population playbooks](docs/wsus-data-flow.md). Internal client
approvals and patch installation use the separate monthly-ceiling and managed-update
Job Templates documented above.

Validate without executing against Windows:

```bash
ansible-playbook -i inventory.ini configure_windows_server_basics.yml --syntax-check
ansible-playbook -i inventory.ini setup_wsus.yml --syntax-check --vault-password-file /path/to/vault-password
ansible-playbook -i inventory.ini setup_chocolatey.yml --syntax-check --vault-password-file /path/to/vault-password
```

## Application repositories and Chocolatey

The expanded demo co-hosts Nexus Repository Community Edition on external and
internal WSUS. External Nexus provides a staging feed; internal Nexus provides a
baseline and current feeds containing older and newer offline-ready application packages. Managed Windows
servers use Chocolatey CLI, invoked by AAP over WinRM, to install selected versions.

`setup_chocolatey.yml` deploys both Nexus Windows services and hosted feeds,
and bootstraps the Chocolatey clients from an offline MSI. See
[application deployment](docs/application-deployment.md) for installer inputs,
credentials, resource requirements, package promotion, and pending live validation.

The clients have only an isolated NIC. AAP needs an execution node on that
network or a restricted management route. Internal WSUS's second NIC does not
provide a WinRM jump host automatically. The demo execution-node connectivity has been verified over WinRM; this playbook does not change network isolation or VM sizing.

## Implementation status

Fresh workflow 2303 passed VM creation, networking, evaluation activation,
repository preparation, WSUS and Nexus/Chocolatey setup, both external population
pipelines and internal imports, the April ceiling, both managed OS patch jobs,
baseline applications and upgrades. Installers download automatically with pinned
checksums; administrator and package-reader credentials remain in the encrypted vault.

AAP-controlled application synchronization, export, internal import, baseline
installation and upgrade are implemented as separate playbooks/job templates.
The targeted content is 7-Zip and Git with two pinned versions each. Native modules
handle normal configuration and installation; small helpers build deterministic
packages/exports, inspect archive integrity and upload binary packages on Windows.
The complete fresh run verified the application versions and sole internal source
on both endnodes. Networking uses the scheduled-task/reconnection correction
for the earlier SYSTEM process-token launch failure. See
[application deployment](docs/application-deployment.md) and the
[end-to-end evidence](docs/end-to-end-test-2026-10-20.md).

AAP execution-node access to the isolated endnodes is required. Installer downloads
and vaulted application credentials are configured for deployment. See the detailed
[implementation status and remaining work](docs/application-deployment.md#implementation-status-and-remaining-work).

### Permanent Windows NIC configuration

Provide `windows_network_interfaces` and `windows_connection_address` as protected
per-host inventory variables. Each interface entry requires `mac`, `name`,
`ipv4_address`, `prefix_length`, `gateway` (empty string for none), and `dns_servers`
(an empty list for none). Supply every demo NIC, including both internal WSUS NICs.
The connection address must match one configured NIC. Use actual deployed MACs;
fixed MAC inputs are supported by the VM deployment playbook.

Initially, inventory `ansible_host` must be the discovered DHCP address. Do not
supply `ansible_host` through launch extra variables: they would override the
playbook's switch to the permanent address. The bootstrap script validates all
MAC matches before applying changes, runs through Task Scheduler independently of the connection
interruption, and verifies its exit code and JSON result after reconnecting. It owns the configured
NICs' IPv4 addresses and replaces other IPv4 assignments on those NICs.

Only external WSUS may have an IPv4 gateway or DNS servers. Internal WSUS has
forwarding disabled as well. The script changes neither WinRM security settings
nor PowerShell execution policy. Existing WinRM firewall/certificate configuration
must permit connections at the permanent address from the AAP execution node.

`ansible_host` is updated for the current job, not persisted to the AAP database.
Update the AAP host's inventory variables to the permanent address after a
successful bootstrap, before future jobs. The vaulted umbrella network record is
reference data and is not automatically loaded or converted into these host vars.
Windows network switching was verified with the modular template on Windows
Server 2025 after changing its launcher to Task Scheduler. Console access is
needed to recover a misconfigured NIC.

### Repository server identities

The external and internal repository servers each host both WSUS and Nexus for
Chocolatey packages. Their planned VM names and Windows hostnames are recorded in
the umbrella project's vaulted network inventory. Use those values for `vm_name`
at deployment and `windows_hostname` during guest configuration.

The existing `wsus` deployment role and `wsus_external` / `wsus_internal` inventory
groups remain compatible with the playbooks; they identify WSUS-capable repository
servers, not dedicated WSUS-only guests. AAP workflow launch inputs use the
repository-server identities recorded in the vaulted inventory.

## Destroy a Windows demo clone

`destroy-win-vms.yml` tears down one VM per launch. Supply `vm_name` and the exact
`windows_demo_vm_names` allowlist through AAP or protected variables. Wildcards
are not accepted as authorization. Both repository servers and managed Windows
VMs belong in that list; actual VM names stay in the vaulted network mapping.

New deployment disks use `/opt/vms/win-<vm-name>-clone.disk.qcow2`, and new domain
definitions carry the `aap-disconnected-windows-clone` description marker. Teardown
checks the exact domain name, marker, sole writable disk, absence of references
from other domains, regular nonsymlink file, and standard per-domain NVRAM location
before proceeding. It force-stops the validated domain, checks standalone qcow2
format, undefines the domain (removing UEFI NVRAM when present), and deletes only
its expected clone disk. Base images and shared networks are preserved.

Older unmarked VMs or disks using the earlier naming scheme are refused and need
manual review. A missing domain also fails rather than deleting an orphan disk.
Additional writable disks, unusual NVRAM paths, snapshots that prevent undefining,
or other libvirt errors stop teardown. File checks inspect metadata without
hashing the entire VM disk; content hashes do not establish deletion ownership.
Check mode performs inspection and does not stop, undefine, or delete anything.
Guarded teardown and independent preservation verification passed before the
2026-10-07 fresh deployment; the new end-to-end test repeats them.

```bash
ansible-playbook -i inventory.ini destroy-win-vms.yml --syntax-check
```

Optional deployment variables `vm_mac` and `vm_management_mac` assign explicit
primary/secondary NIC MACs. Supply actual assignments from the vaulted mapping
through AAP workflow variables. The secondary MAC requires a secondary network.
If omitted, libvirt generates the MAC.

### Networking modules and remaining PowerShell

DNS configuration uses `ansible.windows.win_dns_client`, the internal repository
server's router registry flag uses `ansible.windows.win_regedit`, and hostnames
use `ansible.windows.win_hostname`. These modules compare existing state before
applying changes.

`assets/configure-static-network.ps1` covers MAC-based NIC matching, NIC renaming,
DHCP disabling, static IPv4 addresses, per-interface default routes, and forwarding.
It validates every NIC before applying changes, skips matching settings, and reports
changes through `$Ansible.Changed`. Validation and check mode make no changes.
The installed `win_route` module cannot select an interface or manage DHCP default
routes in active and persistent stores, so these routes remain in the script.
DNS and registry configuration are outside the asynchronous network script.

### Configuration logging surveys

The Windows basics job template prompts for `windows_no_log`: `true` (default) hides
network task arguments and results, while `false` exposes them in AAP job output
for troubleshooting. An external boolean variable is also accepted. If omitted,
the playbook defaults to protection enabled. The survey definition is stored in
`assets/windows-basics-survey.json` for reuse on another controller. The WSUS
template has its own `wsus_no_log` survey for content-path diagnostics, also
defaulting to `true`, in `assets/wsus-setup-survey.json`.

The Windows basics toggle applies to network validation, asynchronous configuration/status,
connection-address switching and DNS tasks. Disabling it may reveal environment
IPs, MACs, adapter names and error details to users who can read the job output.
It does not disable logging protection in other playbooks, or print the Machine
or Vault credential values. A completed job's hidden results cannot be recovered
by changing the toggle; launch a new run to obtain diagnostic output.

The network task uses `community.windows.win_scheduled_task` with the built-in
`SYSTEM` service account and a delayed registration trigger. This avoids the
`runas` process-token creation failure observed on Windows Server 2025 (error 367),
and keeps the task independent of the WinRM login profile. Native task inspection
checks completion and exit code. Status polling explicitly reconnects after a
WinRM transport interruption while another NIC is still being changed; a
bounded 36-attempt loop still fails on persistent connection loss or task errors.
A small local runner records script errors and
change status in an atomic JSON result. Its working directory is restricted to
administrators and SYSTEM. The task and files are removed after success; failures
retain the result for diagnostics. Windows security and execution policies are
unchanged. The basics JT accepts a host limit for targeted troubleshooting.

### Teardown verification

`capture_windows_teardown_baseline.yml` and `verify_windows_teardown.yml` run
read-only through normal AAP job templates using the hypervisor Machine credential.
Capture the baseline before invoking the guarded destroy JT for each approved
Windows domain. Pass the capture job's `teardown_baseline` artifact (pre-teardown
domain XML/state and base-image file metadata) and the exact
`windows_demo_vm_names` list as protected inputs to verification after destruction.
It verifies only those four domains disappeared, their clone disks are absent,
and other domain definitions/states and base-image size/inode/mtime are unchanged.
This is a metadata comparison, not a full disk-content checksum.
Keep environment-specific baseline values outside plaintext Git.

`inspect_windows_network.yml` provides a read-only diagnostic JT for the saved
network result, scheduled-task status, current adapters, addresses and routes.
It accepts a host limit and uses the Windows Machine credential. Diagnostic
output includes network details and stays in AAP, outside Git.
