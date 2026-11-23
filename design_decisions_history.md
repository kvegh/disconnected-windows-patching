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
