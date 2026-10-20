# Design decisions history

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
