# WSUS and Red Hat Satellite: staged patching compared

WSUS controls which Microsoft updates Windows clients may install. Satellite
curates repositories into versioned Content Views and promotes those versions
through lifecycle environments. Both support staged patching, but a WSUS approval
is not a Content View version.

This comparison uses Microsoft's WSUS documentation and Satellite 6.19
documentation. It describes the Windows and RHEL patching workflows respectively;
Satellite is not a replacement Windows Update service. AAP can coordinate each
platform's separate workflow.
[Microsoft: WSUS deployment](https://learn.microsoft.com/en-us/windows-server/administration/windows-server-update-services/plan/plan-your-wsus-deployment),
[Red Hat: content and patch management](https://docs.redhat.com/en/documentation/red_hat_satellite/6.19/html/overview_concepts_and_deployment_considerations/content-and-patch-management-with-satellite).

## Capability comparison

| Area | WSUS | Red Hat Satellite |
| --- | --- | --- |
| Patching unit | Microsoft update identity/revision, commonly identified by a KB; OS cumulative updates bundle earlier fixes. | RPM package versions and errata describing security, bug-fix and enhancement updates. |
| Repository selection | Select products, classifications and languages; synchronize metadata and download required files. | Enable Red Hat repositories or create custom products/repositories; synchronize their content. |
| Baseline | Maintain an explicit update selection and its approvals for computer groups. | Publish a versioned Content View containing selected repositories and optional filters. |
| Content Views | No native equivalent. A console update view filters the administrator's display. | Native content snapshots; composite views can combine component views. |
| Promotion | Apply the tested update selection to another computer group. There is no native promotion of a versioned baseline object. | Promote a specific published version along a lifecycle path such as Development → Test → Production. |
| New synchronization | Adds or revises catalogue entries; automatic approvals can change deployment eligibility. | Refreshes source repositories; publishing a new version is a separate operation for versioned views. |
| Client access | Installation approvals target computer groups; declining suppresses an update server-wide. | Host Content View/environment assignments, repository enablement and other access rules determine available packages. |
| Installed state | Read the client OS build, installed updates and reboot status. | Read installed RPM versions, running kernel and reboot/service state. Neither repository state alone proves successful patching. |

Sources:
[Microsoft: update management](https://learn.microsoft.com/en-us/windows-server/administration/windows-server-update-services/manage/viewing-and-managing-updates),
[Microsoft: cumulative servicing](https://learn.microsoft.com/en-us/windows/deployment/update/servicing-stack-updates),
[Red Hat: products and repositories](https://docs.redhat.com/en/documentation/red_hat_satellite/6.19/html/managing_content/adding-content-to-satellite),
[Red Hat: Content Views](https://docs.redhat.com/en/documentation/red_hat_satellite/6.19/html/managing_content/managing-content-views-and-content-view-environments),
[Red Hat: host content access](https://docs.redhat.com/en/documentation/red_hat_satellite/6.19/html/managing_content/content-access-control-for-hosts).

## Publishing and promotion

In Satellite, **publish** creates a versioned snapshot from the Content View's
repositories and filters. **Promote** makes an existing version available in a
chosen lifecycle environment. Promote the tested version through each stage;
republishing at every stage would create a different candidate.
[Red Hat: Content View workflow](https://docs.redhat.com/en/documentation/red_hat_satellite/6.19/html/managing_content/managing-content-views-and-content-view-environments).

For example, Test can consume version 2.0 while Production remains on 1.0. Moving
2.0 to Production changes available content; it does not install packages.
Selecting an earlier version also does not downgrade installed packages.
[Red Hat: application lifecycles](https://docs.redhat.com/en/documentation/red_hat_satellite/6.19/html/managing_content/managing_application_lifecycles_content-management).

This applies to **versioned, non-rolling** Content Views. Rolling Content Views
follow synchronized repository changes without publishing or promoting new
versions, so they do not provide this fixed-baseline workflow.
[Red Hat: rolling Content Views](https://docs.redhat.com/en/documentation/red_hat_satellite/6.19/html/managing_content/managing-content-views-and-content-view-environments).

WSUS instead retains mutable update approvals. Reproducing a baseline requires
automation to record exact update identities/revisions, target groups and
prerequisites. Merely naming a group “April baseline” does not freeze its content.

## WSUS approval, visibility and a date cutoff

**Not Approved** prevents installation through that approval policy, but clients
can still evaluate whether the update is needed. **Declined** prevents WSUS from
offering it for evaluation or installation. Decline applies to the server rather
than an individual computer group. A console date filter changes neither.
[Microsoft: update operations](https://learn.microsoft.com/en-us/windows-server/administration/windows-server-update-services/manage/updates-operations).

Use group-specific approvals for parallel test/production stages. Check inherited
approvals, membership in multiple groups and automatic rules; a group name alone
does not establish isolation.
[Microsoft: computer groups](https://learn.microsoft.com/en-us/windows-server/administration/windows-server-update-services/manage/managing-wsus-client-computers-and-wsus-computer-groups).

A reproducible Windows “through April” baseline should name the selected OS
cumulative update for each OS, expected builds, applicable .NET updates and
required prerequisites. A calendar label alone is insufficient. Cumulative
updates include earlier fixes; Server 2025 checkpoint dependencies still require
the necessary content to be available.
[Microsoft: cumulative servicing](https://learn.microsoft.com/en-us/windows/deployment/update/servicing-stack-updates),
[Microsoft: checkpoint updates](https://learn.microsoft.com/en-us/windows/deployment/update/catalog-checkpoint-cumulative-updates).

For the demonstration, a strict server-wide visibility cap could decline newer
updates on internal WSUS, then reinstate and approve the next baseline. That is a
proposed policy, not a native WSUS snapshot or an action performed by this document.
It requires checking every affected client group before changing shared policy.

## Disconnected content transfer

WSUS metadata export and update files are separate. `WSUSutil export/import`
handles metadata; the binaries must also be copied. This repository's
[WSUS pipeline](wsus-data-flow.md) publishes the metadata, files and a checksum
manifest externally, then the internal server pulls and verifies them before
import. Internal client approvals remain a separate step. The transfer does not
install updates on endnodes.
[Microsoft: WSUSutil export/import procedure](https://learn.microsoft.com/en-us/intune/configmgr/sum/get-started/synchronize-software-updates-disconnected).

Satellite supports exporting/importing Library content, individual repositories
or specific Content View versions, including incremental exports. Exporting a
version preserves the curated content selection; exporting Library lets the
disconnected Satellite curate it locally. Required payloads must be downloaded
before export; the documented workflow uses Immediate download policy.
Transporting archives, importing them and making content available are distinct
from patching hosts.
[Red Hat: Inter-Satellite Synchronization](https://docs.redhat.com/en/documentation/red_hat_satellite/6.19/html/managing_content/synchronizing_content_between_servers_content-management).

## Mapping the X → X+1 demonstration

These are conceptual equivalents, not interchangeable objects:

| Step | WSUS approach | Satellite approach |
| --- | --- | --- |
| Define X | Pin OS-specific update identities, prerequisites and expected builds. | Publish and retain Content View version 1.0 with the intended package set. |
| Make X available | Transfer required content and reconcile internal group approvals. | Import if disconnected, then promote 1.0 to the host's environment. |
| Apply and prove X | Install from internal WSUS; reboot as required; assess builds and updates. | Apply updates from the assigned content; assess RPMs and the running system. |
| Advance to X+1 | Reconcile approvals to the next pinned selection; install and verify again. | Publish 2.0, test and promote that same version; patch and verify again. |

Keep content preparation, deployment policy, installation and assessment as
separate Ansible stages. Satellite exposes publish/promote operations through
[`redhat.satellite.content_view_version`](https://redhatsatellite.github.io/satellite-ansible-collection/develop/plugins/content_view_version_module.html).
Windows installation can use
[`ansible.windows.win_updates`](https://docs.ansible.com/projects/ansible/latest/collections/ansible/windows/win_updates_module.html)
with `server_selection: managed_server`; WSUS administration uses its PowerShell
API, as described in the pipeline documentation. These are automation options;
this comparison does not add approval or OS-installation playbooks.

Retain the selected payloads and baseline definitions for repeatability. Start
demonstrations from a known older host state: narrowing available content never
turns an already newer machine back into X. The repository's
[patch-level assessment](../assess_windows_patch_level.yml) supplies Windows build and hotfix evidence;
successful synchronization or import is not that evidence.
