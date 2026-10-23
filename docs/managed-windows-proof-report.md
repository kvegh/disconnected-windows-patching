# Live proof on both managed Windows servers

Double-click **Windows Demo Proof** on the Windows desktop. The shortcut starts
the installed PowerShell report with `-NoExit`, so its colored output remains
open. The same script is used by the AAP **Disconnected Windows Patching - Show
Managed Windows Demo Proof** Job Template. That job connects to both managed
nodes over WinRM, queries each server live, and displays their combined result
at the end. The full data is also retained in the job artifacts.

The reporter installs no updates, changes no WSUS policy and upgrades no
applications. It reads actual registry policy, the internal WSUS endpoint,
Windows build/hotfix state, Windows Update Agent local history, installed
package metadata, executable versions and retained local application history.
The expected values are comparison targets, never a substitute for a query.

| Proof | Evidence read on the server |
| --- | --- |
| Internal WSUS | Actual WUServer/WUStatusServer, UseWUServer, public-update policy, ClientWebService HTTP response and successful managed-server update history where retained. |
| April 2026 OS cutoff | Current build and revision, expected cumulative KB in Get-HotFix, related .NET markers and servicing reboot indicators. |
| Baseline then upgrade | Successful Chocolatey operations with versions/timestamps, plus verified machine-bound package-state receipts from future Ansible application runs. |
| Current applications | Installed package nuspec versions and the actual 7-Zip executable/Git version output. |

The regular April targets are Server 2022 build `20348.5020` / `KB5082142` and
Server 2025 build `26100.32690` / `KB5082063`. A higher build is clearly reported
as newer than the exact cutoff. Related .NET candidates are shown as installed
markers; this report does not perform a fresh catalogue/applicability scan.

| Application | Baseline package | Upgraded package |
| --- | --- | --- |
| 7-Zip | `26.3.0` | `26.4.0` |
| Git for Windows | `2.55.0.5` | `2.56.0.2` |

**PASS** means the evidence for that check was found. **WARN** includes a newer
OS build, a pending reboot, baseline-only state or missing historical evidence.
**FAIL** identifies a conflicting current WSUS policy, below-target OS build or
unexpected installed version. Current package versions alone do not prove that
the baseline was previously installed. Missing history is reported explicitly.

`deploy_managed_windows_demo_report.yml` installs the script, non-secret
comparison configuration and public desktop shortcut. Its separate **Install
Managed Windows Demo Proof** template can update existing nodes without
patching or upgrading them. Baseline/upgrade application playbooks deploy it
automatically on future runs and write evidence after live version checks pass.
No execution-policy bypass is used. The installer tests normal PowerShell file
execution and the pure evidence rules on Windows before reporting success.

Source files:

- [`assets/show-windows-demo-proof.ps1`](../assets/show-windows-demo-proof.ps1)
- [`report_managed_windows_demo.yml`](../report_managed_windows_demo.yml)
- [`configure_windows_demo_proof_templates.yml`](../configure_windows_demo_proof_templates.yml)
- [`tests/Test-WindowsDemoProof.ps1`](../tests/Test-WindowsDemoProof.ps1)

Microsoft documents the [NoExit switch](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_powershell_exe?view=powershell-5.1)
and the update-history [ServerSelection property](https://learn.microsoft.com/en-us/windows/win32/api/wuapi/nf-wuapi-iupdatehistoryentry-get_serverselection).
