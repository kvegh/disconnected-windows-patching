# Design decisions history

The history of the 1.x implementation is in `archive/design_decisions_history.md`.

## 2026-11-23 (CET): WF3 review and rewrite, version 2.0.0

Line-by-line review of the 1.x code (task ratings in the workspace analyses
`windows-analysis/00..04`, tracked in bead-wd-0gnz.45), then archive and
clean reimplementation of the patching use case. Active Directory is out of
scope (later review).

Implementation: public `60829ee` (this repository, 2.0.0), private
`11f6bdc` (`disconnected-windows-patching-secrets`, 1.0.0).

### User decisions

- 10:51 Archive both repositories in `archive/` and rebuild from a clean state.
- 12:06 No partial live deploy; test the rewrite, run end to end, then rerun
  stage by stage with a cold, disk-only snapshot of all four VMs between
  stages. 12:07 Stage names `stage-1-OS-install` ... `stage-8-apps-upgraded`.
- 12:09 Drop the runtime-profile layer, filter plugins, helper scripts, the
  JT/workflow creator playbooks, teardown/regression/inspect playbooks and
  tests (old code stays as reference).
- 12:10 Keep the evaluation activation, once, in stage 2.
- 12:15 AAP reaches the isolated network through a second NIC of the AAP VM
  (shortcut 1, documented); execution node inside the network is a TODO
  (bead-wd-0gnz.45.2).
- 12:17/12:24 One sequential repository setup (features and Chocolatey CLI,
  one reboot, WSUS, Nexus) instead of three jobs.
- 12:19 Drop the WSUS prerequisite playbook; one free-disk check in the WSUS
  download step.
- 12:29 Public Chocolatey community packages as published (with their
  dependency) instead of self-built packages.
- 12:39/12:51 New proof report: one CSV line per run via
  `community.windows.win_lineinfile`, four workflow points, a desktop script
  that only displays the CSV. Drop the patch level assessment.
- 12:52 Destroy-all-VMs job template (keeps base images, network, AAP NIC).
- 12:53 Keep `demo-with-aap/` updated to the new flow; the simple `demo/`
  stays archived.
- 13:33 AAP VM NIC configured with `redhat.rhel_system_roles.network`.
- 13:34 Fixed Windows addresses through libvirt DHCP host entries instead of
  in-guest static IP configuration.
- 13:35/13:39 All four VMs in one run, parallel first boot, skip defined VMs,
  version -> image/osinfo/boot mapping (2022 BIOS, 2025 UEFI), OS version
  check after the first boot.
- 14:37 Anonymous read on the repo-int Nexus.
- 14:41 Nexus 3.98.3-01, EULA accepted for exactly that version (recorded in
  the private configuration).
- 14:55 repo-int keeps its second NIC on the management network via DHCP
  (shortcut 2, documented; no router TODO).
- 14:57 Applications: explicit export archive -> transfer -> import; hosted
  feed on repo-ext, no proxy.
- 15:00 Fixed patch month in the configuration (stage 3 downloads it, stage 5
  approves it).
- 15:02 One workflow; snapshot nodes switched by the survey `take_snapshots`,
  default yes.
- 15:07/15:19 Custom credential type "Nexus admin" for the jobs that call the
  Nexus API.
- 15:22/15:23 The Windows infra is deployed by the AutoDeploy deployer's infra
  node; the infra playbook lives in this public repository
  (`playbooks/aap-infra.yml`), configuration in the private `aap-infra/`.
- `no_log: true` only on tasks that carry or could print secrets (user
  correction during the rewrite; supersedes a play-level proposal).

### Agent choices (within the decisions)

- Activation NIC on the management network (old baseline); only the managed
  servers get it (`windows_activation_mac`): the repository servers already
  reach the Internet through that network (repo-int by shortcut 2).
- Activation as four workflow nodes, not three: attach, activate, detach on
  success (continues) and a second detach after a failed activation (stops
  the workflow), so a failure never leaves the NIC attached nor continues
  with an unactivated server.
- WSUS transfer through the existing WSUS IIS site (`/Content` and a new
  `/export` virtual directory) instead of a dedicated site; IUSR read on the
  export folder; `.gz` added to the IIS MIME map next to `.msu`/`.wim`.
- WSUS API and WsusUtil as SYSTEM (`become` runas), as in 1.x.
- Snapshot and revert in one job template (survey action/stage); NVRAM copy
  of the UEFI VM next to each snapshot and back on revert (libvirt does not
  capture it offline).
