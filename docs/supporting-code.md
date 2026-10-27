# Supporting code: reasons and boundaries

## TLDR

AAP executes the Ansible playbooks. Python and PowerShell support specific
artifact, platform API, validation and recovery operations described below.
Comments in each asset and its Ansible execution point link to the relevant
reason. Tests have their own [language and coverage guide](../tests/README.md).
This inventory is part of the ongoing review, not a final acceptance report.

Use native collection modules for deployment state when they cover the required
behavior. A script needs a concrete reason, bounded inputs, truthful change and
failure reporting, and functional evidence. Keep credentials in AAP credentials
or Vault inputs; protect temporary sensitive files and remove them on completion.

## WSUS server operations

PowerShell accesses the Windows WSUS administration API for synchronization,
metadata export/import, update dependency closure and approval changes. The
pinned collections do not expose the same complete server-side monthly-content
policy and verified transfer protocol. `win_updates` handles client updates,
not this server-side workflow.

| Assets | Purpose and reason |
| --- | --- |
| `sync-external-wsus.ps1` | Configure the declared products/languages/classifications, wait for synchronization and report actual server readiness. |
| `export-external-wsus.ps1` | Export metadata and selected payload identities into a snapshot with a verified manifest. |
| `prepare-wsus-import.ps1` | Validate metadata, content hashes and disk requirements before an import; queue only missing or mismatched payloads. |
| `import-wsus-metadata.ps1` | Invoke the supported WSUS metadata importer and verify its result. |
| `wsus-patch-month-functions.ps1` | Share dependency/bundle closure, content accounting and month-policy comparisons between operations and tests. |
| `prepare-wsus-patch-month.ps1`, `set-internal-wsus-patch-month.ps1` | Prepare and enforce the selected month with server-side update approvals and prerequisite checks. |

The inline WSUS initialization/readiness checks in `setup_wsus.yml`,
`check_wsus_prerequisites.yml`, `export_external_wsus.yml` and
`tasks/validate_windows_patch_ceiling.yml` inspect server-native state that must
agree with these operations. Ansible manages Windows features, files, ACLs,
firewall rules, transfers and asynchronous waits around them. Do not replace
these controls with unrestricted remote shell calls.

## Windows inspection and evidence

PowerShell can query registry, CIM, Windows Update Agent COM, servicing state and
Windows event/history APIs together without parsing localized command output.
These collectors report observed state and set `Ansible.Changed` to false.

| Assets or inline operation | Reason |
| --- | --- |
| `assess-windows-patch-level.ps1`, `inspect-windows-update-client.ps1` | Compare the observed OS/build/update-source configuration with explicit expectations. |
| `search-managed-windows-updates.ps1` | Read managed-server offers in the restricted WinRM context; retain exact observed title patterns and reboot evidence without installing updates. |
| `show-windows-demo-proof.ps1` | Serve the same live evidence to AAP and the desktop, including package-operation chronology rather than just current versions. |
| `tasks/record_windows_demo_application_state.yml` | Retain receipts only after live native-module verification and bind the evidence to the current machine identity. |
| `inspect_active_directory_guest.yml`, `inspect_windows_network.yml` | Collect diagnostic snapshots and parse PowerShell syntax without modifying the guest. |
| `tasks/deploy_windows_demo_proof.yml` | Create the desktop shortcut through Windows Shell COM, verify its actual properties and exercise the real PowerShell file entry point. |

These checks do not establish universal OS compatibility. Run them in the
documented Windows lab; record unavailable diagnostics and missing history as
limitations. A collector succeeding does not prove update installation or a
complete deployment.

## Windows networking and activation

`configure-static-network.ps1` matches NICs by MAC, validates every requested
adapter before writes, and manages address, DHCP/default-route and forwarding
state in active and persistent stores. The currently pinned route module does
not cover the required interface-specific DHCP-route behavior. DNS, hostname and
registry settings use native modules outside this script.

