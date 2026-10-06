# Disconnected application deployment

Windows patching uses WSUS. Application deployment uses Chocolatey CLI on managed
Windows guests and Nexus Repository Community Edition on both repository guests.
Chocolatey CLI is invoked by AAP over WinRM; it is not a polling management service.

| Location | Components | Purpose |
|---|---|---|
| External repository guest | WSUS, Nexus, hosted `chocolatey-staging` feed | Connected update acquisition and application package staging |
| Internal repository guest | WSUS, Nexus, hosted `chocolatey-released` feed | Imported updates and released application packages |
| Managed Windows guests | Windows Update client, Chocolatey CLI | Install updates and specific application versions under AAP control |
| AAP execution environment | WinRM dependencies and Windows/Chocolatey collections | Run configuration and deployment jobs |

Packages must contain installers and dependencies, or reference binaries hosted
inside isolation. A public Chocolatey package may contain an Internet download
script; copying that wrapper alone is insufficient. The intended workflow is to
prepare packages externally, test them, transfer exact versions to internal Nexus,
and deploy a versioned package manifest through AAP. The two feeds provide staging
and release separation; they do not automatically create Satellite content views.
Hosted feeds prohibit overwriting an existing version (`ALLOW_ONCE`).

## AAP connectivity to isolated endnodes

The managed guests have one NIC on an isolated libvirt network. Internal WSUS has
a second NIC on the management LAN, but neither Ansible nor WinRM automatically
uses it as a jump host. AAP's execution node, where the job actually runs, needs
network access to each guest's WinRM HTTPS port. The current VM deployment does
not establish that path.

Two possible arrangements preserve the clients' single isolated NIC:

- Run an AAP execution node with management connectivity and access to the isolated
  network. The hypervisor already has an interface on the isolated bridge and is
  a candidate, subject to validating execution-node deployment and container
  network access. Restrict client Internet access and do not enable network
  forwarding merely because the node is connected to both networks.
- Provide an explicit, restricted management route through the hypervisor, with
  a return route and firewall rules permitting only required management traffic.
  This entails routing configuration, which the demo has not selected.

An execution node on the isolated side fits the current preference to avoid
setting up a router. Registering that node, assigning an AAP instance group, and
verifying WinRM connectivity are outstanding work, not changes made by this
playbook. Clients retrieve packages from internal Nexus directly over the isolated
network. Transfers and server configuration use the WSUS guests' management
connectivity; no general client Internet access is needed.

## Deploy repository services and clients

`setup_chocolatey.yml` installs Nexus as a Windows service on both WSUS
servers, initializes its administrator password on first start, creates the
hosted feeds, opens source-scoped TCP port 8081 rules, and installs Chocolatey CLI
on managed guests from an offline MSI. It removes the default public Chocolatey
source and configures the authenticated internal NuGet v2 source.

This is an initial-install playbook. It refuses to reuse a Nexus service pointing
to a different distribution, does not upgrade an existing Chocolatey installation,
and does not build packages, transfer repository contents, or install applications.
Unexpected enabled Chocolatey sources cause failure for explicit review. Source
passwords are set when the source is created; credential rotation is separate.
Existing Windows/IIS rules are not narrowed by the added firewall rule.

Stage installers inside the job's execution environment before launch, using a
read-only mounted artifact directory or a preceding preparation step. Paths are
local to the execution environment, not the controller filesystem or Windows
hosts. Do not commit installer binaries or environment-specific variables.

Use the same disjoint inventory groups as WSUS configuration: `wsus_external`,
`wsus_internal`, and `windows_managed`, as children of the `windows` parent group.
Use AAP Machine credentials for WinRM. Store Nexus passwords and client source
credentials in AAP custom credentials or Vault-encrypted variables; secret-bearing
tasks suppress their output.

| Input | Scope | Meaning |
|---|---|---|
| `nexus_windows_archive` | Job | Execution-environment path to official Windows ZIP, version 3.87 or later with bundled Java |
| `nexus_archive_sha256` | Job | Verified archive SHA-256 |
| `nexus_distribution_directory` | Job | Exact `nexus-...` directory name within the ZIP |
| `chocolatey_msi` | Job | Execution-environment path to official Chocolatey CLI MSI, version 2 or later |
| `chocolatey_msi_sha256` | Job | Verified MSI SHA-256 |
| `nexus_admin_username`, `nexus_admin_password` | Each WSUS host | Nexus credentials; first-start bootstrap uses the built-in admin account |
| `nexus_allowed_sources` | Each WSUS host | Allowed client/AAP/transfer source addresses or subnets |
| `chocolatey_internal_source_url` | Managed group/job | Internal Nexus NuGet v2 URL, ending in `/repository/chocolatey-released/` |
| `chocolatey_source_username`, `chocolatey_source_password` | Managed group | Internal repository read credentials; demo may use the supplied internal admin credential |

