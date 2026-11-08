# Per-clone Windows evaluation activation

Windows Server 2022 and 2025 share `01-win-vm-setup.yml`, selected by
`windows_version`. The deployment sequence is:

1. Create the four independent clones.
2. Configure permanent Windows networking, management access and identity.
3. Run `activate_windows_evaluations.yml` for evaluation licensing.
4. Prepare repository services and continue the existing WSUS/Chocolatey pipeline.

The activation stage runs after Windows basics because Ansible must already be
able to reach the guest over its permanent management address. It does not edit
the base image. For prepared instances, basics records licensing without stopping
an expired evaluation before activation; it retains guest isolation. The
activation job checks licensing and restored topology before the existing release
include obtains fresh Windows/native ownership evidence and publishes permissions.
The `hypervisor` inventory target may be a host alias or a group;
the play validates the resolved host count rather than requiring a named group.
Microsoft's evaluation requires Internet activation within ten
days to avoid automatic shutdown, and Sysprep generalization normally resets
licensing timers. Verify each deployed clone rather than assuming the base
image's licensing state is inherited.

## Activation and isolation

The playbook first checks the installed operating-system license and matches
the guest version, permanent addresses, DNS, default routes and adapter MACs to
encrypted configuration. It verifies the domain's demo ownership marker and
that live and persistent libvirt adapters match the protected deployment mapping.
For virtual-network adapters, the comparison excludes only libvirt's generated
live `portid` and resolved `bridge` source attributes. Network identity, other
source attributes, MAC, interface type, model and link state remain checked;
bridge-type adapters retain their source bridge identity.

Already-licensed clones skip licensing calls, Windows update-policy changes,
temporary adapters and cleanup timers. Prepared instances still verify the
original topology and pass the existing ownership/release transaction. A normal
run on an unlicensed evaluation:

1. Disables automatic Windows updates with `NoAutoUpdate=1`. For managed
   endnodes it first rejects any conflicting explicitly configured WSUS URL,
   fills missing `WUServer`/`WUStatusServer` values from the existing encrypted
   `wsus_internal_url`, and sets `UseWUServer=1`. Matching source URLs are
   preserved. It then sets `DoNotConnectToWindowsUpdateInternetLocations=1`.
   Microsoft's Internet-location restriction depends on an intranet WSUS source;
   it is not an independent Internet block on a fresh clone. Repository roles
   preserve their existing OS update source and use `NoAutoUpdate` as their
   automatic-update guard. The stage never requests or installs Windows updates.
2. Uses existing connected access only when a default route exists **and** an
   approved permanent libvirt adapter is on the configured connected network.
   Otherwise it arms a 15-minute hypervisor cleanup deadline and attaches
   a temporary e1000e adapter **live only** to the approved connected libvirt
   network. The isolated primary adapter and every permanent secondary adapter
   stay attached.
3. Waits for the temporary DHCP/default route. If Windows has already activated
   automatically, it skips the licensing method. Otherwise PowerShell calls the
   installed evaluation SKU's local `SoftwareLicensingProduct.Activate` method
   through Ansible and polls for licensed status with positive remaining time.
4. Removes only this operation's generated temporary MAC in an Ansible `always`
   block, even after an activation or WinRM failure. It verifies removal has
   completed, live and persistent libvirt topology match the original snapshot,
   and guest addresses, DNS and default routes match the protected configuration.
5. Rechecks licensing after restoring the original topology. Managed clients
   therefore return to isolated-only access. Repository roles retain their
   approved permanent topology, including any permanent management adapter.

The hypervisor timer first lowers the temporary link and then detaches that
specific adapter if execution is canceled or the controller disappears. Normal
cleanup stops the timer only after original libvirt and Windows topology are
verified. In the legacy path, the connected network must already provide DHCP,
DNS and Microsoft activation access; that path creates no firewall exception. It
requires `systemd-run`/`systemctl` on the libvirt hypervisor as well as the existing
`virsh` and Python 3 tools. A host power loss already removes a live-only adapter
from the next startup, since the persistent definition is never changed.

Failures stop the deployment before repository preparation. A licensing error
does not authorize edition conversion, installation of a different product key,
resetting grace timers, disabling licensing services, or accepting license
terms. Check mode inspects the existing state without activation, policy writes
or NIC changes. Check mode is not proof that an unlicensed clone can activate.

## Prepared environments

