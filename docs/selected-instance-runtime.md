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

Initial WinRM trust is a separate prerequisite. A fresh LDAPS CA does not make a
golden image's original self-signed WinRM listener trusted for new names and
addresses. Instance profiles therefore start with `windows_runtime_winrm_ready:
false`. Guest jobs refuse to run until a reviewed bootstrap has installed the
correct certificate and normal HTTPS hostname/issuer validation is configured.
The loader accepts only validated WinRM connections and writes the selected
public issuer into a private execution-environment CA file. It introduces no
certificate-validation exception.

Legacy project-local encrypted profiles and behavior remain intact for existing
jobs that do not select the new runtime transport. Their encrypted copies are
retained in the private companion. Prepared versioned CaC imports use only their
explicit private instance profile; they never fall back to inherited targets.

## Release after verified per-VM configuration

The server-basics job checks Windows identity after its permanent networking,
scheduled network-task result, hostname and required reboot have succeeded.
The AD preparation job performs the same check after its hostname and explicit
update-source configuration, before public update downloads. Release is limited
to complete, unskipped normal runs. Later patch, application and directory
functional tests remain separate acceptance steps.

The proof reads the actual computer name, CIM product UUID, Server build and
every active NIC's MAC and permanent IPv4 address through normally validated
WinRM. It refuses inherited foreign domain membership or update-service URLs.
Pinned SSH then reads both native domain definitions, the existing instance
owner marker, independent clone disk and actual network bridges. The shared
Windows resource is produced only when the observed computer UUID equals the
native domain UUID and every interface matches. No Linux machine identity or
SSH identity is invented for a Windows guest.

Within that same job, a temporary checkout of the fixed public AutoDeploy
repository at a reviewed forty-character revision supplies its existing
`recovery_guest_release` role. The role owns the existing policy/publication
transaction and preserves production exclusions and unrelated permissions. The
checkout and temporary hypervisor trust file are removed on success or failure.
There is no second publisher, extra orchestration job or Windows bootstrap
HTTPS exception.

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
to remove only the exact test authenticator and its recognized maps, verifies
built-in and unrelated authentication IDs remain, then removes only the matching
CA anchor and exact marked block from the gateway bundle. The AAP guest's SSH
keys and libvirt product UUID are verified first. Changed, shared or ambiguous
ownership fails closed.

This component is prepared for the full decommission sequence. Its live use and
the connection to VM, network, inventory and shared lifecycle retirement remain
unfinished. It does not add another Job Template or automatically enable cleanup.

## Verification and remaining acceptance

Offline checks cover wrong-instance documents, unreviewed variable injection,
duplicate NICs/addresses, invalid machine pins, Windows name limits, WinRM trust
gating and conflicting/shared network records. Syntax checks cover every saved
runtime playbook. Private capture checks render the selected resources and reject
unprepared destinations while preserving literal credential injectors.

These checks do not prove a live Windows deployment. Provisioning, Windows trust,
approved network access, patching/application/AD acceptance and complete scoped
decommission must be verified in the serialized test window. The existing
baseline, guarded clone removal and post-removal verification jobs remain the
starting point for decommission; their current implementation does not by itself
remove instance-specific network, inventory, LDAP or shared lifecycle resources.
