# Selected-instance Windows runtime

The private companion repository supplies one reviewed runtime profile for each
prepared AAP instance. The CaC importer resolves the selected inventory entry to
its existing verified physical instance identity. Importing an instance without a
prepared Windows profile fails before any resources are changed.

The profile binds five Windows computer names, their image versions, unique MACs,
permanent addresses, libvirt networks, the independent AD forest and certificates,
repository settings, activation settings and exact teardown scope. Computer names
are limited to fifteen characters. Existing captured network reservations are
preserved; new guests receive distinct names, NICs and reservations.

The private capture stores runtime settings as one opaque, whole-file Ansible
Vault string in each job template's saved variables. Every runtime template uses
the existing Windows Playbook Vault credential. An execution-environment task
writes only ciphertext to a private temporary file, uses native `include_vars`
decryption, validates the selected instance and fixed setting names, then removes
the temporary file. No new credential type, secret store, wrapper playbook or
external service is involved. Secrets do not become individual launch variables.

The selected existing hypervisor Machine credential supplies SSH authentication.
Before any hypervisor operation, the loader installs independently verified host
keys, fixes the selected address and port, and compares `/etc/machine-id` with the
private profile. VM creation also checks the exact declared name, version and NIC
mapping. DHCP and DNS changes reject conflicting or shared records and preserve
unrelated network definitions.

The owner explicitly retained the existing Windows demo connection policy:
HTTPS on port 5986, NTLM authentication and `server_cert_validation: ignore`.
The selected profile uses those existing Ansible settings and credentials. It
requires neither a WinRM CA nor an added certificate-bootstrap, console or image
inspection before the normal jobs. Their existing `wait_for_connection` and
authenticated Windows commands still have to succeed. This Windows-only lab
exception does not change AAP HTTPS, LDAPS or pinned hypervisor SSH validation.

Profiles selecting `validate` retain the stricter path: the loader requires the
selected public CA and writes it to a private execution-environment file before
using normal hostname/issuer validation. No policy flag, secret store or fallback
is added. The current selected profile no longer carries the extra inspection
readiness value introduced during preparation.

Legacy project-local encrypted profiles and behavior remain intact for existing
jobs that do not select the new runtime transport. Their encrypted copies are
retained in the private companion. Prepared versioned CaC imports use only their
explicit private instance profile; they never fall back to inherited targets.

## Infrastructure includes its AAP management connection

The original captured topology includes an AAP interface on the Windows isolated
network. Fresh versioned AAP deployments initially retain their primary network
only. For a prepared Windows profile, `01-win-vm-setup.yml` now establishes the
explicitly selected AAP VM's second NIC and persistent RHEL connection before
creating Windows clones. The existing AD creation playbook imports that same
entrypoint. Exact selected clone/survey inputs, existing VM/disk refusal and
read-only image/network/destination checks run before management preparation.
Invalid legacy VM names therefore fail before an OS/network write. Omitting the
optional encrypted connection profile preserves legacy behavior. The API-only CaC importer installs definitions and never changes NICs.

The private profile holds the immutable registered AAP route and eight primary
ownership fields, plus one Windows-owned NIC/connection declaration. Its static
address is outside the existing DHCP pool and distinct from every selected guest.
Fresh native checks reject conflicts in both domain/network definitions, leases,
reservations, host addresses and neighbours. The isolated bridge has no forward
configuration. The playbook adds no DHCP/DNS record for the AAP NIC, gateway,
forwarding rule, firewall exception, execution node or proxy.

The existing hypervisor Machine credential authenticates pinned SSH. Only the
existing AD Target credential's OS SSH username, password and independently
verified host keys are used for AAP OS configuration. They must match the
selected route's public SSH keys. The guest's real DMI UUID and machine-id are
read before changes; neither API/admin-password fallback nor key installation is
allowed. The existing source API reader, source CA, Git writer and two Vaults
support the same shared publisher. These existing references are added only to
the infrastructure, AD creation and post-teardown templates; other assignments,
credential definitions and secret values are unchanged.