`run-network-configuration.ps1` is the short local runner for that operation. It
records errors and change status atomically while Task Scheduler keeps the
operation alive through the expected WinRM address change. Its protected working
directory and actual task completion/exit code are checked by Ansible. See the
[networking design](../README.md#networking-modules-and-remaining-powershell).

`windows-evaluation-activation.ps1` uses the installed evaluation's licensing CIM
method and checks network state. The Ansible playbook bounds temporary exposure
and cleanup; a hypervisor systemd timer invokes two narrowly scoped `virsh`
operations as a fallback when the controller cannot finish cleanup. The shell
receives the validated domain and this operation's generated MAC as positional
arguments. It must preserve every original interface. See the
[activation safeguards](windows-evaluation-activation.md).

`configure-winrm-https.ps1` is a manual image-preparation utility for a host that
does not yet accept Ansible connections. It requires an administrator at the
console, an explicit management-source address and separately configured
certificate trust. It is outside the automated deployment and is not claimed
idempotent; it refuses an existing named firewall rule. The deployment assumes
prepared base images and must not silently execute this utility or weaken trust.

## Artifact creation and Nexus upload

`build-offline-chocolatey-package.py` and `create-chocolatey-export.py` use Python's
standard library to produce deterministic NuGet-compatible ZIP/XML/multipart
bytes and verify selected installer/package hashes and offline hooks. Ansible
orchestrates acquisition, repository state, transfer and installation; the
pinned collections do not provide this deterministic package builder. A repeat
build reports change only when artifact bytes differ.

`upload-nexus-package.ps1` streams a previously verified binary package through
.NET multipart HTTP to the local Nexus API. The pinned Windows HTTP module does
not expose the required binary file-upload operation. It refuses redirects and
validates the expected response, avoiding command-line credentials and binary
text conversion. `validate-chocolatey-export.ps1` checks the archive/manifest
boundary before publishing imported packages. See the
[application pipeline](application-deployment.md).

The generated `chocolateyInstall.ps1` hook is part of the NuGet package format.
It verifies the embedded installer and invokes the Chocolatey installation API
without fetching another installer from the Internet. Its Python builder is the
execution point and links back to this reason.

## Active Directory and AAP verification

`active-directory-model.py` builds the shared synthetic access model.
`generate-active-directory-profile.py` combines that model with random passwords
and an encrypted dedicated CA/leaf bundle using the existing `cryptography`
library. This is one-time protected profile generation, followed by Ansible Vault
encryption; it must not regenerate credentials during ordinary reconciliation.
Ansible controls file protection and Vault storage.

`configure-active-directory-identities.ps1` reconciles the owned AD tree with
explicit preflight/retirement checks and preserves administrator-added members.
`verify-active-directory-additional-members.ps1` is the opt-in integration probe
for that preservation contract and removes only its verified owned fixtures.
Native AD cmdlets keep these comparisons and writes within the directory host;
Ansible handles connection changes, features, DNS, certificates and workflow.

Forest creation and its reboot now use the native
[`microsoft.ad.domain`](https://docs.ansible.com/projects/ansible/latest/collections/microsoft/ad/domain_module.html)
module with explicit Server 2025 functional levels. The remaining readiness and
LDAPS probes use Windows AD/certificate APIs to verify the actual service and
trust boundary. Native `microsoft.ad.user`, `group` and `ou` modules also exist.
The identity batch retains its combined ownership, retirement and
additional-member guarantees; a future conversion must preserve those behaviors
and justify its change/test effort. Live revalidation and the final review must
record whether that retained implementation is an accepted deviation. Do not
claim there are no native AD alternatives.

`inspect-aap-ad-migration.py` discovers owned IDs and rejects foreign references
before native AAP modules reconcile them. `verify-aap-ad-regions.py` checks the
complete object-access matrix using each synthetic identity and waits for jobs
it launches, including failure cleanup. A single injected request interface lets
offline tests exercise the same verifier. Its direct HTTP client must retain
CA/hostname validation, reject redirects and avoid leaking credential material.
Native AAP modules continue to create and update the declared platform objects.

The gateway trust checks run Python's normal SSL context inside the actual
existing gateway container so they verify that runtime's CA bundle and LDAPS
hostname/chain checks. Ansible obtains the expected container/mount metadata and
manages the trust files; the probe must not disable certificate verification.

## Hypervisor inspection and recovery

`inspect-activation-domain.py` normalizes live and persistent libvirt XML while
retaining meaningful topology differences. The inline Python in baseline,
reservation and guarded teardown playbooks performs structured XML, subnet and
ownership comparisons before any mutation. A generic domain deletion operation
does not provide the combined marker, exact disk, sharing, backing-file and
unrelated-resource preservation checks. Ansible controls the sequence and
validated `virsh`/disk operations. Their safety still requires live verification.

`hypervisor-memory-report.py` samples Linux memory, swap, pressure and KSM counters
with a monotonic interval. Ansible's ordinary memory facts do not provide this
combined rate/KSM snapshot. It is diagnostic and changes no host tuning.
Do not treat KVM/libvirt as a requirement for every project: it is this demo's
implemented provisioning backend and the available lab's test boundary.

## Immediate connection refresh

The Chocolatey bootstrap's narrowly scoped `no-handler` exception keeps
`meta: reset_connection` immediately after a changed MSI installation and any
required reboot. Subsequent tasks need the refreshed Windows environment in the
same included task sequence. Deferring that connection control to play-end
handlers could run dependent work against the old environment. The reset remains
conditional and does not reinstall Chocolatey. Host CA trust and Windows Update
service changes use notified handlers flushed before dependent verification.
