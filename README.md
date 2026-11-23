# Disconnected Windows patching with AAP

Version 2.1.1. Ansible Automation Platform (AAP) patches Windows servers in a
network without Internet access: Microsoft updates and application packages
are fetched on the connected side, exported, pulled into the isolated side and
installed from there only. Windows updates go through WSUS, applications
through a Chocolatey feed in Sonatype Nexus.

This repository holds only execution code (playbooks). Every environment
value (addresses, MACs, names, versions, checksums) and every secret lives in
the private repository `disconnected-windows-patching-secrets`.

The old implementation (1.x) is kept unchanged in `archive/` as reference.

The Active Directory part moved to its own use case `kvegh/AAP-ActiveDirectory`
(2026-11-23); `archive/` keeps the old AD code as reference.

## Topology

```
  Internet
     |
  management network (libvirt NAT, "internal")
     |-- AAP VM (first NIC)
     |-- repo-ext   external repository: WSUS + Nexus, syncs from Microsoft
     |              and the Chocolatey community feed
     |-- repo-int   (second NIC, see shortcut 2)
     |
  isolated network (libvirt, no forwarding, no DNS)
     |-- AAP VM (second NIC, see shortcut 1)
     |-- repo-int   internal repository: WSUS + Nexus, import only
     |-- win2022-managed   Windows Server 2022
     |-- win2025-managed   Windows Server 2025
```

All four Windows VMs run on one KVM hypervisor. libvirt DHCP host entries give
every NIC its fixed address; Windows needs no IP configuration.

## Documented shortcuts

This is a functional demo, not a security reference. Two shortcuts differ from
a real disconnected site:

1. **AAP has a NIC in the isolated network.** The AAP VM gets a second NIC with
   a static address in the isolated network and manages the internal hosts
   directly ("a bit cheating"). A real site would run an AAP execution node
   inside the isolated network (see `TODO.md`).
2. **repo-int is dual-homed.** Its second NIC sits in the management network
   (DHCP, with a default gateway, so technically Internet-capable) instead of
   a DMZ behind a firewall. repo-int only pulls the export from repo-ext and
   never synchronizes from Microsoft; the managed servers stay in the
   isolated network without any route out. A router or firewall would not
   change the package transfer shown here.

## Stages and snapshots

The workflow runs the stages in order. After each stage all four VMs are shut
down and get a cold, disk-only snapshot with the same name; a demo starts by
reverting to one of them.

| Stage | Work | Playbooks | Snapshot |
|---|---|---|---|
| 1 | Network, AAP NIC, four VMs (AutoDeploy infra node) | `aap-infra.yml` | `stage-1-OS-install` |
| 2 | Host names, update policy, evaluation activation (temporary NIC), repository setup (features, Chocolatey CLI, one reboot, WSUS, Nexus, client sources) | `windows-basics.yml`, `activation-nic.yml`, `windows-activate.yml`, `repositories-setup.yml` | `stage-2-basics-repos` |
| 3 | repo-ext: WSUS sync, download of the patch month, metadata export; community packages into the external feed, export archive | `wsus-external-fill.yml`, `applications-external-fill.yml` | `stage-3-external-repo-fill` |
| 4 | repo-int pulls and imports the WSUS export and the package archive | `wsus-internal-import.yml`, `applications-internal-import.yml` | `stage-4-internal-repo-import` |
| 5 | repo-int approves only the patch month; proof report `before-patching` | `patch-level-cutoff.yml`, `proof-report.yml` | `stage-5-patch-level-cutoff-set` |
| 6 | Managed servers install the approved updates; proof `os-patched` | `windows-patch.yml`, `proof-report.yml` | `stage-6-OS-patched` |
| 7 | Baseline application versions; proof `apps-baseline` | `applications-deploy.yml` (`app_track: baseline`), `proof-report.yml` | `stage-7-apps-baseline` |
| 8 | Upgrade to the newer versions; proof `apps-upgraded` | `applications-deploy.yml` (`app_track: upgrade`), `proof-report.yml` | `stage-8-apps-upgraded` |

