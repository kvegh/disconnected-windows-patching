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

| VM name | Role | Windows version | Primary NIC | Second NIC |
|---|---|---|---|---|
| `wsus-external` | `wsus` | `2022` | `internal` | None |
| `wsus-internal` | `wsus` | `2022` | `windows-isolated` | `internal` |
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

The playbook checks WinRM, optionally renames/reboots guests, installs WSUS with
Windows Internal Database, initializes content storage, and selects manual
synchronization. Both WSUS servers are standalone; internal WSUS receives offline
imports. No synchronization is launched. Managed guests use internal WSUS with
Internet update locations blocked and automatic updating disabled, leaving patch
installation to AAP. Client web-service reachability is checked.

NIC addresses, routing, and network isolation must already be configured. AAP's
execution node must reach the isolated guests. Internal WSUS needs routing disabled
and no default gateway. The added client firewall rule does not narrow existing
WSUS/IIS rules. This playbook does not configure NICs or transfer access.

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
