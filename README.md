# Disconnected Windows Patching

AAP, WSUS, Chocolatey and Nexus demo for Windows patching and application deployment
in a simulated disconnected environment.

## VM deployment

`01-win-vm-setup.yml` creates one VM per launch on the inventory's `hypervisor` group.
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
2 vCPUs; `managed` gets 2048 MiB RAM and `wsus` gets 8192 MiB.
An existing VM or destination disk causes the launch to stop rather than overwrite it.

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

`wait_for_dhcp` defaults to `false` because initial setup or the network layout
may prevent immediate DHCP. Enable it to wait up to five minutes and discover
IPv4 by MAC on a libvirt network providing DHCP. A lease does not establish that
Windows is ready for AAP management. Configure management connectivity and
isolation separately; this playbook does not create networks or firewall rules.

## Layout and validation

- `01-win-vm-setup.yml`: VM deployment playbook.
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
- `sync_external_wsus.yml`: Microsoft metadata synchronization and selected file downloads.
- `export_external_wsus.yml`: WSUS metadata export and management-only IIS publication.
- `replicate_and_import.yml`: direct external-to-internal HTTP transfer and offline WSUS import.
- `docs/wsus-data-flow.md`: inputs, workflow, integrity checks, module use and live validation status.
- `collections/requirements.yml`: pinned Ansible collection dependencies.
- `docs/application-deployment.md`: application architecture, inputs, and remaining work.
- `vars/main.yml`: base images and sizing configuration.
- `assets/deploy-vm-survey.json`: AAP survey specification.

Install `ansible-core` in the execution environment. Validate without deployment:

```bash
ansible-playbook -i 'hypervisor,' 01-win-vm-setup.yml --syntax-check
```

Use standard Ansible YAML formatting (two-space indentation). VM creation, Windows basics and WSUS configuration have been exercised against
the demo guests. Nexus/Chocolatey deployment still needs a live test.

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
| Preparation and reboots | `prepare_repository_servers.yml` | Disconnected Windows Patching - Prepare Repository Servers |
| WSUS | `setup_wsus.yml` | Disconnected Windows Patching - Setup WSUS |
| Application repositories and clients | `setup_chocolatey.yml` | Disconnected Windows Patching - Setup Chocolatey |

The existing **Deploy Windows + WSUS environment** workflow creates four VMs in
parallel and waits for all four to succeed before Windows basics. A preparation
stage completes feature/MSI installation and reboots. WSUS setup and Chocolatey/Nexus
setup then run in parallel. The Chocolatey branch proceeds through external package
synchronization, HTTP export, internal import, baseline installation and upgrade.
The WSUS branch continues through prerequisite checks,
synchronization, export, and replication/import. Each transition requires success.
See [WSUS data flow](docs/wsus-data-flow.md) for the full graph and inputs.
Use an individual configuration template to reconfigure existing VMs; rerunning
the deployment workflow attempts creation and its existing-VM guard will stop it.

All configuration templates use WinRM and a Windows Machine credential. Their
execution environment needs `pywinrm` and the pinned Ansible collections.
Required disjoint inventory groups are `wsus_external`, `wsus_internal`, and
`windows_managed`. Keep environment assignments protected and out of plaintext Git.

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

Both WSUS servers are standalone and synchronization is manual. Managed guests
use internal WSUS with Internet update locations blocked and automatic updating
disabled, leaving patch installation to AAP. Product selection, synchronization, download-only
approvals, metadata export/import and update binary transfer are implemented in
the separate [WSUS population playbooks](docs/wsus-data-flow.md). Internal client
approvals and patch installation remain separate work.

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

The deployment, preparation, setup and WSUS population playbooks are written
and syntax-checked.
VM creation, networking, DNS, hostnames, WSUS initialization and client policies
have completed successfully in the demo. The split preserves those tasks; the
new modular templates need their first separate live runs. External WSUS readiness
passed read-only job 1072; the new synchronization/export/import stages need
their first live runs. Nexus/Chocolatey has
not been deployed yet. Installers download automatically with pinned checksums;
Nexus administrator and package-reader credentials are in the existing encrypted vault.

AAP-controlled application synchronization, export, internal import, baseline
installation and upgrade are implemented as separate playbooks/job templates.
The targeted content is 7-Zip and Git with two pinned versions each. Native modules
handle normal configuration and installation; small helpers build deterministic
packages/exports, inspect archive integrity and upload binary packages on Windows.
The full flow still needs live Nexus and endnode validation. The latest environment
workflow stopped during Windows 2025 basics before service setup; its four VM
creation jobs succeeded. See [application deployment](docs/application-deployment.md).

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
Windows network switching and reboot persistence were verified before the split;
the modular template has not yet been run separately. Console access is needed to recover a misconfigured NIC.

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
or other libvirt errors stop teardown. Check mode performs inspection and does
not stop, undefine, or delete anything. No teardown has been live-tested or run.

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
checks completion and exit code; a small local runner records script errors and
change status in an atomic JSON result. Its working directory is restricted to
administrators and SYSTEM. The task and files are removed after success; failures
retain the result for diagnostics. Windows security and execution policies are
unchanged. The basics JT accepts a host limit for targeted troubleshooting.

### Teardown verification

`verify_windows_teardown.yml` runs read-only through its own AAP job template.
Supply `teardown_baseline` (pre-teardown domain XML/state and base-image file
metadata) and the exact `windows_demo_vm_names` list as protected AAP inputs.
It verifies only those four domains disappeared, their clone disks are absent,
and other domain definitions/states and base-image size/inode/mtime are unchanged.
This is a metadata comparison, not a full disk-content checksum.
Keep environment-specific baseline values outside plaintext Git.