Before hotplug, the job captures protected primary addresses, routes, resolver
bytes and all existing persistent NetworkManager settings. It refuses a foreign
unbound autoconnect Ethernet profile, then creates the exact manual profile bound
to the future NIC MAC. NetworkManager can therefore select the intended disk
profile when that device appears. This follows its documented
[automatic-default selection](https://networkmanager.dev/docs/admins/) and
[Ethernet MAC binding](https://www.networkmanager.dev/docs/api/latest/settings-802-3-ethernet.html).
No global NetworkManager setting changes. The profile has manual IPv4, no gateway
or DNS, no automatic DNS, no default route and disabled IPv6. Authenticated final
readback checks the persistent policy, actual address and absent IPv6/default
routes. All meaningful primary settings stay exact; only naturally decreasing
address lifetimes and route expiry are excluded from comparison.

One protected checkout of the fixed shared AutoDeploy implementation remains
alive for source planning, native work, publication and any fresh ownership
readback. Its existing `recovery_guest_release` role supplies the `plan` entrypoint
and `aap_supplemental_interface` transaction. Ownership is stored in the existing
AAP resource and mirrored main-inventory record, preserving primary fields,
route and the entire firewall policy. There is no extra registry or publisher.

Native component locks serialize identical jobs. A matching unpublished profile
from another job is not adopted; the caller waits and refreshes canonical state.
A failure may undo only components this job actually created, and only after a
fresh authenticated canonical read proves no job durably published them. If that
read is uncertain or publication succeeded, components remain for a safe retry.

The same existing native lock covers the first standalone clone conversion and
teardown's final check of all five Windows names and derived clone paths before
NIC detach. If cloning wins, its disk prevents cleanup. If cleanup wins, cloning
refuses a missing management NIC before disk or reservation writes. All selected
DHCP/DNS reservations occur after that protected disk exists and before boot;
the selected fresh AD address stage defers to this same path. Legacy reservation
and recovery behavior stays unchanged.

On a network whose actual XML disables DNS, the reservation helper manages exact
DHCP names and addresses but requires no matching DNS host record. Enabled DNS
continues to require both records. The shared release/retirement pin below
verifies the same distinction; this never enables a DNS service.

If a selected provisioning job stopped after its disk copy but before VM creation,
the same entrypoint can retain that copy. Before each such attempt, the existing
`recovery_guest_retire` **plan** entrypoint reads current encrypted ownership and
the source AAP's main inventory; it must find no guest ownership. It performs no
deletion or publication. Under the existing native component lock, the clone
operation then requires a root-owned regular single-link standalone disk, no
live/persistent domain reference or guest permission, original virtual capacity,
and successful logical-content comparison with the unchanged golden image.
Only that pristine unused copy is retained without another conversion. A changed,
registered, referenced or linked disk remains a stop; legacy behavior is unchanged.

The baseline records the optional exact management declaration. After all five
Windows clones/disks are absent and unrelated definitions, states and golden
metadata pass preservation checks, the existing post-teardown playbook removes
only the declared owned NIC, then its OS connection. It validates current owned
addresses and policy first, supports an interrupted retry with the exact profile
but NIC already detached, and publishes removal through the same transaction.
The final XML comparison permits only that exact supplemental NIC removal.
Preexisting/shared or ambiguously owned interfaces and connections are refused.
The full AAP decommissioner separately recognizes the same saved supplemental
record; this component does not stop or delete the AAP VM.

The selected live test has created all five guests and completed the four regular
baselines, AD preparation and real LDAP permission verification. WSUS content and
the April ceiling passed. Both managed Windows versions reached their exact April
baselines without remaining approved updates or reboot. Nexus package
synchronization/export/import, baseline installation and upgrades also passed.
The subsequent selected Windows-only teardown passed final verification 435,
preserving four core guests and two golden images. A fresh unattended full
workflow remains unverified.
Successful CaC import alone does not establish those runtime outcomes.

## Migrating the selected workflow graph

The selected private capture declares twenty-nine workflow nodes. An existing
Controller can still contain four inherited creation nodes with legacy inputs
alongside the four selected replacements: the CoP workflow update matches nodes
by identifier and does not implicitly remove the obsolete identifiers.
A successful CaC import therefore also needs an exact graph comparison before
this workflow can be launched; checking the template count alone is insufficient.

For the reviewed migration, retain the existing workflow and every Job Template,
compare the actual graph with the private selected graph, and preview only the
four proven obsolete creation nodes and their existing edges. Require no active
owned workflow/jobs or enabled schedules. The coordinator can then remove just
those Controller template nodes and verify the selected twenty-nine-node graph.
There is no blanket node destruction, replacement workflow or new removal
mechanism. The current private desired graph already omits the four inherited
identifiers, so a normal reimport must not recreate them. Actual migration
identities and review evidence stay in protected records.

## Release after verified per-VM configuration

The server-basics job checks Windows identity after its permanent networking,
scheduled network-task result, hostname and required reboot have succeeded.
The AD preparation job performs the same check after its hostname and explicit
update-source configuration, before public update downloads. Release is limited
to complete, unskipped normal runs. Later patch, application and directory
functional tests remain separate acceptance steps.

The proof reads the actual computer name, CIM product UUID, Server build and
every active NIC's MAC and permanent IPv4 address through authenticated HTTPS
WinRM using the selected policy. It refuses inherited foreign domain membership
or update-service URLs.
Pinned SSH then reads both native domain definitions, the existing instance
owner marker, independent clone disk and actual network bridges. The shared
Windows resource is produced only when the observed computer UUID equals the
native domain UUID and every interface matches. No Linux machine identity or
SSH identity is invented for a Windows guest.
The existing `winrm_certificate_validated` field records the truthful Boolean:
`false` for the approved lab setting and `true` for certificate validation.
Authenticated commands and successful native identity proof are required in
both cases.

Within that same job, a temporary checkout of the fixed public AutoDeploy
repository at a reviewed forty-character revision supplies its existing
`recovery_guest_release` role. The role owns the existing policy/publication
transaction and preserves production exclusions and unrelated permissions. The
checkout and temporary hypervisor trust file are removed on success or failure.
There is no second publisher, extra orchestration job or Windows bootstrap
HTTPS exception.

The current pin is AutoDeploy 0.45.3 implementation
`3f5c7e253133d9b25e7a213cdb45bebdabca3f17`. Its existing Windows branch accepts
the genuine Boolean certificate result under the owner's lab policy while
retaining every successful identity, ownership and source/policy check. It also
retains the canonical Controller SSH-port representation fix; different or
malformed ports still fail. The same reviewed implementation supplies the plan
entrypoint and exact supplemental-interface ownership transaction, preserves
existing primary identities, and resolves action support code from the current
checked-out role when one job invokes it repeatedly.

The existing reset jobs use the same retirement role. Its `tasks_from: plan`
entry point reads actual canonical/source ownership before the destroy job selects
typed Windows retirement or the strict unconfigured-clone path. Missing records
remain null in both templating modes. See the [run/reset sequence](../README.md#teardown-verification)
for the original core baseline, LDAP-before-regional cleanup and final NIC removal.

These two jobs use the existing hypervisor Machine credential for pinned SSH.
Server-basics binds only its guest connection to the already-encrypted bootstrap
login; AD preparation retains its existing protected initial login and subsequent
domain authentication logic. Other runtime jobs are unchanged. The existing
source API reader, source CA, central Git writer, central CaC Vault and Windows
Playbook Vault support the same publisher. Their existing distinct Vault
identities and passwords are preserved; native supported-EE checks prove both
current unlabeled ciphertexts load without a Vault matching override.

Offline and cached-EE checks do not prove a Windows TLS handshake, successful
guest configuration, live isolation release or completed functional test.

## Scoped authentication cleanup component

The existing `configure_aap_ad_trust.yml` playbook supports `ad_trust_state:
absent` for a selected private instance. It requires the exact five-clone
`windows_decommission_preview` and a Boolean `windows_decommission_apply` flag.
The default `false` collects protected LDAP/CA ownership evidence without
removing anything. An approved `true` run uses native platform collection modules
to remove the owned maps, then captured LDAP-exclusive test users, then their
authenticator. Captured IDs/names, original-baseline exclusion and absence of
foreign or elevated grants are required; unknown provider users stop removal.
It verifies built-in and unrelated authentication IDs remain, then removes only
the matching CA anchor and exact marked block from the gateway bundle. The AAP
guest's SSH keys and libvirt product UUID are verified first. Changed, shared or ambiguous
ownership fails closed.

Trust-removal job 412 and regional-resource removal 417 passed. The existing
per-guest destroy jobs subsequently verified five retirements, and final job 435
verified all owned resource absences before removing the recorded supplemental
AAP connection. No additional Job Template or automatic cleanup trigger is added.

## Verification and remaining acceptance

Offline checks cover wrong-instance documents, unreviewed variable injection,
duplicate NICs/addresses, invalid machine pins, Windows name limits, selected
WinRM policy and conflicting/shared network records. Native encrypted-loader
tests accept `ignore` with no CA and require a CA for `validate`. Syntax checks cover every saved
runtime playbook. Private capture checks render the selected resources and reject
unprepared destinations while preserving literal credential injectors.

The selected live run separately proved authenticated WinRM, approved network
access, patching, application upgrades and real LDAP permissions. The existing
baseline, trust/resource removal, guarded clone removal and final verification
jobs also completed the selected reset, including owned inventory, reservations,
permissions and supplemental AAP networking. The first guest required a
separately user-approved exact orphan-disk unlink after an interrupted deletion;
later normal retirements and final verification passed. This staged acceptance
does not prove an unattended fresh full workflow, and the proposed future
basics/activation ordering change remains unapproved.