For an explicitly approved prepared instance, the same playbook additionally
matches the hypervisor's pinned machine identity, Windows/native UUID, clone
title and disk path. The encrypted activation network must be an existing IPv4
NAT network with no live or persistent domain references, an approved isolation
bridge and no IPv6 network. A shared bridge is refused because routed firewall
rules alone do not establish isolation between guests on that bridge.

The generated MAC must be unused across all domains. Under the existing
900-second deadline, the job validates and adds five temporary nftables rules:
public IPv4 TCP 80/443, the existing private/production destination deny set,
an IPv6 forward block, and gateway-only UDP/TCP DNS. Existing DHCP permission is
reused. This is public HTTP/HTTPS access, not a Microsoft hostname filter.
The job starts an initially inactive network without enabling autostart and
attaches only the live temporary adapter. It creates no new network or service.

Both normal cleanup and the same existing deadline execute one cleanup command.
They check machine/UUID, lower and detach the exact temporary MAC first, then
remove only rules matching both its unique operation comment and MAC. They stop
an initially inactive network only after checking every domain's live and
persistent references. Cleanup failures remain failures and leave the deadline
armed; it is stopped only after successful original-topology checks.

Only after this include returns successfully does the play run native `Verify`,
require licensed status and positive evaluation grace, then invoke the existing
verified-guest release tasks. A failed activation, cleanup or final verification
cannot reach release. Licensed skips use that same verification/release endpoint.
The CaC template must attach the same existing source CA, source API reader,
central Git writer and central CaC Vault credentials used by the baseline
publisher, in addition to its existing Machine and Windows Vault credentials.
This reuses the existing Job Template and workflow graph, updates its credential
assignments and creates no new Job Template or credential type.

The private CaC enables the existing activation template's host-limit prompt
only for a prepared instance. For one already-created guest, include both the
`hypervisor` group and its exact inventory name in the limit, for example
`hypervisor:example-windows-clone`. Keep the encrypted target list unchanged.
The current expired guest can be activated after its clock repair and before
retrying the stopped baseline. This does not claim that activation has succeeded;
read back the actual installed license and original topology before continuing.

## Credentials and protected configuration

The activation Job Template uses the existing **Hypervisor SSH Machine** and
**Vault** credentials. Its first play builds an in-memory Windows inventory with
explicit WinRM settings and existing Windows credentials from
`vars/windows_activation_vault.yml`; Windows execution has `become: false`.
The existing `vars/wsus_environment_vault.yml` supplies the internal WSUS URL for
unlicensed managed clients, using the same Vault credential.
Hypervisor-only tasks delegate over SSH with explicit privilege escalation.
All connection inputs, topology results and credentials use `no_log: true`.

The encrypted file contains:

| Key | Purpose |
|---|---|
| `windows_activation_approved` | Recorded approval for the temporary activation exception |
| `windows_activation_network` | Existing connected libvirt network |
| `windows_activation_username`, `windows_activation_password` | Existing Windows management login |
| `windows_activation_targets` | Exact clone inventory/domain/version mappings and connection/topology settings |

Each target contains `inventory_host`, `vm_name`, `windows_version`, the same
`interfaces` list used by Windows basics, `libvirt_interfaces` entries with
`mac` and `network`, and `connection` settings `address`, `port`, `scheme`,
`transport`, `server_cert_validation`. Retain the existing WinRM authentication
and certificate-validation settings. Store actual hostnames, usernames,
addresses, passwords and network names only in encrypted configuration.
When rotating the Windows management login or changing clone topology, update
this encrypted record together with the inventory and deployment inputs.

## AAP configuration

`configure_windows_activation_template.yml` uses native `ansible.controller`
modules to create the activation template and change this success edge:

```text
Windows basics -> evaluation activation -> repository preparation
```

It checks that the existing basics node has exactly the expected successor
before changing it. Other workflow nodes and content pipelines are retained.
Supply protected controller connection references using the same
`wsus_controller_*` variables as the existing configuration playbooks, plus:

- `windows_activation_controller_workflow`: the existing Windows deployment workflow ID.
- `windows_activation_controller_credentials`: exactly the existing Hypervisor SSH and Vault credential references.

Refresh the project and apply this configuration before running a fresh
deployment. The activation template forbids simultaneous launches and does not
prompt for arbitrary extra variables. Do not launch the deployment workflow
against existing clones: its creation guard deliberately rejects them.