The patch month is fixed in the configuration (for example `2026-04`): stage 3
downloads only that month and the updates it requires, stage 5 approves only
that month.

The evaluation licenses are activated once, in stage 2, so reverted snapshots
keep running (an unactivated evaluation shuts down after 10 days). The
managed servers get a live-only NIC on the management network for the
activation; it is detached right after.

Applications are the public Chocolatey community packages as published
(7-Zip and Git, two pinned versions each, plus their dependency), checked
against pinned SHA512 values, uploaded to repo-ext's feed, exported as one
archive, pulled by repo-int and imported into its feed. The managed servers
install from repo-int only. Both Nexus servers allow anonymous read; writing needs
the admin login.

## Using the demo

In AAP (all objects come from the -secrets repository):

1. Run **Disconnected Windows - Snapshot VMs** with `snapshot_action: revert`
   and the stage to start from, for example `stage-5-patch-level-cutoff-set`.
2. Run the job templates of the following stages by hand, or show their
   earlier job output.
3. Run **Disconnected Windows - Proof Report** (any `proof_stage` text) to show
   the history; on a managed server the desktop shortcut "Patch and
   application proof" shows the same file in colour.

The proof report appends one line per run to
`C:\ProgramData\WindowsDemoProof\proof-log.csv` on each managed server: UTC
time, host, stage, OS build (`CurrentBuild.UBR`), newest installed cumulative
update (KB), installed version of each application. Because the file is on the
VM disk, a reverted snapshot shows exactly the history up to its stage.

