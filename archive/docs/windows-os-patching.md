# Monthly Windows patch ceilings

Use **Disconnected Windows Patching - Set WSUS Patch Ceiling** to prepare and
publish a monthly OS/.NET baseline on internal WSUS. This changes available
content; it does not install updates on endnodes.

## Evaluation activation prerequisite

The evaluation installation already includes a time-limited evaluation license;
it does not require purchasing a retail key for the trial. Microsoft provides a
180-day evaluation but requires activation over the Internet within the first
ten days to avoid automatic shutdown. Prepare and verify evaluation activation
while the guest has authorized activation connectivity, before isolating it.
See [Microsoft's Server 2025 evaluation requirements](https://www.microsoft.com/en-us/evalcenter/evaluate-windows-server-2025)
and the equivalent [Server 2022 requirements](https://www.microsoft.com/en-us/evalcenter/evaluate-windows-server-2022).

If a guest shuts down repeatedly, inspect its evaluation status and remaining
grace time. Windows licensing service (WLMS) events 100/101 and System event 1074
can identify an expired evaluation as the shutdown cause. The live diagnosis
found an expired activation grace period on the Server 2025 endnode, while
Server 2022 had a valid evaluation. This is separate from WSUS approval policy
and update installation; detailed guest evidence stays outside Git.

The separate [clone deployment activation stage](windows-evaluation-activation.md)
uses its encrypted, explicitly approved connectivity configuration. Monthly
ceiling and client patching playbooks do not activate guests or change their
network topology. An existing isolated guest needs an authorized activation
path before attempting online activation. A trial
that has already expired needs a supported recovery decision; do not assume
restarting the VM renews it. Microsoft's
[licensing command reference](https://learn.microsoft.com/en-us/windows-server/get-started/activation-slmgr-vbs-options)
describes status, activation and timer-reset operations.

For the diagnosed Server 2025 activation-grace failure, the operator authorized
temporary connectivity. A live-only second NIC on an existing NAT network
provided a route and DNS while preserving the original isolated adapter.
Windows activated its installed evaluation automatically; no product key,
edition conversion or timer reset was needed. A read-only Ansible WinRM query
confirmed licensed status and 180 days remaining. Removing the temporary NIC
restored the original single-adapter configuration and no default route; the
evaluation stayed valid and the internal WSUS source policies still matched.
The persistent VM definition was unchanged. Network identifiers and detailed
guest evidence remain outside Git.

For a future recovery, record the original adapters, routes and WSUS policies;
obtain approval for the temporary network exception; verify activation while
connected; then remove the temporary adapter and verify licensing, isolation
and WSUS policies again. Use a live-only adapter so it is not retained in the
persistent VM definition. Do not treat an attachment or activation command's
exit status alone as proof of a valid evaluation.

## Month choices

The required dropdown contains January 2026 through September 2026, the regular
monthly OS cumulative releases present for both supported Windows versions when
the feature was implemented. The default is April 2026. Display names map to
canonical release months internally. The playbook rejects unsupported choices.
Update the audited choices and survey together when more releases are available.

## What the selection means

Selecting April 2026 chooses each OS's regular April cumulative update, the
newest applicable .NET cumulative release at or before April, and required
prerequisites. .NET does not have a release every month. Older superseded
prerequisites remain eligible when necessary.

The ceiling uses release months in Microsoft update titles, with explicit
audited mappings required for prerequisite titles without a release month.
It does not confuse metadata revision dates or local arrival dates with the
original release month. Unknown or later prerequisites, expired selections and
ambiguous shared bundles stop the job before policy changes.

The internal policy approves the selected cumulative releases and prerequisites
for All Computers, and declines other catalogue entries server-wide. This also
hides unused older cumulative updates: the selected cumulative baseline includes
their fixes without offering every historical package. Preview updates and
other architectures are excluded. Automatic approval rules, automatic approval
refresh and scheduled internal synchronization are disabled.

The job cannot uninstall updates from a machine already newer than the ceiling.
Existing downloaded client content and installed state require separate
assessment; changing availability is not a rollback procedure.

## Ansible stages

1. Validate the named month, inventory roles, catalogue identities and internal
   file readiness without changing policy.
2. On external WSUS, approve the explicit historical baseline for an empty
   download-only group. Reuse existing files and budget only missing or incomplete
   payloads against the configured disk reserve. This does not target clients.
3. Wait for WSUS readiness and check file existence and lengths. A required license
   agreement causes failure; the job never accepts license terms automatically.
4. Reuse the existing export and internal HTTP pull/import playbooks, including
   their manifest and SHA-256 verification.
5. Apply internal approvals/declines, re-read the resulting policy, and save the
   verified month. AAP artifacts contain the selected update identities and
   verification result. Detailed diagnostics remain protected by default.

When the internal file check finds no missing or incomplete baseline payloads,
stages 2–4 are skipped. An approval-only change then stays on internal WSUS;
it does not prepare or retransfer external content.

Ansible handles orchestration, services, files, transfer, waiting and artifacts.
The WSUS management operations use its native PowerShell API through
`ansible.windows.win_powershell`.

The saved internal policy is reapplied after subsequent runs of
`replicate_and_import.yml`. WSUS has no native persistent month-filter setting:
this is reconciliation after import, not an atomic visibility boundary during
an import. Direct manual approval changes or synchronization outside these
playbooks can cause drift; validate or reapply the ceiling before client patching.
Changing from one month to another never deletes downloaded update files.

## Run and preview

Use the Job Template survey, or an existing protected inventory and credentials:

```bash
ansible-playbook -i YOUR_PROTECTED_INVENTORY set_internal_wsus_patch_month.yml \
  -e '{"wsus_patch_month":"April 2026"}'
```

Select AAP job type **Check**, or add `--check` locally, for a read-only plan.
Check mode reports selected identities and missing internal payloads without
downloading, exporting, importing or changing approvals. Normal mode prepares
content before applying policy. Catalogue presence alone does not mean the
corresponding update files are ready.

## Reproduce the Job Template configuration

### Install the currently published baseline

Run **Disconnected Windows Patching - Update Managed Windows** after the ceiling
job succeeds. Its playbook, `update_managed_windows.yml`, reads the verified
internal policy; it has no independent month selector. Run ceiling, transfer and
client installation jobs sequentially so the served baseline remains stable.

Before any installation it verifies every endnode's existing internal WSUS source
policies, client web service access and supported OS family. It also revalidates
internal approvals, declines and payloads. Conflicting sources stop the job for
configuration review rather than changing the source during patch installation.
Ceiling selection and client preflights check WSUS readiness, exact identities,
policy, file existence and lengths without hashing payloads. Transfer integrity
checks remain: export supplies SHA256 hashes, existing internal files are checked
once, and downloaded files are verified by the native Ansible downloader.
Metadata import does not repeat those payload checksums.

To patch two servers concurrently, launch this Job Template twice, selecting a
different managed host on each. Each limit must also include `wsus_internal` for
the shared read-only preflight: use `HOST_A:wsus_internal` and
`HOST_B:wsus_internal`. The template permits simultaneous jobs and accepts a limit
at launch; each individual playbook launch retains sequential client processing.
Never overlap the managed-host targets of concurrent jobs. Keep ceiling changes,
content import and client patching as separate stages, with the ceiling stable
until both jobs finish. An already running job retains the targets and scheduling
it started with.

Each pass performs a read-only Windows Update Agent search,
checks the release ceiling and license state, then gives the exact observed
update titles to `ansible.windows.win_updates` with `reboot: true`. The native
allowlist handles both the exact title and the pinned module's concatenated
title-plus-KB representation, with anchored patterns for the observed identities.
The configured retry count must be a YAML integer from one to three; its type
is retained for the native action plugin before Windows argument validation.
The native
module handles installation, intermediate reboots and rescans for that set.
Further bounded passes admit newly applicable prerequisites after fresh checks.
Read-only scans use Windows Update and Component Based Servicing registry reboot
markers, as the installed-state inspection does. The WUA `ISystemInformation`
interface is unavailable remotely and must not be used from the WinRM session;
see [Microsoft's remote WUA interface restrictions](https://learn.microsoft.com/en-us/windows/win32/wua_sdk/using-wua-from-a-remote-computer).
An empty scan with an outstanding reboot uses `ansible.windows.win_reboot`.
The default is eight passes, two retries for failed updates and an hour per reboot.

A successful normal run requires no applicable approved updates, no pending
reboot and an installed OS build at least as new as the audited monthly baseline.
`vars/windows_patch_builds.yml` records the official OS KB/build pairs for each
supported month and OS family. An empty update list alone is insufficient.
Before/after builds, scans and pass results are retained in authenticated AAP
artifacts. A client already above the ceiling remains above it.

Choose AAP job type **Check** for source validation and applicability reporting
without installation, reboot or license acceptance. This uses a read-only WUA
PowerShell search because the pinned native update module can accept update
licenses during a search. Native Ansible still performs installation and reboot
management in normal runs. Failed or unaccepted licenses require separate review.

```bash
ansible-playbook -i YOUR_PROTECTED_INVENTORY update_managed_windows.yml --check
```

### Configure both templates

`configure_wsus_patch_ceiling_template.yml` refreshes the project and configures
the template, credential associations and survey using
`ansible.controller.job_template`. Its separate optional controller administration
dependency is pinned in `configuration/collections/requirements.yml`; it is not
added to the Windows execution environment's runtime requirements.

Supply the following through protected configuration: `wsus_controller_host`,
`wsus_controller_token`, `wsus_controller_inventory`, `wsus_controller_project`,
`wsus_controller_execution_environment` and `wsus_controller_credentials`.
The credentials must include the existing Windows Machine and Vault credentials.
TLS certificate verification remains enabled. Existing standard controller
authentication environment variables can also supply the connection.

```bash
ansible-playbook configure_wsus_patch_ceiling_template.yml \
  -e @YOUR_PROTECTED_CONTROLLER_CONFIGURATION
ansible-playbook configure_windows_patching_template.yml \
  -e @YOUR_PROTECTED_CONTROLLER_CONFIGURATION
```

## References and verification

- [Microsoft: approvals, declines and update visibility](https://learn.microsoft.com/en-us/windows-server/administration/windows-server-update-services/manage/updates-operations)
- [Microsoft: cumulative and servicing-stack updates](https://learn.microsoft.com/en-us/windows/deployment/update/servicing-stack-updates)
- [Microsoft: checkpoint cumulative updates](https://learn.microsoft.com/en-us/windows/deployment/update/catalog-checkpoint-cumulative-updates)
- [Existing WSUS transfer pipeline](wsus-data-flow.md)
- [Installed build assessment](../assess_windows_patch_level.yml)

`tests/Test-WsusPatchMonthSelection.ps1` exercises invalid/missing months,
architecture and preview filtering, .NET fallback, prerequisites, explicit
prerequisite mappings and shared-bundle conflicts. Run it with an existing
Windows PowerShell 5.1 or PowerShell 7 installation; it needs no WSUS service.

`tests/Test-WindowsUpdateClientPolicy.ps1` checks client source-policy rejection
using mocks. `tests/Test-WsusContentValidation.ps1` verifies that policy checks
do not hash payloads and that transfer preparation detects missing, truncated
and same-length corrupt files while skipping already verified matching files.
`tests/Test-ManagedUpdateSearch.ps1` reproduces restricted COM access with mocks,
checks managed-source selection and pending licenses, verifies both reboot
markers, exercises the native title-plus-KB representation and rejects incomplete
searches. These PowerShell tests run without a
WSUS service. With the existing pinned Ansible dependencies, run the filter and
completion regression checks using:

```bash
python3 -m unittest discover -s tests -p test_windows_patching_filters.py -v
```

These tests do not install updates. Live Check mode validates integration;
normal client runs provide actual OS installation evidence.

Live validation on 2026-10-20 successfully published the internal April ceiling:
four selected OS/.NET bundles were ready and approved, other catalogue entries
were declined and no selected payloads were missing. The updated client Check
run passed internal policy and Server 2022 source validation, then stopped on
the unreachable Server 2025 endnode. A later read-only WinRM audit reached both
endnodes, confirmed their internal WSUS source settings and diagnosed expired
evaluation activation grace on Server 2025. Subsequently, authorized temporary connectivity activated the
existing Server 2025 evaluation automatically, and isolation was restored as
described above.

Subsequent normal installation upgraded Server 2022 from `20348.169` to the
April baseline `20348.5020`, installing OS update KB5082142 and .NET bundle
KB5084071. It reached its final verified report after about 39m49s. The original
two-client job was canceled at its handoff after this successful client result
to avoid overlapping the independent Server 2025 job. After a clean full VM
stop/start applied the requested 4 GiB RAM, a separate normal targeted run
succeeded in 2m00s: the build remained at the April baseline, no applicable
updates remained and no reboot was pending. That second run measures a settled
client, not the initial installation time.

System event record order confirms two patching restarts after the OS install
started and before the RAM-maintenance shutdown: one initiated by Ansible and
one planned upgrade restart by Windows TrustedInstaller. The full VM stop/start
for memory allocation is separate. Guest clock offsets make event record order
safer than comparing guest timestamps directly with Controller timestamps.

The Server 2025 download initially stalled because IIS returned HTTP 404 for an
existing complete MSU. The focused Setup WSUS tag `wsus_uup_mime` added the
server-level MSU/WIM MIME mappings through a successful normal AAP job in 31s.
HTTP HEAD then returned 200 with the exact expected file length from the client
and both repository servers. The original download retried and advanced;
Delivery Optimization's log recorded progress and completion for requested
transfer segments. Windows subsequently requested additional payload content
and reconstructed component files before the OS installation-start event.
Completion of one transfer is not completion of the entire update.
The servicing stack KB5082062 then reached Installed while the main April
update was being staged. No network isolation change or download service reset
was needed.

Server 2025 subsequently completed normal patch job 2258 successfully in
1h38m52s, including the initial download retries and recovery. It upgraded from
`26100.1742` to April build `26100.32690`, installing OS update KB5082063 and
.NET update KB5082417. Three outer passes handled the OS update, newly applicable
.NET update, and final empty scan. The final guard verified the internal WSUS
source, audited OS baseline, zero remaining applicable/hidden updates or pending
licenses, and no pending reboot. Four System restart records occurred after OS
installation began: two initiated by Ansible and two planned upgrade restarts
by TrustedInstaller. Use record order rather than skewed guest timestamps.

At one Windows-requested reboot boundary, the operator-authorized memory change
was applied by allowing the VM to stop and starting a fresh QEMU process with
4 GiB. No active installation was forcibly powered off. The one-time live reboot
action was replaced by the unchanged persistent restart policy on startup.
Both managed VMs now have 4 GiB allocated and verified from Windows. This memory
change does not establish that all servicing delays were caused by RAM.

When a newer client stays at zero download progress, check that the actual
payload is served through IIS as well as present on disk. Microsoft's required
[UUP MIME mappings](https://learn.microsoft.com/en-us/windows-server/administration/windows-server-update-services/plan/plan-your-wsus-deployment#manually-add-the-required-mime-types-for-uup)
are configured by `setup_wsus.yml`. `Get-DeliveryOptimizationStatus` and
`Get-DeliveryOptimizationLog` expose download state and retry errors; a completed
download is separate from successful update installation and the final build.

## Measured job runtimes

The [fresh end-to-end test](end-to-end-test-2026-10-20.md) subsequently passed
all 21 stages in 3h48m50s. Parallel patch jobs 2333 and 2334 reached the April
Server 2022 and 2025 builds in 41m28s and 1h05m09s respectively, including the
applicable .NET updates and final empty scans with no pending reboot. Both
clients started with 4 GiB allocated. Event record order confirms two patch
restarts on Server 2022 and four on Server 2025. Baseline and current application
deployment followed only after both patch jobs finished. This new run includes
the IIS MIME repair in normal setup and required no download-recovery intervention.

The ten latest successful jobs in this use case were inspected on 2026-10-20,
before the installation runs described above completed.
Durations below use AAP execution time, excluding the delay between job creation
and execution. Task spans come from matching per-host start and completion
events; asynchronous wait spans include the monitored Windows operation.
Failed jobs and the later client installation runs are outside this historical
successful-job sample.

| Job | Date | Operation | Execution time | Measured main cost |
|---|---|---|---|---|
| 2218 | October 20 | First April ceiling publication | 37m31s | External baseline preparation 12m37s; internal verification/import 8m54s; transfer/check loop 4m45s; approval reconciliation 2m47s. |
| 2203 | October 20 | Ceiling preview in Check mode | 1m11s | Execution startup 48s; baseline preview 10s. |
| 2191 | October 20 | Installed patch assessment | 13s | Windows state query 8s; this launch targeted one endnode. |
| 2183 | October 20 | Repeat WSUS replication/import | 4m20s | Transfer prevalidation 107s, per-file checks 65s, import wait 35s; all 22 file items reported unchanged. |
| 2185 | October 20 | Chocolatey replication/import | 1m48s | Numerous small feed/account/package checks; actual archive pull 6s. |
| 2181 | October 20 | WSUS prerequisite check | 33s | PowerShell syntax validation 18s; readiness inspection 6s. |
| 2179 | October 20 | WSUS prerequisite check | 42s | PowerShell syntax validation 18s; readiness inspection 8s. |
| 1302 | October 7 | Full WSUS replication/import | 36m33s | Download/verification loop 16m24s for about 13.0 GB; verification/import wait 18m34s. |
| 1300 | October 7 | External WSUS export | 3m00s | Export and manifest operation 2m17s. |
| 1268 | October 7 | External WSUS synchronization | 52m35s | Microsoft metadata synchronization and selected-file download wait 50m42s; four selected updates estimated at about 13.0 GB. |

The three long runs account for about 91% of this sample's execution time.
Their source predates removal of redundant payload hashing. Earlier import
operations combined payload verification and WSUS metadata import in one script;
the recorded task duration cannot divide that phase precisely between the two.
The first April publication transferred about 2.8 GB of additional files while
checking a 15.8 GB manifest, so the total selected content was larger than the
new network transfer.

The repeat WSUS run also spent time on unchanged files. Current transfer
preparation returns only missing or mismatched files, metadata import avoids a
second full payload hash, and an already available monthly baseline skips
external preparation and transfer entirely. These changes address measured
repeated work; another comparable successful run is needed to quantify their
speedup. A fresh baseline still needs its missing binaries and real WSUS work.

Creation-to-start delay was usually 14–42 seconds, with a 2m41s exception.
Startup before the first playbook event was usually 3–14 seconds, with 48s and
81s exceptions. These spans are measured separately; the events alone do not
fully attribute them to queueing, project preparation or execution-environment
startup. The async poll interval is 30 seconds; it can delay noticing completion,
but does not explain a 50-minute Windows operation.

Recommended priorities are to reuse synchronized content and existing baselines,
run independent endnodes concurrently through disjoint host-limited jobs, and
measure disk, memory and native WSUS subphase timings before attributing the
remaining import time to a particular resource. Reducing many small WinRM/API
checks can help short jobs, but those checks are not the main cause of the long
WSUS runs. Preserve update/reboot verification and the internal-only source.
