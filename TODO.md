# Demo TODO

## Review Ansible use and external dependencies

- Review every automation stage to identify whether it uses native Ansible
  modules only. List each exception: PowerShell scripts, Windows/WSUS APIs,
  command-line utilities, custom helpers and direct external API calls.
- For each exception, record its purpose, how Ansible invokes it, why a native
  module is insufficient, and whether it can be replaced with supported Ansible
  content. Include controller configuration, content transfer and client patching.
- Document the resulting module/dependency map and remaining replacements.

## Verify Microsoft reboot guidance during patching

- Check that server patching performs every reboot required or recommended by
  Microsoft for the selected updates and prerequisites, before, within and after
  installation rounds.
- Verify native `win_updates` handling within a batch and the playbook's later
  rescan/reboot passes against applicable Microsoft guidance on both supported
  Windows Server versions.
- Record update KBs, reboot triggers and counts, and final pending-reboot state.
  Add focused regression coverage for any gaps found during the review.

## Permanent IP and MAC assignments

- Define permanent addresses for every demo VM and every relevant NIC, including
  the AAP management and isolated interfaces, test server, monitoring server,
  remote management host, external WSUS/Nexus, internal WSUS/Nexus on both networks,
  and all managed Windows endnodes.
- Assign and preserve explicit unique MAC addresses in VM deployment so deleting
  and recreating a VM does not change its NIC identities.
- Prefer MAC-bound DHCP reservations where we control DHCP. On the management
  LAN, coordinate reservations with its actual DHCP server; libvirt reservations
  only apply to networks where libvirt provides DHCP. Use guest static addresses
  outside DHCP pools where reservations are unavailable.
- Verify address/MAC uniqueness, exclude static addresses from dynamic pools, and
  ensure persistent reservations survive network restarts and host reboots.
- Identify and rename Windows adapters by MAC as Management or Isolated; do not
  rely on enumeration order. Keep isolated NICs without a gateway or DNS server.
- Keep AAP inventory connection addresses aligned with the permanent assignments.
  Verify WinRM from the actual AAP execution environment and confirm isolated
  clients cannot obtain Internet access through dual-connected hosts.
- Store the complete address/MAC mapping in AAP inventory or Vault-encrypted
  configuration, including deployment/workflow inputs and DHCP configuration.
  Keep actual hostnames, IPs, MAC assignments, and credentials out of plaintext Git.
- Fixed MAC deployment inputs are implemented. Automate DHCP reservations to
  match those inputs; libvirt generates MACs when explicit inputs are omitted.

## WSUS population follow-up

- Run and validate the new sync, export and import stages with current Microsoft updates.
- Validate applicability and prerequisite/checkpoint coverage on both older base images.
- Internal monthly approval/visibility ceilings are implemented in
  `set_internal_wsus_patch_month.yml`, with saved-policy reapplication after imports.
  Client patch installation is implemented separately in `update_managed_windows.yml`.
- Installed-state assessment is implemented in `assess_windows_patch_level.yml`.
  The managed update template provides read-only applicability scans in Check mode.
- Validate a complete client OS baseline installation and a later-month upgrade
  on both supported Windows versions, including intermediate reboots and final
  installed-build evidence. Code tests and dry runs do not establish this result.
- Reproducible named-month selection, historical content download and internal
  approval are implemented. Keep newer releases available externally for the
  next demonstration stage and add survey choices after auditing new catalogues.
- Validate the pinned Nexus/Chocolatey downloads and vaulted inputs in live service setup.
- Validate Task Scheduler network configuration on all four freshly cloned VMs.
- Exercise the five application stages: sync, export, import, baseline deployment and upgrade.
- Add metadata snapshot/import-log retention without deleting active transfer files.
- Migrate pinned community IIS modules to microsoft.iis before their upstream removal.

## Active Directory and AAP permissions from nested groups

- [x] Deploy a separate Windows Server 2025 domain controller and start the
  dedicated test AAP. Keep the existing Windows service VMs separate.
- [x] Install current applicable Microsoft Server updates, complete reboots and
  require an empty applicable-update scan. Report the Windows 11-only Security
  UI offer separately using Microsoft's product applicability.
- [x] Configure and verify the forest-root time service against its existing
  NTP peer; do not propagate an inherited virtual hardware clock.
- [x] Reconcile the existing directory to 12 users: reader, executor and admin
  for DK, NO, NZ and HU. Maintain 12 global people groups and 12 domain-local
  access groups (DK/NO/EU/NZ), retire EU-only users, and verify matching-role
  EU-approved inheritance for DK/NO/HU with independent NZ access. HU needs no
  own domain-local groups or resources.
- [x] Install the dedicated LDAPS certificate and verify normal chain and
  hostname validation inside the test AAP gateway runtime.
- [x] Apply the five country-owned resource sets: DKlocal, NOlocal,
  DKEUapproved, NOEUapproved and NZlocal. Each has an inventory, independent mock
  credential, distinct AAP Project and two inert job templates. Twelve teams
  provide 75 object-scoped grants; executors have view-only Project access.
- [x] Document the complete twelve-user access matrix and step-by-step Windows
  AD → nested group → AAP mapping → resource demonstration in both presenter
  guides. Distinguish country ownership, EU clearance and identity-based access.
- [x] Add the eight-stage AD branch to the Windows provisioning workflow while
  preserving its other 21 nodes. Capture all 32 job templates and 29 workflow
  nodes in encrypted CaC; validate import and target-specific credentials on
  the separate AAP.
- [x] Complete live validation of the revised five-set matrix: 12 LDAP logins,
  expected teams on gateway/controller, 75 grants, 360 primary read/launch checks
  and 36 successful inert jobs across both template operations. Count unchanged
  description PATCH and exact-list checks separately. Prove strict-local and NZ
  isolation, shared approved access, role limits and retirement of EU-only users.
  The revised model passed on 2026-10-23, including 108 description PATCH,
  48 exact-list and 24 gateway/controller membership checks.
- [x] Preserve additional AD users and nested groups across identity setup
  reruns. A native Windows test passed two reconciliations with additional
  objects, an unchanged second run, preserved nested permissions and cleanup.
  The following complete AAP access regression passed again.
- [x] Document readable hyphenated resource labels, the deployed-key lookup,
  actual demo usernames, new-user Windows steps and multiple permissions per
  mapped AD group.

An access-removal demonstration is outside the requested scope. The presenter
walkthrough covers granting access, automatic first login and role/country
isolation.

Optional later work: compare nested-group lookup performance with the AD
matching rule in chain on a realistically sized test directory. The current
implementation uses `NestedActiveDirectoryGroupType`, lowercase full group DNs,
explicit map order and revocation; normalization follows Red Hat's mapping
examples without depending on a case-sensitivity feature flag.