`demo-with-aap/` is a browser walkthrough of the stages
([published page](https://kvegh.github.io/disconnected-windows-patching/demo-with-aap/)).

## Deployment

### Prerequisites

- KVM hypervisor with libvirt 9.9 or newer (revert of external snapshots),
  the management network, the base images of Windows Server 2022 (BIOS) and
  2025 (UEFI), downloaded and checked by the hypervisor build.
- Base images with the local Administrator password of the -secrets vault and
  WinRM over HTTPS (port 5986, self-signed certificate) allowed from the AAP
  VM's addresses in both networks (manual image preparation).
- An AAP deployed by AutoDeploy, with the use case deployer.

### Infra: `playbooks/aap-infra.yml`

The AutoDeploy use case deployer (infra node, catalog keys
`infra_repository: kvegh/disconnected-windows-patching`, `infra_ref: main`,
`infra_playbook: playbooks/aap-infra.yml`) clones this repository and the
-secrets repository and runs, from this checkout:

```
ansible-playbook --vault-id cac@/dev/stdin \
  -e usecase_target_aap=<AAP VM name> \
  -e usecase_secrets_dir=<absolute path of the -secrets checkout> \
  playbooks/aap-infra.yml
```

Localhost is the only inventory; the playbook loads `aap-infra/*.yml` and
`env_variables.yml` from the -secrets checkout and adds the hypervisor, the
AAP VM (through the hypervisor as jump host) and the four Windows VMs itself.
The AAP VM's address is not configured: AutoDeploy gives its AAP VMs DHCP
addresses (several AAPs can share the hypervisor), so the playbook reads it
from the VM's DHCP lease on the hypervisor (`community.libvirt.virt`,
`get_ifaddresses`) by the name `usecase_target_aap`.
It is rerunnable and leaves existing networks, entries, NICs and VMs alone.

It needs from the deployer's execution environment (to verify at the first
deploy): `ansible.windows` (WinRM connection, facts), `redhat.rhel_system_roles`
(network role), `community.libvirt` (the AAP VM's address), Python `pywinrm`,
an SSH client. `collections/requirements.yml`
lists the same pins; the AAP project sync installs it for the job templates.

The deployer must run on the target AAP itself: the OS check at the end
reaches the isolated hosts through the AAP VM's new NIC.

### AAP content

The deployer's content node applies `aap-content/` of the -secrets repository:
custom credential type "Nexus admin" and the credentials, inventory, project
(this repository), job templates and the workflow
**Disconnected Windows - Deploy and test** (survey `take_snapshots`, default
`yes`). The workflow starts with the snapshot `stage-1-OS-install` of the VMs
the infra node created and ends with `stage-8-apps-upgraded`.

**Disconnected Windows - Destroy VMs** removes the four VMs with all their
snapshots and files (not the network, not the AAP NIC, not the base images);
the infra node creates them again.

## Automated functional tests

The end-to-end test is the workflow itself, run on freshly created VMs:

1. Destroy VMs (if VMs exist), then the deployer's infra node (`aap-infra.yml`).
2. Workflow **Disconnected Windows - Deploy and test** with
   `take_snapshots: no` for a quick functional run, or `yes` for the final run
   that leaves the eight demo snapshots.

What it verifies:

- aap-infra: every VM answers WinRM and runs the configured Windows Server
  version.
- Stage 2: activation succeeds (license status 1); the internal WSUS and the
  internal feed answer from both managed servers.
- Stage 3/4: every update file and package is checked against its SHA1/SHA512
  during transfer; WsusUtil export/import succeed.
- Stage 5: the approved month is `Ready` on repo-int.
- Stage 6: `win_updates` ends with no update left and no reboot pending.
- Stages 7/8: Chocolatey installs exactly the pinned versions.
- The four proof reports show the expected progression in the job output:
  OS build and newest KB change between `before-patching` and `os-patched`;
  application versions change from `-` to baseline to upgrade.

Reverting a stage snapshot and rerunning the later job templates repeats the
demo path. Local checks without targets: `ansible-playbook --syntax-check`
on every playbook, `yamllint`, and the walkthrough tests in `demo-with-aap/`.

## Conventions

- Playbooks: `playbooks/<object>-<action>.yml`, one per job template;
  shared task files in `playbooks/tasks/`.
- Variables: snake_case; configuration variables are prefixed by component
  (`windows_`, `wsus_`, `nexus_`, `chocolatey_`, `repository_`, `proof_`,
  `snapshot_`); playbook-internal variables by playbook (`fill_`, `import_`,
  `setup_`, ...).
- `no_log: true` only on tasks that carry or could print secrets (passwords,
  keys, Nexus API calls with credentials, vault loading); everything else
  stays visible.
- Native certified modules first; inline PowerShell only where no module
  exists (WSUS server API, Windows licensing, Windows Update history, IIS MIME
  map, multipart upload from Windows), each with a comment on the gap.

## Configuration reference

Set in the -secrets repository (AAP inventory variables of
`aap-content/`, infra values in `aap-infra/`):

- Windows: `windows_wait_timeout`, `windows_staging_dir`, `windows_vm_dir`,
  `windows_activation_network`, host vars `windows_activation_mac`,
  `windows_nvram_file` (group `windows_uefi`).
- WSUS: `wsus_port`, `wsus_content_dir`, `wsus_patch_month`, `wsus_products`,
  `wsus_classifications`, `wsus_languages`, `wsus_minimum_free_gb`,
  `wsus_sync_retries`, `wsus_download_retries`, `wsus_import_ready_retries`.
- Transfer: `repository_export_dir`, `repository_import_dir`,
  `repository_firewall_remote_addresses`.
- Nexus: `nexus_version`, `nexus_download_url`, `nexus_download_sha256`,
  `nexus_eula_accepted_version`, `nexus_install_dir`, `nexus_data_dir`,
  `nexus_port`, `nexus_service_name`, `nexus_feed_name`; `nexus_admin_password`
  from the "Nexus admin" credential.
- Chocolatey: `chocolatey_msi_url`, `chocolatey_msi_sha256`,
  `chocolatey_community_feed_url`, `chocolatey_source_name`,
  `chocolatey_packages` (`id`, `version`, `track` baseline | upgrade |
  dependency, `sha512`).
- Patching and proof: `windows_update_reboot_timeout`,
  `windows_update_failed_retries`, `proof_dir`, `snapshot_shutdown_retries`.
