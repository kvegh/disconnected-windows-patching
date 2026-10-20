# Design decisions history

## 2026-10-20 — Follow managed updates through intermediate reboots

Implementation: `5e401ac`. The operator requested a separate client patching
playbook and Job Template using the currently served WSUS ceiling, with repeated
installation and reboot cycles. Validate the internal policy and every client's
existing source before installation, then process clients serially with bounded
passes. Native Ansible handles update installation, rebooting and reconnection.

Use read-only Windows Update Agent searches through Ansible PowerShell for
applicability checks: the pinned native update module can accept update licenses
even during search. Freeze each pass to the exact observed client titles after
license checks, and rescan before admitting newly applicable prerequisites.
This also accommodates .NET component titles that differ from WSUS bundle titles.
Stop for unaccepted terms rather than accepting them automatically.

Require the official monthly OS build floor, no remaining applicable updates
and no pending reboot before claiming completion. Record before/after evidence
and report already newer clients honestly. Check mode performs no installation
or reboot. Seven filter/completion regression checks and Windows PowerShell
parsing/source-policy tests passed; actual OS installation needs a normal run.
Keep controller configuration reproducible with native Ansible modules and
environment references protected outside plaintext Git.

## 2026-10-20 — Validate the existing offline WSUS role

Fix: `569a0fd`. The first deployed ceiling preview rejected the internal WSUS
because the existing offline setup retains the Microsoft upstream-selection
flag on both autonomous servers. Determine the internal role from the protected
inventory and retain local-content, autonomous-mode and active-sync checks.
Do not change the existing upstream configuration merely to satisfy the new
guard. The policy continues to disable scheduled internal synchronization.
The corrected AAP preview passed without host changes.

## 2026-10-20 — Offer named monthly Windows baselines

Implementation: `eae5cbd`. The operator requested a survey-driven internal WSUS
ceiling and reproducible Ansible automation. Use month names in the survey and
canonical release months internally. Prepare exact OS cumulative releases,
the latest eligible .NET releases and their prerequisites before approving them
internally. Existing export and verified internal pull/import stages are reused.
Budget missing files rather than all files, preserving downloaded content.

Decline unselected catalogue entries server-wide so later updates are not
offered for evaluation, and disable automatic approval paths. Save the verified
policy and reconcile it after later imports because WSUS has no native durable
month-filter setting. Unknown release identities, expired content, ambiguous
bundles, missing files and unaccepted license agreements stop the operation.
Check mode provides a read-only plan; this stage never patches endnodes.

Keep the Job Template, credential associations and named-month survey in an
Ansible controller configuration playbook. Its controller collection dependency
is separate from the Windows runtime dependencies. Add a TODO to review every
non-native-module dependency and whether supported Ansible content can replace
it. Windows execution validated the PowerShell parser and selection regression
checks before deployment; live policy validation is recorded separately.

## 2026-10-20 — Compare WSUS approvals with Satellite content lifecycles

Documentation: `578bedd`. The operator requested a public comparison of patching,
repository management, Content Views and promotion. Add a sourced guide and
README link, using Microsoft's WSUS documentation and Satellite 6.19 guidance.
Distinguish mutable WSUS group approvals from published Content View versions,
and explain why promotion does not install or downgrade host packages. Include
the rolling-view exception, disconnected transfer choices and separate Ansible
stages for content preparation, policy, installation and verification.

Use generic examples without deployed identities or connection details. The
comparison describes conceptual equivalents and does not add OS-installation
or approval automation. The same documentation change records successful
read-only assessment and artifact collection on both supported Windows versions;
no host changes were reported. Sources, relative links and whitespace were
reviewed before publication.

## 2026-10-20 — Make installed patch assessment repeatable

Implementation: `1d05660`. The operator requested reproducible Ansible tasks and
a check of both managed endnodes against April 2026. Add a dedicated read-only
playbook and PowerShell reader, using the installed OS build and revision as
the primary cumulative-update evidence. Compare against Microsoft's published
April monthly builds and retain exact installed hotfix identifiers separately,
because supersedence can remove an older KB from the installed list.

Report April .NET component KB matches without inferring absence of their fixes
when an exact KB is missing. Preserve pending-reboot evidence, distinguish a
newer OS revision from the exact requested baseline, and fail on unsupported
OS builds or inaccessible nodes. Protect detailed results by default and retain
them in authenticated AAP artifacts for before-and-after comparisons. This stage
does not scan, approve, install, reboot or start VMs. Applicability assessment,
older-baseline content selection and internal approval remain separate work.

## 2026-10-20 — Suggest SSH-tunneled VNC for demonstration access

