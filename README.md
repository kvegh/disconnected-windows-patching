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
No AAP configuration has been applied by this repository change.

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
images. The local SPICE console supports initial Windows setup. The role input
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
- `configure_wsus_environment.yml`: WSUS installation and client update policies.
- `deploy_chocolatey_nexus.yml`: Nexus services, hosted feeds, and Chocolatey clients.
- `collections/requirements.yml`: pinned Ansible collection dependencies.
- `docs/application-deployment.md`: application architecture, inputs, and remaining work.
- `vars/main.yml`: base images and sizing configuration.
- `assets/deploy-vm-survey.json`: AAP survey specification.

Install `ansible-core` in the execution environment. Validate without deployment:

```bash
ansible-playbook -i 'hypervisor,' 01-win-vm-setup.yml --syntax-check
```

Use standard Ansible YAML formatting (two-space indentation). No Windows VM
deployments or guest-level tests have been performed yet.

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

## Configure Windows and WSUS

`configure_wsus_environment.yml` runs against Windows guests over WinRM. Supply
an AAP Machine credential and inventory connection variables for NTLM over HTTPS
(port 5986), with certificate trust or an explicitly chosen demo validation policy.
The execution environment needs `pywinrm` and `collections/requirements.yml`.

Required inventory groups: `wsus_external` (one host), `wsus_internal` (one host),
and `windows_managed` (managed guests). Keep the groups disjoint. Supply sensitive
environment values through AAP credentials/inventory or Vault-encrypted variables.

Required variables:

- `wsus_internal_url`: internal WSUS HTTP URL including port 8530, reachable by clients.
- `wsus_client_sources`: list of client addresses/subnets allowed by the added firewall rule.
- Optional per-host `windows_hostname`: unique desired Windows name.
- Optional `wsus_content_path`: defaults to `C:\WSUS`. A separate content volume
  may be needed depending on the update set; the playbook does not resize disks.

The playbook checks WinRM, configures permanent NIC settings by MAC, reconnects
at the permanent address, optionally renames/reboots guests, and installs WSUS with
Windows Internal Database, initializes content storage, and selects manual
synchronization. Both WSUS servers are standalone; internal WSUS receives offline
imports. No synchronization is launched. Managed guests use internal WSUS with
Internet update locations blocked and automatic updating disabled, leaving patch
installation to AAP. Client web-service reachability is checked.

AAP's execution node must reach both the initial DHCP and permanent guest addresses.
The playbook configures static NIC addresses and removes unwanted default gateways. Internal WSUS needs routing disabled
and no default gateway. The added client firewall rule does not narrow existing
WSUS/IIS rules. Transfer access and network-level firewall isolation are configured separately.

Product/language/classification selection, synchronization, approval, export/import,
content transfer, and patch installation are subsequent steps. Clones also need
unique Windows Update client identities; this playbook does not reset them.

```bash
ansible-galaxy collection install -r collections/requirements.yml
ansible-playbook -i inventory.ini configure_wsus_environment.yml --syntax-check
```

## Application repositories and Chocolatey

The expanded demo co-hosts Nexus Repository Community Edition on external and
internal WSUS. External Nexus provides a staging feed; internal Nexus provides a
released feed containing offline-ready application packages. Managed Windows
servers use Chocolatey CLI, invoked by AAP over WinRM, to install selected versions.

`deploy_chocolatey_nexus.yml` deploys both Nexus Windows services and hosted feeds,
and bootstraps the Chocolatey clients from an offline MSI. See
[application deployment](docs/application-deployment.md) for installer inputs,
credentials, resource requirements, package promotion, and pending live validation.

The clients have only an isolated NIC. AAP still needs an execution node on that
network or a restricted management route. Internal WSUS's second NIC does not
provide a WinRM jump host automatically. The execution-node arrangement remains
to be configured; this playbook does not change network isolation or VM sizing.

## Implementation status

The three deployment/configuration playbooks are written and syntax-checked.
They have not been executed against the demo guests. VM creation remains separate
from Windows/WSUS configuration and Nexus/Chocolatey setup.

External-to-internal application promotion is intended to be AAP-controlled:
retrieve selected `.nupkg` versions from external Nexus, verify their checksums,
and upload them to internal Nexus. The replication playbook is not implemented;
Nexus does not automatically mirror the two feeds in this setup. Package building,
application deployment, and release manifests also remain to be implemented.

Before live deployment, stage verified installers, supply credentials, and establish
AAP execution-node access to the isolated endnodes. See the detailed
[implementation status and remaining work](docs/application-deployment.md#implementation-status-and-remaining-work).

### Permanent Windows NIC configuration

Provide `windows_network_interfaces` and `windows_connection_address` as protected
per-host inventory variables. Each interface entry requires `mac`, `name`,
`ipv4_address`, `prefix_length`, `gateway` (empty string for none), and `dns_servers`
(an empty list for none). Supply every demo NIC, including both internal WSUS NICs.
The connection address must match one configured NIC. Use actual deployed MACs;
fixed MAC inputs in VM deployment are still pending implementation.

Initially, inventory `ansible_host` must be the discovered DHCP address. Do not
supply `ansible_host` through launch extra variables: they would override the
playbook's switch to the permanent address. The bootstrap script validates all
MAC matches before applying changes, runs asynchronously through the connection
interruption, and verifies completion after reconnecting. It owns the configured
NICs' IPv4 addresses and replaces other IPv4 assignments on those NICs.

Only external WSUS may have an IPv4 gateway or DNS servers. Internal WSUS has
forwarding disabled as well. The script changes neither WinRM security settings
nor PowerShell execution policy. Existing WinRM firewall/certificate configuration
must permit connections at the permanent address from the AAP execution node.

`ansible_host` is updated for the current job, not persisted to the AAP database.
Update the AAP host's inventory variables to the permanent address after a
successful bootstrap, before future jobs. The vaulted umbrella network record is
reference data and is not automatically loaded or converted into these host vars.
This change is syntax-checked; Windows network switching and reboot persistence
still require a live test. Console access is needed to recover a misconfigured NIC.

### Repository server identities

The external and internal repository servers each host both WSUS and Nexus for
Chocolatey packages. Their planned VM names and Windows hostnames are recorded in
the umbrella project's vaulted network inventory. Use those values for `vm_name`
at deployment and `windows_hostname` during guest configuration.

The existing `wsus` deployment role and `wsus_external` / `wsus_internal` inventory
groups remain compatible with the playbooks; they identify WSUS-capable repository
servers, not dedicated WSUS-only guests. Existing AAP workflow launch inputs still
need to follow the renamed identities before deployment.

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
