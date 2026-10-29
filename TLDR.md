# Disconnected Windows demo: TLDR

AAP provisions a small Windows lab, acquires WSUS updates and pinned application
installers on the connected repository, transfers verified content to the
internal repository, and patches/upgrades the managed Windows servers from
internal sources. The interactive [walkthrough](https://kvegh.github.io/disconnected-windows-patching/)
explains that sequence; it is an illustration, not live execution evidence.

## Supported scope

- The implemented provisioning backend is KVM/libvirt with prepared Windows
  base images. VMware and arbitrary virtualization backends are outside this
  implementation and the available test environment.
- Four core Windows clones: connected repository, internal repository, Server
  2022 managed endnode and Server 2025 managed endnode.
- The optional AD extension adds one Windows Server 2025 domain controller and
  uses a separate existing AAP test platform for identity/access demonstrations.
- This is a simulated disconnected network with explicit management paths.
  Documented provisioning, content acquisition and evaluation activation have
  different connectivity requirements. It is not a general air-gap certification.
- Windows disks, adapters, paths and preconfigured WinRM must match the declared
  image/inventory contract. This project does not test every Windows edition,
  locale, platform, authentication method or network layout.

The owner permits resetting only the owned Windows demo VMs. Preserve the Linux
AAP platforms, unrelated VMs and original images. A whole-host preservation
baseline contains unrelated domains; it does not make those domains demo targets.

## Execution and inputs

Run the normal AAP job templates/workflow using the actual supported EE and the
project's pinned collections from private automation hub. The review baseline
is ansible-core 2.16.19 in the deployed AAP EE; collection metadata must support
that version. No custom EE is currently required by this review.

Store actual credentials and environment mappings in AAP credentials, private
inventory variables or Vault inputs. Keep controller objects reproducible through
CaC. Collection releases belong in private automation hub, with dependency pins
in `collections/requirements.yml`; do not copy collection source into this repo.

## Demonstration sequence

1. Check the inventory/image contract, available resources and protected inputs.
2. Provision the owned Windows clones and complete native connectivity smoke
   checks before configuring their permanent identities and networking.
3. Prepare WSUS and Nexus, synchronize external content, export verified
   snapshots and import them into the internal repository.
4. Enforce the selected OS patch month, patch the managed servers, then install
   the pinned application baseline and upgrade it to the current feed versions.
5. Query the live proof report. Current versions alone do not establish a past
   baseline-to-upgrade sequence; missing history remains unproven.
6. Run the optional AD workflow and access-matrix verifier when that extension
   is included in the declared test scope.

Fresh replay may require the guarded Windows-only teardown because an upgraded
endnode deliberately refuses an implicit application downgrade. Capture and
verify preservation evidence around that reset.
The default capture covers four owned Windows targets. Set
`windows_demo_include_ad: true` with an exact five-target list to include AD.
Fresh baseline artifacts bind that target list and record ownership markers;
old unbound artifacts cannot be used for verification.

## Review and evidence

Review acceptance is incomplete. Both recorded core runs passed all 21 core
stages on the 1.0.7 revision. The combined run's AD creation did not start because
its project sync failed during the platform outage. The 1.0.8 client fix is
offline-tested; a complete combined AAP run remains required for acceptance.
The version file identifies cleanup patches; it does not certify acceptance. See the [test guide](tests/README.md) for Python,
PowerShell and JavaScript checks and the
[supporting-code rationale](docs/supporting-code.md) for every retained language.
The [quality assessment](docs/review-quality-assessment.md) records agent
judgments on readability and simplicity; the
[requirements/deviation record](docs/review-requirements-and-deviations.md)
separates accepted minor deviations from unresolved acceptance requirements.

`verify_windows_regressions.yml` provides native Ansible orchestration for the
six mocked PowerShell suites on the two endnodes. These regressions complement
live service validation and the complete scoped AAP end-to-end workflow.

After findings are fixed in a batch, run functionality tests, restart the full
review, and finish with the end-to-end test. Only then create the dated
`Code_Review_YYYY-MM-DD.md` report with actual functionality confirmation,
conflicting guidance and choices, accepted deviations and untested scope.

Use the [README](README.md) for setup and template details, the
[WSUS data flow](docs/wsus-data-flow.md), the
[application pipeline](docs/application-deployment.md), and the
[AD presenter guide](docs/active-directory-demo-guide.md) for the detailed paths.