Documentation: `e8d1665`. The operator requested a saved suggestion for reaching
the Windows GUI from a Linux laptop and showing that upgrades worked. Recommend
the existing loopback VNC consoles through the operator's authorized SSH route.
This builds on the VNC deployment choice in `fc8ac60` and reaches the guest
display independently of its isolated network.

The guide resolves console endpoints at demonstration time because ports are
assigned automatically. Read-only hypervisor inspection verified the console
configuration and an active endpoint. The end-to-end laptop connection, SSH
forwarding permission and Desktop Experience installation remain unverified.
The suggestion does not enable RDP or deploy a browser console.

Show OS builds and Windows Update installation events as patch evidence, since
Settings history can omit updates installed through Windows Update Agent APIs.
Show application versions separately. Proposed OS levels X and X+1 use pinned
cumulative updates and expected builds for repeatability; date-based selection
must distinguish metadata revision dates from local arrival dates. The older
baseline and its prerequisites may need explicit download and retention.
These are documented suggestions; client assessment, approval and OS patch
installation automation remain future work.

## 2026-10-06 — Approved Nexus onboarding

Keep EULA acceptance in the Nexus installation playbook. Check the existing
acceptance state and use the supported API only when approval for the pinned
distribution is recorded in the encrypted configuration. This makes repeated
setup safe and avoids silently accepting terms for a future distribution.
Implementation: `4c83c87`. Both repository servers passed live onboarding.

## 2026-10-06 — Native conditional path validation

Validate Windows paths using Ansible's actual conditional parser and full-string
matching. Escaping that worked in a rendered expression failed in task assertions.
Implementation: `89cd9fc` (Nexus paths), `aac60dd` (internal transfer path).
The regression suite checks both forms of deployment input.

## 2026-10-06 — Targeted synchronization diagnostics

Expose a protected-by-default logging survey for external package publication,
so development failures can be diagnosed without changing the normal default.
Implementation: `62feaaf`. External synchronization and archive publication
passed live execution after approved onboarding.

## 2026-10-06 — Windows JSON array handling

Assign the converted JSON package array directly before counting and filtering it.
Wrapping the conversion in an array expression can retain a nested array on
Windows PowerShell and report one expected package instead of four. Keep all
manifest, package checksum and archive-path checks in place and report harmless
schema/count details when validation fails.
Implementation: `95cbd03`. Live import verification passed, including checksum
verification and publication to the two internal release feeds.
Baseline installation and upgrades subsequently passed on both Windows client
versions, including exact installed versions and the sole enabled source check.
Fresh-environment workflow 1252 passed all 17 nodes on 2026-10-07 after guarded
Windows-only teardown and independent preservation verification. This validates
the combined implementation, including `4c83c87`, `aac60dd` and `95cbd03`, in a
complete run rather than only targeted recovery jobs.

## Retrospective — Deployment and isolation

These entries reconstruct significant decisions from session requirements and
the corresponding Git changes; they summarize the history rather than every fix.

- `81595b7`: deploy one VM per launch, with role and Windows-version inputs, so
  AAP can compose four independent deployments and run them in parallel.
- `91e0f4e`: select BIOS or UEFI from verified image partition layouts rather
  than assuming all Windows images boot the same way.
- `4475c21`, `efcab6a`: configure permanent guest networking and fixed deployment
  MAC addresses so management remains predictable across repeated cloning.
- `fc8ac60`: keep environment-specific WSUS settings encrypted; use VNC because
  the hypervisor does not support SPICE.
- `f888b68`, `b9342a2`, `d3d8db5`: restrict teardown to explicitly allowed demo
  VMs and their marked clone disks, and independently verify unrelated domains
  and base images against a captured baseline.

## Retrospective — Modular service and content lifecycle

- `a69418f`: separate Windows basics, WSUS installation and Chocolatey/Nexus
  installation so progress is visible and failed stages can be rerun separately.
- `5160e70`: prepare features and reboots before parallel service setup; separate
  WSUS readiness, synchronization, export and internal import into distinct jobs.
- `d9729d5`: download pinned installers during deployment, verify their checksums,
  and keep independent repository account credentials in Vault.
- `d6149aa`: build self-contained packages for two pinned versions each of 7-Zip
  and Git. Separate external synchronization/export, internal import, baseline
  installation and upgrades; expose distinct immutable release feeds instead of
  making disconnected clients fetch installers from the Internet.

## Retrospective — Network bootstrap reliability

- `a6638d1`: use native Ansible Windows modules for DNS and routing registry
  settings where they can express the desired state.
- `8b5795e`: launch NIC changes through native Task Scheduler so changes can
  complete despite interrupting the WinRM session and without SYSTEM run-as
  process creation on the affected image.
- `57f35d8`: reconnect after temporary WinRM interruption while polling scheduled
  completion, with bounded waits and explicit result validation. This prevents
  a successful network change from being misreported as a permanent failure.
