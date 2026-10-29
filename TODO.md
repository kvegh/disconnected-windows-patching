# Demo TODO

## Code review checklist

This is the complete review worklist, organized by the 15 sections of the
[review policy](https://github.com/kvegh/Agent_generated_code_review/blob/e45b49b/README.md).
A checked item means the stated assessment is completed, including documented
deviations. An unchecked item identifies remaining evidence or a decision; it
does not automatically identify a code defect. Each open item can close through
verification, a focused correction, justified non-applicability or a documented
accepted deviation. Discuss the open CoP topics below individually.

- [ ] **R01 — Whole CoP guide:** close CP01–CP09 below. All 13 areas and 310
  trace entries are already accounted for; mapping alone is not full acceptance.
- [ ] **R02 — Red Hat and CIS guidance:** Red Hat development guidance has been
  consulted. Select the applicable CIS benchmark/profile/controls and record the
  assessment or a proportionate scoped disposition. No host compliance claimed.
- [ ] **R03 — Actual AAP core and deprecations:** core 2.16.19/Python 3.12.14
  and compatible collection pins are verified; deprecated authored module usage
  was replaced. Record a final disposition for the vendor-owned Python `crypt`
  warning without independently upgrading the supported Ansible runtime.
- [x] **R04 — Readability, simplicity, naming and comments:** explicit
  [source assessment](docs/review-quality-assessment.md) and naming/style
  deviations documented; no human readability sign-off required.
- [x] **R05 — Native Ansible and content selection:** suitable native modules,
  certified/community provenance and retained alternatives assessed;
  [foreign-code reasons](docs/supporting-code.md) and linked comments documented.
- [x] **R06 — Idempotency, failure handling and recovery disposition:** source
  safeguards, focused negative tests and selected repeat applies assessed. The
  owner skipped additional idempotency verification (CP01) and further complete
  rollback verification for this demo (CP05). Unperformed checks are not passes.
- [ ] **R07 — Credentials and security:** protected inputs and secret scanning
  assessed. WinRM certificate checking and WSUS HTTP are owner-accepted lab
  deviations; historical usernames are closed. CP06/CP07/CP09 cover distinct
  remaining platform practices and boundary evidence.
- [x] **R08 — Private automation hub:** exact release pins/source availability
  checked; no vendored runtime collections or newly authored collection.
- [ ] **R09 — AAP execution and EEs:** actual normal-template/workflow runtime
  verified. Finish the image/release evidence or disposition in CP03/CP08.
- [x] **R10 — CaCable assessment disposition:** the owner skipped additional
  CaC reconstruction verification for this review (CP02). Existing configurators
  remain; a complete current restore is not claimed as verified.
- [x] **R11 — Speed:** job timings, workflow concurrency and bounded waits
  assessed. No unsupported performance improvement claimed.
- [ ] **R12 — Strict lint and APME:** production lint passed; APME scan and
  triage recorded. Its dependency backend fails on synthetic collection package
  records. Document reliable supplemental coverage and the tooling limitation;
  do not interpret zero returned observations as a clean dependency audit.
- [ ] **R13 — Smoke and functionality tests:** 109 Python tests, 14 browser
  tests, six PowerShell suites and scoped AAP core evidence recorded on their
  respective revisions. The combined functional test belongs to the owner;
  record its exact tested revision/result when supplied.
- [ ] **R14 — Review procedure and dated report:** fix batches, conflicts and
  evidence recorded in the [incomplete dated report](Code_Review_2026-10-29_INCOMPLETE.md).
  Complete the remaining dispositions and evidence before issuing a successful
  review report. Do not invent findings to generate more changes.
- [x] **R15 — Documentation:** README, TLDR, source-quality assessment,
  requirements/deviations, CoP trace, decision history and visual walkthrough
  maintained. Keep this worklist current as decisions are made.

## Open CoP topics to review individually

These are grouped evidence/process questions, not a list of demonstrated
playbook defects. The [directive trace](docs/review-cop-directives.csv) gives
the exact source locations; repeated sections, bullets and examples can point
to the same topic. PR-only checks do not apply to owner-directed main-only work.

- [x] **CP01 — Scoped idempotency evidence: owner skipped.** On 2026-10-29
  the owner chose to skip further idempotency verification in this review.
  Existing repeat-test evidence remains valid within its scope; unperformed
  checks are not passes. Accepted deviation D13. Trace: COP-184, COP-264, COP-239.
- [x] **CP02 — Complete CaC reconstruction: owner skipped.** On 2026-10-29
  the owner chose to skip further CaC reconstruction assessment in this review.
  This does not remove existing configurators or establish a verified complete
  current restore. Accepted deviation D14. Release provenance and CI questions
  remain separate. Trace: COP-223, COP-233–239, COP-249, COP-280, COP-300.
- [x] **CP03 — Release references and provenance: owner skipped.** On
  2026-10-29 the owner declined locking and chose to move on. Keep the current
  main/latest references and existing recorded SHAs/digests. No AAP revision,
  EE, release-tag or manifest change is required for this review. This does not
  guarantee that future runs resolve to identical content. Accepted deviation
  D15. Trace: COP-246–249, COP-280, COP-300.
- [x] **CP04 — Proportionate automated checks: owner skipped.** On 2026-10-29
  the owner chose to move on without adding automated Ansible/pre-commit/CI
  gates. Retain the recorded review checks, existing Pages CI and GitHub secret
  protection. No PR workflow or new branch restrictions are introduced. This
  does not claim automatic Ansible enforcement or waive the owner's functional
  test. Accepted deviation D16. Trace: COP-240, COP-253–254, COP-266–267,
  COP-270–271, COP-287.
- [x] **CP05 — Recovery and rollback boundary: owner skipped for this demo.**
  On 2026-10-29 the owner skipped further complete rollback verification for
  this demo environment. Retain the existing retry/recreation instructions;
  do not claim restoration of every prior machine/data state or add rollback
  machinery for this review. Accepted deviation D17. Trace: COP-281.
- [ ] **CP06 — Least privilege and periodic access review.** Regional RBAC
  tests cover the demo matrix. Verify or explicitly scope remaining AAP service
  account, credential and automation-pipeline permissions and the access-review
  practice. Do not claim an organization-wide audit from regional tests.
  Trace: COP-293–296, COP-306–310.
- [ ] **CP07 — Credential rotation practice.** Check the actual supported
  rotation/revocation process or document the lab's accepted limitation. No
  credential exposure was established, and this item does not authorize changing
  credentials just to demonstrate activity. Trace: COP-298.
- [ ] **CP08 — Vendor EE security evidence.** Record applicable image
  vulnerability and software-component inventory/SBOM evidence, advisory
  applicability, or an explicit scoped disposition. Upstream Python tooling
  findings do not establish that the vendor EE is affected. Trace: COP-299.
- [ ] **CP09 — Intended network boundaries.** Assess the lab's actual
  separation and permitted management traffic against the CoP environment
  segmentation guidance. Document the supported boundary and evidence; do not
  require a new Kubernetes/VPC or enterprise dev/QA/prod architecture. Accepted
  WinRM/WSUS exceptions remain closed. Trace: COP-301, COP-303, COP-305.

APME's dependency-backend failure, the vendor `crypt` warning and CIS selection
also remain in the full checklist above; they are not additional confirmed CoP
playbook bugs. The [requirements record](docs/review-requirements-and-deviations.md)
contains current dispositions and conflicts.

## Existing demo backlog

The entries below retain earlier implementation/follow-up work. Historical
checked items do not replace current revision evidence in the review checklist.

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
- [x] Migrate pinned community IIS modules to microsoft.iis before their upstream removal.

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
  protected-prefix username patterns, new-user Windows steps and multiple permissions per
  mapped AD group.

An access-removal demonstration is outside the requested scope. The presenter
walkthrough covers granting access, automatic first login and role/country
isolation.

Optional later work: compare nested-group lookup performance with the AD
matching rule in chain on a realistically sized test directory. The current
implementation uses `NestedActiveDirectoryGroupType`, lowercase full group DNs,
explicit map order and revocation; normalization follows Red Hat's mapping
examples without depending on a case-sensitivity feature flag.
