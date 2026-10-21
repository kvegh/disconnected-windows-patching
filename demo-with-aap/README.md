# Windows demo with AAP orchestration

A separate browser walkthrough that adds connected AAP and a proposed Linux
execution node inside the secure network. It retains the original palette,
larger typography, growing workflow, server details and in-page code previews.
The original `demo/` assets remain independent.

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
data remains a separate internal-initiated HTTP pull from external IIS/Nexus.
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