## Validation

No additional test framework is required. With the existing project collections
available, run:

```bash
ansible-playbook -i 'hypervisor,' activate_windows_evaluations.yml --syntax-check --vault-password-file /path/to/vault-password
ansible-playbook -i localhost, configure_windows_activation_template.yml --syntax-check
python3 -m unittest discover -s tests -p 'test_windows_activation*.py' -v
powershell.exe -NoProfile -File tests/Test-WindowsEvaluationActivation.ps1
```

The PowerShell tests replace all licensing and network calls with mocks and
cover licensed skips, evaluation-only activation, check mode, ambiguous/wrong
licenses, changed addresses/DNS/routes/adapters, temporary routing, original
repository connectivity, licensing errors and expired evaluations. Python tests
verify live/persistent topology evidence and the activation task cleanup paths,
fresh managed source establishment before exposure, conflicting-source refusal,
preservation of matching URLs, and rejection of an arbitrary default route as
evidence of connected-network access. Native completion tests also check release
after cleanup and final verification, licensed skips, no release after failures,
and preservation of baseline inventory variables by the existing `add_host` task.
Source validation does not substitute for a controlled fresh-clone workflow run.

Selected-instance recovery subsequently verified actual activation and cleanup.
The installed evaluation reached licensed status with approximately 180 days
remaining. The first cleanup exposed an unsupported `domif-setlink --live`
option; implementation `34accc1` removes it, and the same corrected cleanup
successfully restored the original NICs, removed all operation rules and stopped
the initially inactive network. Independent native checks confirmed those
results. Normal job 293 then passed the already-licensed skip, including original
addresses, DNS and routes; only after those checks was the original deadline
disarmed. The focused remaining baseline, job 296, also succeeded. Earlier three
baseline successes were preserved. The staged selected AD/content tests and
Windows-only teardown subsequently passed. The corrected completion placement
still requires its own fresh-clone live workflow test.

Live controller configuration on 2026-10-20 created activation Job Template 82
and routed the existing Windows basics success edge through activation to
repository preparation. Reapplying the configuration left the template and
workflow edges unchanged. Check job 2283 succeeded on all four existing clones
in 63 seconds: each was already licensed and its original guest and libvirt
topology matched the protected configuration. No activation, policy writes or
adapter changes occurred.

Normal job 2286 then succeeded in 69 seconds on the same four licensed clones.
Its recap reported zero changed tasks, no failures and no unreachable hosts.
Each clone skipped activation and passed the final licensed-state and original
topology verification. This verifies the deployed normal licensed skip path.

The first two Check attempts caught and corrected integration assumptions:
the hypervisor inventory entry is a host alias rather than a same-named group,
and live libvirt network interfaces have generated `bridge`/`portid` fields
absent from persistent XML. Target selection now requires one resolved host;
network comparison ignores only those generated fields for network interfaces.
Twenty regression tests pass, including real captured topology comparisons and
refusal of actual network, portgroup, unknown-attribute, model, MAC or link changes.
Fresh workflow 2303 subsequently passed all 21 stages. Its activation job 2311
took 3m32s: the three Server 2022 clones were already licensed and skipped
activation; the fresh Server 2025 clone began unlicensed, activated successfully,
and passed licensed-state and original-topology verification after temporary
connectivity cleanup. Repository preparation started only after that success.
This proves the normal unlicensed path on a fresh clone. Failure cleanup retains
the focused mocked coverage; the successful live test did not induce a licensing
failure or controller loss.

References:

- [Microsoft: Windows Server 2025 evaluation requirements](https://www.microsoft.com/en-us/evalcenter/evaluate-windows-server-2025).
- [Microsoft: licensing operations and Sysprep rearm behavior](https://learn.microsoft.com/en-us/windows-server/get-started/activation-slmgr-vbs-options).
- [Microsoft: SoftwareLicensingProduct licensing status and Activate method](https://learn.microsoft.com/en-us/previous-versions/windows/desktop/sppwmi/softwarelicensingproduct).
- [Microsoft: intranet WSUS and the Internet-location policy dependency](https://learn.microsoft.com/en-us/windows/deployment/update/waas-wu-settings#do-not-connect-to-any-windows-update-internet-locations).
- [libvirt: live interface attachment, removal and link control](https://www.libvirt.org/manpages/virsh.html).