Optional job extra variables: `nexus_install_root` (default `C:\Nexus`),
`nexus_data_directory` (default `C:\NexusData`), and per-server host variable
`nexus_feed_name`. Port 8081 is fixed for this initial deployment. Client
traffic uses HTTP for this demo; HTTPS termination and production repository
access controls are separate configuration. Administrative API calls run locally
on each WSUS host, with their responses protected by `no_log`.

The script uses Sonatype's service installer and Chocolatey's MSI bootstrap.
It does not change PowerShell execution policy or disable security controls.

## Resources and pending validation

Both WSUS/Nexus guests use 2 vCPUs and 8 GiB RAM for this demo; managed guests
retain 2 vCPUs and 2 GiB RAM. These are demo allocations below the published Nexus
repository guide's 4-core/16-GB sizing. Validate service startup and shared WSUS/Nexus
memory use under the demo workload. Review the chosen Nexus release's JVM defaults
before deployment. The VM deployment sizing applies to newly created guests;
existing VMs are not resized by these playbooks. Disk capacity must cover
Windows, WSUS content, Nexus data,
and free space; Nexus requires at least 4 GB free to avoid database read-only mode.

Dependencies:

```bash
ansible-galaxy collection install -r collections/requirements.yml
ansible-playbook -i inventory.ini setup_chocolatey.yml --syntax-check
```

The execution environment also needs `pywinrm` and ansible-core 2.18 or later
for the pinned Chocolatey collection. Install/data directories must not contain
spaces. Local syntax checks used ansible-core 2.16 and reported the Chocolatey
collection compatibility warning; the deployment EE must meet the 2.18 requirement.
No Windows guest execution or
live Nexus API test has been performed. First deployment must validate the chosen
archive layout, service installation, startup, password bootstrap, feed access,
and client installation. Execution-node connectivity is a prerequisite.

## Implementation status and remaining work

- Implemented: WSUS configuration and managed-client Windows Update policies.
- Implemented: Nexus Windows service installation on both WSUS guests, hosted
  staging/released feeds, and offline Chocolatey CLI bootstrap on endnodes.
- Validated locally: YAML and Ansible syntax, including Nexus task includes.
- Pending: live Windows/Nexus/Chocolatey validation with the selected installers.
- Verified: WinRM connectivity from the AAP execution node to all Windows guests.
- Pending: AAP-controlled package replication/promotion from external Nexus to
  internal Nexus. Retrieve selected `.nupkg` files, verify checksums, and upload
  the same versions to the released feed; include all offline dependencies.
- Pending: package preparation and an AAP application deployment playbook driven
  by a versioned manifest. A hosted NuGet feed is the Nexus repository format;
  no separate NuGet server or Chocolatey.Server installation is required.
- Pending: WSUS product selection, synchronization, approvals, update-content
  transfer, metadata export/import, and patch installation.

The deployment workflow creates the four VMs in parallel, then runs
`configure_windows_server_basics.yml`, `setup_wsus.yml`, and `setup_chocolatey.yml`
in sequence. Configuration stages are also separate AAP job templates for reruns
on existing guests. Chocolatey setup requires the staged installers and protected
inputs described above; it has not yet been executed. Installing Nexus and creating
feeds does not populate them or implement automatic replication.

References:

- [Nexus Windows service installation](https://help.sonatype.com/en/run-as-a-service.html)
- [Nexus distribution downloads](https://help.sonatype.com/en/download.html)
- [Nexus sizing and storage requirements](https://help.sonatype.com/en/sonatype-nexus-repository-system-requirements.html)
- [Nexus REST API](https://help.sonatype.com/en/api-reference.html)
- [Chocolatey MSI and offline installation](https://docs.chocolatey.org/en-us/choco/setup/)
- [Offline application packaging](https://docs.chocolatey.org/en-us/guides/create/recompile-packages/)

## Repository server naming

Both repository guests provide WSUS and a Nexus feed for Chocolatey. Their VM names
and planned Windows hostnames are stored in the umbrella's vaulted network mapping,
with both services explicitly recorded. Apply those names through `vm_name` and
`windows_hostname`; actual assignments remain outside plaintext documentation.
Keep the existing WSUS inventory groups and role selector for playbook compatibility.

## Parallel setup workflow

Windows basics is followed by `prepare_repository_servers.yml`, which installs
repository Windows features and bootstraps the offline Chocolatey MSI on clients,
finishing all required reboots. `setup_wsus.yml` and `setup_chocolatey.yml` then run
in parallel. Their standalone templates retain the shared bootstrap tasks. Stage
the verified MSI before preparation and the Nexus ZIP/credentials before the
application branch. The WSUS branch proceeds independently through sync, export
and import; see [WSUS data flow](wsus-data-flow.md).