- Package upload: AAP (EE) uploads to repo-ext with `ansible.builtin.uri`
  multipart; repo-int uploads the unpacked archive to its own Nexus with a
  short inline PowerShell HttpClient call (gap: `win_uri` has no multipart,
  PowerShell 5.1 no `-Form`).
- Baseline/upgrade versions: 7-Zip 26.3.0 -> 26.4.0, Git 2.55.0.5 ->
  2.56.0.2 (the versions of 1.x, now as community packages),
  chocolatey-core.extension 1.3.3 (no further dependency; 1.4.0 would pull
  chocolatey-compatibility.extension). SHA512 pins from the community feed,
  checked against downloaded files.
- Same SSH key and automation account for the hypervisor and the AAP VM
  (AutoDeploy pattern); AAP VM address = its fixed DHCP reservation
  (configuration), its virsh name = `usecase_target_aap`.
- All job template configuration as AAP inventory variables (they also
  apply to the plays on the job's localhost).

### Unverified until the first deploy

Listed in `TODO.md` and in the README (execution environment contents of the
deployer, Nexus 3.98 service script and asset download, IIS export reads,
WsusUtil import, UEFI NVRAM path, repo server disk space).

## Anonymous read on repo-ext as well — 2026-11-23

User decision (20:41 CET): repo-ext's Nexus also allows anonymous read. The
export reads (search and the pinned package download into the export folder) no
longer log in, which removes the unverified login-across-redirect risk of the
asset download. Writing (uploads to repo-ext) still uses the admin login. Supersedes
"anonymous read on the repo-int Nexus" (14:37). Commit: `ec71fef` (v2.0.1).

## AAP VM address from its DHCP lease — 2026-11-23

AutoDeploy decision (user, 19 November 2026, CET; approved for implementation
23 November 2026, CET; AutoDeploy bead bead-wd-0gnz.42): one hypervisor may
host several AAPs, whose VMs get DHCP-assigned MACs and addresses. The AAP VM
address is therefore no longer configuration (`windows_infra_aap_vm.address`,
the old fixed reservation): `playbooks/aap-infra.yml` reads it from the VM's
DHCP lease on the hypervisor with `community.libvirt.virt`
(`get_ifaddresses`, source `lease`), by the name `usecase_target_aap`, and
fails with a clear message if there is no lease. Agent choices: the native
module (same as the AutoDeploy AAP VM stage, same 2.4.0 pin, added to
`collections/requirements.yml`) instead of `virsh domifaddr`; the delegated
task sets `connection: ssh`, because the play's `connection: local` would
otherwise run it in the execution environment (checked locally). The AAP VM's
isolated NIC has a static address and no lease, so only the management
address is found. Still one Windows use case per hypervisor: the Windows VM
names, the isolated network and the AAP VM's isolated NIC MAC and address are
fixed. Syntax check passes (ansible-core 2.16.19); not run.
Commit: `21867e4` (v2.1.0).

## take_snapshots read as a boolean — 2026-11-23

Found in the first v32 test run (Workflow 47, take_snapshots=no): Job 48
and Job 62 — Disconnected Windows - Snapshot VMs shut the VMs down and took
snapshots. AAP passes extra vars tagged `!unsafe`, and ansible-core 2.20
loads `!unsafe 'no'` as the boolean false, so `take_snapshots == 'no'` never
matched (reproduced locally with ansible-core 2.20.11). Agent choice
(routine fix): the skip condition reads `take_snapshots | bool`; the survey
keeps its yes/no choices.

Implementation commit: `b6e2cee` (2.1.1).

## External feed upload from repo-ext — 2026-11-23

Found in the v32 test run (Job 87 — Disconnected Windows - Fill External
Applications, details from debug Job 89/92): Nexus answered every AAP-side
upload with HTTP 500 "Missing nuspec". `ansible.builtin.uri` with
`body_format: form-multipart` base64-encodes file parts (documented in
`prepare_multipart`), and the Nexus Components API does not decode them.
Agent choice (routine fix, no new technology): AAP still downloads and
checks the pinned packages, copies them to repo-ext, and repo-ext uploads
them with the .NET HttpClient multipart the internal import already used;
both playbooks share `tasks/nexus-packages-upload.yml`. Verified by Job 95
(successful).

Implementation commit: `7f492ad` (2.1.2).

## WSUS free-space check counts downloaded content — 2026-11-23

Found when rerunning Workflow 98 on v32 (Job 114 — Disconnected Windows -
Fill External WSUS): the free-space check failed with 3.9 GB free on the
40 GB C: volume, because the first run had already put the patch month
into the WSUS content folder. Agent choice (routine fix): the check adds the
content folder size (win_stat) to the free space, so a rerun passes and a
first run checks exactly as before.

Implementation commit: `9b3a878` (2.1.3).

## Proof KB from the rollup package; power button pressed until off — 2026-11-24

Found in the v32 test run (Workflow 138, Job 62 — Disconnected Windows -
Snapshot VMs) and confirmed on the running VMs with ad hoc diagnostics:

- Proof report `newest_kb` showed `-` on win2022-managed although KB5082142
  was installed: the Windows Update history there is empty
  (`GetTotalHistoryCount` 0; win2025-managed lists its entries), so the
  title filter never had a match. Agent choice (routine fix): read the KB
  from the installed `Package_for_RollupFix` servicing package
  (`Get-WindowsPackage`, description "Fix for KB..."); verified on both
  managed servers (KB5082142, KB5082063). The SYSTEM become is no longer
  needed.
- The managed servers ignored the ACPI shutdown for 10 minutes. Not the
  activation NIC: their displays were idle-off (10-minute timeout) and the
  power button press only woke them (Kernel-Power 566, reason PowerButton,
  at the exact press time); the repository servers had rebooted less than
  10 minutes earlier. Reproduced: one `virsh shutdown` on an idle server
  woke the display, a second shut it off. A display-timeout policy value
  under `HKLM:\SOFTWARE\Policies\Microsoft\Power` did not take effect
  (tested). Agent choice (routine fix, hypervisor side, covers stage 1 and
  any guest setting): the wait loop of the snapshot playbook presses the
  power button again (`virsh shutdown`) until virsh reports the VM as not
  running, instead of only polling `virsh domstate`.
  User (2026-11-24): the workaround is accepted as long as it is documented.
  Untested alternative inside the guest: `powercfg /change monitor-timeout-ac 0`
  (one win_command) would keep the virtual display on.

Implementation commit: `1441a3d` (2.1.4).

## Community feed download timeout — 2026-11-24

Found in the v32 snapshot run (Job 250 — Disconnected Windows - Fill
External Applications): the downloads of the older pinned versions
(7zip.install 26.3.0, git.install 2.55.0.5) failed with read timeouts after
get_url's default 10 s, three times each; the newer versions downloaded at
once. Measured: community.chocolatey.org answered 7zip.install 26.3.0 after
99 s, a repeated request in under a second (the feed serves an older version
slowly when it has not served it recently). Agent choice (routine fix): the
download task gets `timeout: 180`.

Implementation commit: `06a801b` (2.1.5).

## No copied secrets: SSH key and base image password from AutoDeploy — 2026-11-24

User decision (24 November 2026, CET): "don't copy". The AutoDeploy private
repository is the shared storage for values several use cases need. The
infra playbook requires `autodeploy_secrets_dir` from the deployer
(AutoDeploy `944a138`, v0.5.0), loads the AutoDeploy vault as
`autodeploy_vault` and takes from it the automation account's SSH key
(`vaulted_controller_credentials_hactar_ng_ansible_ngng_ssh_key_data`) and
the base images' local Administrator password
(`vaulted_windows_base_image_admin_password`, moved to the AutoDeploy vault
as a property of the images AutoDeploy downloads). The private vault copies
`vaulted_windows_hypervisor_ssh_key_data` and
`vaulted_windows_managed_hosts_password` are removed; the two AAP
credentials reference the AutoDeploy names.

Implementation commit: `eed8108` (2.1.6); private `7707bec` (1.1.2),
AutoDeploy private `4b1c9ed` (0.4.2). Not deployed.

## Evaluation rearm of every fresh clone — 2026-11-24

User decision (24 November 2026, CET): rearm every Windows clone right after
cloning, so each fresh clone gets a full evaluation period. Live facts (Ad
hoc 310 on v32): the base images are ServerDatacenterEval, TIMEBASED_EVAL;
2022 clones inherit a fixed expiry from the base image (about 131 days left,
rearm count 6); 2025 clones showed 180 days, rearm count 1. The infra
playbook runs `cscript //nologo C:\Windows\System32\slmgr.vbs /rearm`
(`ansible.windows.win_command`) and `ansible.windows.win_reboot` after the
first WinRM wait and before the OS check, only on VMs created in this run
(not in the hypervisor's `virsh list --all` before creation): the rearm count
is limited, a rerun must not use it up. The activation after the rearm is
left to the existing stage-2 activation (activation NIC for the managed
servers, internet through `internal` for the repository servers), not
duplicated.

To verify at the next deploy: the license status after the rearm (evaluation
period reset, or a grace state waiting for activation), and that the stage-2
activation succeeds on the rearmed clones.

Implementation commit: `ee6a53d` (2.1.7). Not deployed.
