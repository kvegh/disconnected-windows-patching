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
