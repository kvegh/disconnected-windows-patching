# Windows upgrade demo: presenter guide with VNC

Use real Windows desktops to show three results: the clients use internal WSUS,
the selected Windows patches are installed, and the selected Chocolatey
applications have been installed, upgraded and exercised successfully. This
demonstrates servicing two existing OS versions, not converting Server 2022
into Server 2025.

Keep AAP in one window and the two managed Windows consoles in others. Use one
server for the detailed walkthrough, then repeat the final checks on the other.
The browser architecture demo can explain each transition, but its Next button
does not run automation or establish that a real job has finished.

## 1. Get console access from your laptop

### What already exists

The [deployment playbook](../01-win-vm-setup.yml) creates each VM with
`--graphics vnc,listen=127.0.0.1`. The remote hypervisor provides the VNC console;
you do not need to install a VNC server inside Windows or enable Remote Desktop.

Read-only inspection on **2026-10-22** confirmed all four demo VMs running with
loopback-bound VNC endpoints. Temporary SSH tunnels from the automation workspace
to both managed servers returned VNC protocol banners successfully and were
closed afterward. No hypervisor or Windows configuration was changed. A laptop
viewer session and interactive Windows login have not yet been verified.

| Access method | What you see | Requirements |
| --- | --- | --- |
| Hypervisor VNC console used here | The VM's console, including boot, restart and Windows sign-in | Authorized SSH access to the hypervisor, a tunnel and a VNC viewer |
| Windows Remote Desktop / RDP | A Windows desktop session after its remote-access service is ready | RDP enabled in Windows, an allowed account and a network route/firewall access to the guest |

