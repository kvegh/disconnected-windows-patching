# Windows demo with AAP orchestration

**[Open this visualization](https://kvegh.github.io/disconnected-windows-patching/demo-with-aap/)** · [Standard Windows edition](https://kvegh.github.io/disconnected-windows-patching/)

A separate browser walkthrough that adds connected AAP and a proposed Linux
execution node inside the secure network. It retains the original palette,
larger typography, growing workflow, server details and in-page code previews.
The original `demo/` assets remain independent.

The changing execution-status message sits beside Datacenter on wide windows
and wraps below it on narrower ones. The redundant host-count and environment
labels remain omitted. The title and action area use less vertical space.
The drawing uses a 1036×652 landscape viewBox and renders at 1036–1068.375px
wide, preserving the card and text scale of the previous 1280–1320px drawing.
On narrower screens it scrolls horizontally; normal vertical page scrolling
remains available. The entire drawing is not forced into the remaining
viewport height.

Microsoft Update and Application Repository sync sit above the network
rectangles and appear together in action 4. Removing their former left column
brings both networks together. Each network is 568 units tall, 66 shorter than
the previous 634-unit rectangles; tighter gaps preserve the existing card sizes.
IIS export remains below the content tiles, and managed Windows hosts sit near
the secure rectangle’s bottom. Blue content arrows branch halfway between the
internal repository and managed hosts; purple dashed WinRM control arrows use
separate server entry points and labels. Repository service labels say Chocolatey
application repository. The larger, darker hint highlights server inspection.

Walkthrough ordering, execution phases, server details and code previews remain.
Browser rendering remains unverified under the owner’s choice to proceed without
installing a browser. Source checks and publication verification do not establish
observed visual readability. This compact layout supersedes the previous source
column while retaining the card scale restored after the earlier too-small and
too-large layout attempts.

The existing GitHub Pages root continues to show the original demo. This edition
is published at `/demo-with-aap/` underneath the same project Pages origin. Each
page has its own source files and URL; no second repository is needed.

## Sequence and architecture

The AAP controller and proposed execution node are prerequisites visible before
Windows deployment. AAP's connected card groups control and connected execution;
it does not imply that a controller-only node runs ordinary playbooks.

Each Next click shows scheduling before infrastructure changes. Internal work
then shows an inside-out arrow from the execution node to external AAP, job
dispatch back over Receptor mesh, and local execution against Windows hosts over
WinRM. This outward cue animates before every internal action, including actions
that also involve connected work. Connected-only actions do not animate the mesh.

The first internal action shows the execution node establishing the outbound
connection. Later actions repeat the directional cue while reusing that
connection: it is bidirectional, so jobs flow back over it. The repeated cue is a
visual reminder of connection ownership, not a separate task request, a fresh
connection or periodic HTTP polling. The connection is established during the
first deployment action.

Deployment is shown in two stages: external AAP deploys the external
repository first, then the internal execution node deploys the internal repository
and two managed Windows VMs. One external and three internal deployment arrows
show those relationships. The external server appears after its arrow animation;
the three internal VMs appear after their own deployment arrows. Low-level
provisioning details are abstracted from the walkthrough.

Other Windows/content state changes follow their short orchestration phases.
Previous restores the earlier state. Start over also cancels pending phases, so
a delayed result cannot repopulate a reset diagram. Reduced-motion preferences
make the phase sequence immediate and hide moving particles.

Execution paths are purple; package/update paths retain blue and amber. Export
data remains a separate internal-initiated HTTP pull from external IIS/Chocolatey application repository.
Neither AAP nor the execution node relays the update payloads.

## Proposed topology, not a deployed execution node

This page is an illustrative architecture edition. It does not create an
execution node, configure networking or launch real AAP jobs. The proposed node
is labelled on the diagram, in its details and in the page footer. Mesh access
requires an approved outbound route, trusted certificates and compatible peers.
The diagram represents secure client segmentation with controlled connectivity,
not a physical air gap.

Implementing this topology would require instance-group/job routing and an
execution environment with the required content. Existing WSUS import tasks
delegate trusted manifest reads to external WSUS; those reads need an explicit
connectivity review or a designed trusted-artifact handoff before routing that
job to an internal node. This edition does not establish that the current jobs
already work from the proposed execution location.

The connection model is based on the local AAP 2.7 Administer reference and
Red Hat's [execution-node guidance](https://docs.redhat.com/en/documentation/red_hat_ansible_automation_platform/2.7/administer-proc_run_jobs_on_execution_nodes).
The distinction between connection initiation and bidirectional traffic is
also described in the [AAP 2.7 Administer reference](https://docs.redhat.com/en/documentation/red_hat_ansible_automation_platform/2.7/pdfs/aap-administer-2-7-pdf.pdf).
Operator/cloud mesh ingress is deployment-specific; its installation procedure
is not presented as the procedure for this containerized lab.

## Source and local use

- `index.html`: control plane and Windows architecture.
- `src/styles.css`: independent copy of the original presentation styles.
- `src/aap.css`: orchestration diagram and phase styling.
- `src/scenario.js`: Windows actions and intended execution locations.
- `src/orchestration.js`: phase planning and cancellable playback.
- `src/app.js`: controls, illustrated states, previews and server details.
- `tests/`: state, source integrity, ordering and cancellation checks.

No dependencies or installation are required. Open `index.html` directly or use
an already available Python from the repository root:

```bash
python3 -m http.server --directory demo-with-aap 8000
```

Real-code links work on GitHub Pages. Local previews can use
`?site=https://OWNER.github.io/REPOSITORY/` to identify the public source repository.

With an existing Node.js 18 or newer:

```bash
node --check demo-with-aap/src/scenario.js
node --check demo-with-aap/src/orchestration.js
node --check demo-with-aap/src/app.js
node --test demo-with-aap/tests/*.test.cjs
git diff --check
```

There is no package manager, lockfile, formatter or linter dependency. Retain the
plain HTML, CSS and JavaScript conventions and run the syntax checks above.
The existing Pages workflow checks both editions and publishes only page assets.

## Layout rollback

The layout is a focused Git change; use an ordinary reviewed revert of its
implementation commit recorded in `../design_decisions_history.md` if the owner
chooses to roll it back. The pre-revision layout is preserved at
`d158dcd872ec1553d85d388a04924fd598f79436`; do not reset shared history or revert
unrelated automation changes.

Version 1.2.0 was published from implementation `645a8dbd95f5dc44888ad8474187da99c17aeaff`.
The existing Pages workflow succeeded on 2026-11-15 at 12:54:59 UTC; served
HTML, versioned CSS and app JavaScript matched that revision. The source
checks above passed; browser appearance remains unverified.

Version1.2.1 refines network grouping, managed-host placement and hint visibility
from implementation `07b7f718b8da408b37a32fe6442c6ae1b1c023e2`. Pages succeeded on
2026-11-15 at14:08:11 UTC and served assets matched the checked source.
Browser appearance remains unverified.

Version 1.2.2 adds parallel application synchronization, descriptive application
repository labels and distinct, balanced client routes. Publication evidence is
recorded in the project decision history after verification.

Version 1.2.3 moves synchronization above shorter network rectangles and removes
the empty source column. Implementation and publication evidence are recorded
in the project decision history after verification.
