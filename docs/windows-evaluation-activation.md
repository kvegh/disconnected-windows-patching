# Per-clone Windows evaluation activation

Windows Server 2022 and 2025 share `01-win-vm-setup.yml`, selected by
`windows_version`. The deployment sequence is:

1. Create the four independent clones.
2. Configure permanent Windows networking, management access and identity.
3. Run `activate_windows_evaluations.yml` for evaluation licensing.
4. Prepare repository services and continue the existing WSUS/Chocolatey pipeline.

The activation stage runs after Windows basics because Ansible must already be
able to reach the guest over its permanent management address. It does not edit
the base image. Microsoft's evaluation requires Internet activation within ten
days to avoid automatic shutdown, and Sysprep generalization normally resets
licensing timers. Verify each deployed clone rather than assuming the base
image's licensing state is inherited.

## Activation and isolation

The playbook first checks the installed operating-system license and matches
the guest version, permanent addresses, DNS, default routes and adapter MACs to
encrypted configuration. It verifies the domain's demo ownership marker and
that live and persistent libvirt adapters match the protected deployment mapping.

Already-licensed clones remain read-only: no licensing call, policy write,
temporary adapter or cleanup timer. A normal run on an unlicensed evaluation:

1. Sets `NoAutoUpdate=1` and
   `DoNotConnectToWindowsUpdateInternetLocations=1` with native Ansible Windows
   registry modules. Existing internal WSUS URLs and approval policies remain
   intact. The stage never requests or installs Windows updates.
2. Uses existing connected access when the role already has an approved default
   route. Otherwise it arms a 15-minute hypervisor cleanup deadline and attaches
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
cleanup stops the timer only after libvirt confirms removal. The connected
network must already provide working DHCP, DNS and Microsoft activation access;
the playbook does not create networks, firewall exceptions or proxies. It
requires `systemd-run`/`systemctl` on the libvirt hypervisor as well as the existing
`virsh` and Python 3 tools. A host power loss already removes a live-only adapter
from the next startup, since the persistent definition is never changed.

Failures stop the deployment before repository preparation. A licensing error
does not authorize edition conversion, installation of a different product key,
resetting grace timers, disabling licensing services, or accepting license
terms. Check mode inspects the existing state without activation, policy writes
or NIC changes. Check mode is not proof that an unlicensed clone can activate.

## Credentials and protected configuration

The activation Job Template uses the existing **Hypervisor SSH Machine** and
**Vault** credentials. Its first play builds an in-memory Windows inventory with
explicit WinRM settings and existing Windows credentials from
`vars/windows_activation_vault.yml`; Windows execution has `become: false`.
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
verify live/persistent topology evidence and the activation task cleanup paths.
Source validation does not substitute for a controlled fresh-clone workflow run.

References:

- [Microsoft: Windows Server 2025 evaluation requirements](https://www.microsoft.com/en-us/evalcenter/evaluate-windows-server-2025).
- [Microsoft: licensing operations and Sysprep rearm behavior](https://learn.microsoft.com/en-us/windows-server/get-started/activation-slmgr-vbs-options).
- [Microsoft: SoftwareLicensingProduct licensing status and Activate method](https://learn.microsoft.com/en-us/previous-versions/windows/desktop/sppwmi/softwarelicensingproduct).
- [libvirt: live interface attachment, removal and link control](https://www.libvirt.org/manpages/virsh.html).