VNC is the protocol; a remote console is the access it provides in this setup.
RDP is a different access path. See Microsoft's
[Remote Desktop requirements](https://learn.microsoft.com/en-us/windows-server/remote/remote-desktop-services/remotepc/remote-desktop-allow-access).

### Connect each managed server

On the laptop, have an SSH client, its existing authorized hypervisor identity
and route, and a VNC viewer such as TigerVNC or Remmina. The workspace's SSH alias
is not automatically available on your laptop. Reuse your approved SSH/jump-host
configuration. The commands below use a Bash-compatible laptop terminal.

1. Set the SSH alias and VM name from your private lab configuration:

   ```bash
   demo_hypervisor_ssh='YOUR_HYPERVISOR_SSH_ALIAS'
   demo_windows_vm='YOUR_MANAGED_WINDOWS_VM_NAME'

   ssh "$demo_hypervisor_ssh" \
     virsh --readonly --connect qemu:///system domstate "$demo_windows_vm"

   ssh "$demo_hypervisor_ssh" \
     virsh --readonly --connect qemu:///system vncdisplay "$demo_windows_vm"
   ```

   Require a running VM. The returned `:N` is a **display number**: TCP port is
   `5900 + N`. For example, display `:2` means TCP `5902`. Resolve it again after
   a stop/start; the assigned display can change. A paused VM needs its normal
   authorized resume procedure before you can interact with Windows.

2. Enter the resolved TCP port and start the tunnel:

   ```bash
   demo_remote_vnc_port='YOUR_RESOLVED_VNC_TCP_PORT'
   demo_local_vnc_port=15922

   ssh -N -o ExitOnForwardFailure=yes \
     -L "127.0.0.1:${demo_local_vnc_port}:127.0.0.1:${demo_remote_vnc_port}" \
     "$demo_hypervisor_ssh"
   ```

   Keep this terminal open. The SSH service must permit this local forwarding.
   Both tunnel ends use loopback; the existing VNC listener stays unchanged.
   See the [OpenSSH forwarding options](https://man.openbsd.org/ssh.1).

3. In a second laptop terminal, open TigerVNC:

   ```bash
   vncviewer 127.0.0.1::15922
   ```

   The double colon means a literal TCP port in
   [TigerVNC](https://tigervnc.org/doc/vncviewer.html). Alternatively, use a
   Remmina VNC profile targeting `127.0.0.1:15922`.

4. Use the viewer's **Send Ctrl+Alt+Delete** action if Windows requests it. Sign
   in using the existing authorized Windows account. Confirm that the guest has
   a graphical desktop, not Server Core, before planning GUI demonstrations.

5. Repeat for the other managed server with its own remote port and a different
   local port, for example `15925`. Keep the two viewer windows labelled clearly.
   Close the viewers and press Ctrl+C in each tunnel terminal when finished.

For jump-host details, other viewers and console troubleshooting, see
[Windows remote access](../windows-remote-access.md).

## 2. Prepare a demonstrable starting point

The latest recorded full run already finished at the upgraded state. Inspect
the current guests first; do not assume a fresh baseline. A rerun at the target
versions can prove repeatability, but will not show a version change. The
baseline application playbook does not silently downgrade newer applications,
and a WSUS ceiling does not uninstall newer Windows patches. For a genuine
before/after run, arrange fresh demo endnodes through the established deployment
procedure before the presentation.

Have these ready before the audience joins:

- Both managed Windows desktops, with readable console text and a fresh
  **Windows PowerShell** window opened as administrator.
- Working internal WSUS and Nexus, completed WSUS and Chocolatey imports, and
  both application release feeds populated.
- A verified **April 2026** WSUS ceiling for the target builds below. If this is
  not ready, run **Disconnected Windows Patching - Set WSUS Patch Ceiling** and
  select **April 2026** before client patching.
- AAP access to the individual templates in the next section, with the existing
  inventory, Windows Machine credential and Vault credential associated.
- The actual pre-demo OS builds and package state, so you can describe the
  difference honestly. Keep any environment-specific evidence outside Git.

Use individual job templates to stop at each proof point. The complete
**Deploy Windows + WSUS environment** workflow creates VMs and automatically
continues through patching, baseline applications and upgrades; it has no
presenter pauses between these stages.

For a short presentation, prepare the slow content and OS-patching stages in
advance, show their actual completed AAP jobs, and inspect the real guests live.
Run the application upgrade live if the rehearsed duration fits. For full live
execution, allow the actual jobs to finish between the steps below. The recorded
[end-to-end run](end-to-end-test-2026-10-20.md) took about 41 minutes and 65 minutes
for the two OS-patching jobs, and about four minutes for the application upgrade;
these are historical timings, not estimates for the next run.

## 3. Know which AAP job to launch

In AAP, open **Automation Execution → Templates**, find the named template and
choose **Launch**. Navigation wording can vary by AAP version. Use **Run** for a
change and **Check** only where listed. Wait for the actual job result, then
switch to the Windows console to verify it.

All names below have the prefix **Disconnected Windows Patching -**.

| Point in the demo | Template suffix | What it does |
| --- | --- | --- |
| Optional live source configuration | Setup WSUS | Configures WSUS and the managed clients' internal update policy; requires the prepared repository stage |
| Read installed patch state | Assess Windows Patch Level | Reads build, hotfix evidence and reboot markers; does not search for or install updates |
| Prepare the monthly release | Set WSUS Patch Ceiling | Makes the selected internal OS/.NET baseline available; does not patch clients |
| Preview applicable patches | Update Managed Windows, job type **Check** | Validates internal source/content and searches without installing or rebooting |
| Install the published release | Update Managed Windows, job type **Run** | Installs the internal baseline, completes required reboots and rescans |
| Install the older applications | Deploy Baseline Applications | Installs the pinned older versions from the baseline feed |
| Upgrade those applications | Upgrade Applications | Switches to the current feed and upgrades to the pinned newer versions |

For a patch job limited to one managed host, the limit must also include the
internal WSUS group: `YOUR_MANAGED_HOST:wsus_internal`. To patch both concurrently,
use two jobs with disjoint managed-host limits, each including `wsus_internal`.
Keep the ceiling and repository imports stable until both jobs finish. Assessment
can target a managed host alone. Application templates target `windows_managed`;
do not assume a per-host limit prompt is enabled on those templates.

## 4. Show: “This server uses our internal WSUS”

On the managed server, run these read-only commands in Windows PowerShell:

```powershell
$wu = 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate'
Get-ItemProperty $wu |
    Select-Object WUServer, WUStatusServer, DoNotConnectToWindowsUpdateInternetLocations
Get-ItemProperty "$wu\AU" | Select-Object UseWUServer, NoAutoUpdate
```

Show the audience these values:

| Value | Expected result |
| --- | --- |
| `WUServer` and `WUStatusServer` | Both identify the internal WSUS URL from the protected configuration |
| `UseWUServer` | `1`: use the managed update service |
| `DoNotConnectToWindowsUpdateInternetLocations` | `1`: block public Windows Update locations |
| `NoAutoUpdate` | `1`: automatic updating is disabled; AAP controls installation |

Then demonstrate that its configured WSUS client endpoint responds:

```powershell
$wsus = (Get-ItemProperty $wu).WUServer.TrimEnd('/')
(Invoke-WebRequest -Uri "$wsus/ClientWebService/client.asmx" `
    -UseBasicParsing -TimeoutSec 15).StatusCode
```

Expected: `200`. This proves policy plus endpoint reachability; installation is
verified separately in the next step. These exact values are configured by
[setup_wsus.yml](../setup_wsus.yml). Because it writes the policy registry
directly, Local Group Policy Editor is not the authoritative display of what
the playbook configured.

**Say:** “This server is configured to use our internal WSUS. It can reach the
internal service, and Ansible decides when updates are installed.”

If demonstrating the policy change itself, capture the real prior state before
running **Setup WSUS**, then repeat these checks after it succeeds. If the values
already match, present this as verification of the existing configuration.

## 5. Show: “The selected Windows patch is installed”

1. Before patching, press **Win+R**, enter `winver`, and show the current build.
   Record the initial build for each server. Close the dialog.
2. Optionally launch **Update Managed Windows → Check** to show what is applicable.
   This is an applicability preview, not an installation result.
3. Launch **Update Managed Windows → Run**. During a restart, leave VNC visible
   briefly so the audience can see the real Windows restart. Let AAP finish all
   reboot/rescan passes, then sign in again. A desktop returning alone does not
   mean that the automation has finished.
4. Run `winver` again and compare with the pinned target:

   | Managed OS | April 2026 cumulative update | Target OS build |
   | --- | --- | --- |
   | Windows Server 2022 | KB5082142 | `20348.5020` |
   | Windows Server 2025 | KB5082063 | `26100.32690` |

   These are this demo's regular April baseline, not the latest available
   releases. The selections are versioned in
   [windows_patch_builds.yml](../vars/windows_patch_builds.yml).
5. For a clear textual comparison, show the installed build and reboot markers:

   ```powershell
   $version = Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion'
   $os = Get-CimInstance Win32_OperatingSystem
   [pscustomobject]@{
       OS = $os.Caption
       Build = "$($version.CurrentBuildNumber).$($version.UBR)"
       CBSRebootPending = Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending'
       WindowsUpdateRebootPending = Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired'
   }
   ```

   Both markers should be `False`. The build is the main installed-OS evidence.
   A newer build meets or exceeds April but is not an exact April-only result;
   do not describe it as a newly applied April update.
6. Show the matching hotfixes as supporting evidence:

   ```powershell
   Get-HotFix | Where-Object {
       $_.HotFixID -in @('KB5082142', 'KB5082063', 'KB5082427', 'KB5082425', 'KB5082417')
   } | Select-Object HotFixID, InstalledOn
   ```

   The applicable .NET component identifiers differ by OS and installed
   components; do not expect every identifier on each machine. Exact KB entries
   can also disappear after supersedence, and
   [the hotfix provider is not a complete update inventory](https://learn.microsoft.com/en-us/windows/win32/cimwin32prov/win32-quickfixengineering).
   Pair this with the build and AAP's verification result.
7. In AAP, show the successful patch job and run **Assess Windows Patch Level**
   for the before/after build comparison and reboot evidence. Assessment alone
   is not a pass/fail installation gate. To show no approved applicable updates
   remain, use **Update Managed Windows → Check** after the successful run.

**Say:** “This is the Windows build after the selected baseline was installed.
The patch job completed its reboot cycles, and the final check found no remaining
applicable approved updates.” Only say the final sentence once that check passes.

Use `winver` and installed-state evidence even if Windows Settings' update history
does not show the automation's installations. The
[patching reference](windows-os-patching.md) explains the checks in more detail.

## 6. Show: “The baseline applications are installed and work”

Run **Deploy Baseline Applications**, then open a fresh Windows PowerShell window
on the managed server and show:

```powershell
choco --version
choco list
choco source list
& "$env:ProgramFiles\Git\cmd\git.exe" --version
& "$env:ProgramFiles\7-Zip\7z.exe" i | Select-Object -First 4
```

Chocolatey 2.x's [list command](https://docs.chocolatey.org/en-us/choco/commands/list/)
lists installed packages; the old `--local-only` flag is unnecessary. In the
source listing, show `internal-nexus` as the only enabled source, with a URL path
ending in `/repository/chocolatey-baseline/`. The public source is removed.

| Evidence | Baseline | After upgrade |
| --- | --- | --- |
| `choco list`: `7zip.install` | `26.3.0` | `26.4.0` |
| 7-Zip vendor version | `26.03` | `26.04` |
| `choco list`: `git.install` | `2.55.0.5` | `2.56.0.2` |
| `git --version` | `2.55.0.windows.5` | `2.56.0.windows.2` |
| Sole enabled feed path | `chocolatey-baseline` | `chocolatey-current` |

The package version and the application's vendor version use different formats.
Both are pinned in [chocolatey_packages.yml](../vars/chocolatey_packages.yml).
`choco --version` identifies the package manager, not the version of Git or 7-Zip.

For the visual proof, launch 7-Zip File Manager:

```powershell
Start-Process "$env:ProgramFiles\7-Zip\7zFM.exe"
```

Choose **Help → About 7-Zip** and show `26.03`. Then exercise the applications
using the next section. The checks create only a new temporary demonstration
folder; they need no Internet access or Git identity configuration.

**Say:** “The older versions are installed from our internal baseline feed.
The version shown by the application agrees with the package inventory.”

## 7. Prove the applications perform real work

Run this on the managed server after baseline installation, and run it again
after the upgrade. Each run creates a fresh folder so an old archive cannot
stand in for a new result.

```powershell
$proof = Join-Path $env:TEMP ('upgrade-proof-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $proof | Out-Null
Set-Content -LiteralPath (Join-Path $proof 'proof.txt') -Value 'Installed from the internal repository.'
$git = "$env:ProgramFiles\Git\cmd\git.exe"
$zip = "$env:ProgramFiles\7-Zip\7z.exe"

& $git -C $proof init
if ($LASTEXITCODE -ne 0) { throw 'Git initialization failed.' }
& $git -C $proof add proof.txt
if ($LASTEXITCODE -ne 0) { throw 'Git staging failed.' }
& $git -C $proof status --short
if ($LASTEXITCODE -ne 0) { throw 'Git status failed.' }

& $zip a (Join-Path $proof 'proof.7z') (Join-Path $proof 'proof.txt')
if ($LASTEXITCODE -ne 0) { throw '7-Zip archive creation failed.' }
& $zip t (Join-Path $proof 'proof.7z')
if ($LASTEXITCODE -ne 0) { throw '7-Zip archive test failed.' }
Invoke-Item -LiteralPath $proof
```

Show `A  proof.txt` from Git: it created a local repository and staged the file.
Show **Everything is Ok** and exit code zero from 7-Zip: it created and tested an
archive. For a GUI view, open `proof.7z` in 7-Zip File Manager and show `proof.txt`
inside it. Leave the original text file available for comparison.

**Say:** “These are working applications: Git can manage a file, and 7-Zip can
create and verify an archive. All of this happens locally.”

## 8. Upgrade, then repeat the same evidence

1. Close 7-Zip, Git Bash and any other application windows using the installed
   binaries before launching the upgrade.
2. In AAP, launch **Upgrade Applications**. It selects the internal current feed
   and installs the pinned newer releases. Watch the real job and let any
   required restart finish; wait for job success before claiming completion.
3. Open a fresh Windows PowerShell window. Repeat the inventory, source and
   executable-version commands from section 6. Compare with the table's upgrade
   column, including `/repository/chocolatey-current/` as the selected feed.
4. Open 7-Zip **Help → About** again and show `26.04`. Repeat the functional
   checks in section 7 using the upgraded binaries.
5. Repeat the final build, package-version and functional checks on the other
   managed server. The OS build should retain the selected patch level while
   the application versions change.

**Say:** “The same internal deployment process has moved these applications
from the baseline versions to the newer approved versions. Here are the new
versions, and here they are doing the same work successfully.”

## 9. Finish with three visible facts

Keep the close short: show the internal source, the final OS build with clear
reboot markers, and the new application versions with the successful functional
test. Pair the guest results with the completed AAP jobs for both managed hosts.

If a check fails, keep that result visible and investigate it before advancing
the story. A green illustrative diagram, a returned Windows login screen or a
package-manager record alone is not the complete result.

## Rehearsal and validation status

The underlying patch and application jobs have live evidence in the
[end-to-end test report](end-to-end-test-2026-10-20.md). This guide's job names,
policies, exact package pins and build targets were checked against repository
sources. The console listeners and SSH-forwarded VNC banners were checked live
on 2026-10-22. The new presenter command sequence and GUI walkthrough still need
a rehearsal inside the Windows desktops; this documentation change did not run
patching, reset guests, install applications or change remote-access settings.

Implementation references: [application deployment](application-deployment.md),
[WSUS data flow](wsus-data-flow.md), and
[monthly patching](windows-os-patching.md).
