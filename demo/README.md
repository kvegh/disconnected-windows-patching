# Interactive Windows demo

A browser-based, presenter-paced walkthrough of the disconnected Windows demo.
The page has three main sections: Next/Previous controls, an accumulating workflow,
and an architecture diagram that gains servers, services, content and connections.
Previous rewinds both the workflow and the illustrated environment; Start over
returns to an empty datacenter. There is no autoplay or simulated waiting period.

The visual palette uses clear blue accents, light cyan network areas and restrained
amber export details. Text is 20% larger than the initial presentation, including
diagram labels, responsive layouts and code previews. Controls and popovers have
additional room for the larger text.

This version is an **illustrative walkthrough**, not an AAP client. Clicking an
action updates the visualization immediately. It does not launch jobs, connect to
VMs or establish evidence about the current deployed environment. The displayed
versions reflect the documented demo scenario. A future live mode needs its own
authentication, trusted job results and explicit execution design.

## Interaction

- Next adds an action and reveals its matching architecture changes.
- Previous removes the latest action and restores the preceding state.
- Hover, focus or select a workflow item to see simplified example Ansible.
  Select pins the preview open. Its source link opens the real playbook in a new
  tab. Escape or the close button dismisses the preview.
- Select a server to inspect its configuration at the current walkthrough step.
- Arrow keys navigate when focus is outside an interactive control. R resets.
- Reduced-motion preferences disable the drop/pop animations and moving particles.

The arrows illustrate data direction, not measured throughput or real-time job
progress. WSUS downloads come from Microsoft. The IIS export consists of compressed
`.xml.gz` metadata, a manifest and separate update binaries, **not one WSUS ZIP**.
The separate application ZIP is served through Nexus. Transfer uses the internal
repository's management connection; the diagram does not claim a physical air gap.
OS patching, application installation and application upgrades remain distinct.
The eleven illustrated actions group the underlying workflow jobs.

## Layout and local use

- `index.html`: page structure and SVG architecture.
- `src/scenario.js`: ordered actions, example code and rewindable state.
- `src/app.js`: controls, architecture updates and in-page code previews.
- `src/styles.css`: layout, appearance and motion.
- `tests/scenario.test.cjs`: state order, rewind and source/asset integrity checks.

No dependency installation, package manager, external fonts or build is required.
Open `index.html` directly, or serve this directory with an existing Python:

```bash
python3 -m http.server --directory demo 8000
```

Source links derive their repository from the deployed GitHub Pages URL. For a
local preview, add `?site=https://OWNER.github.io/REPOSITORY/` to the URL using
the actual public Pages location. Without this, local previews explain that
source links are available on the published site.

Run checks with an existing Node.js 18 or newer:

```bash
node --check demo/src/scenario.js
node --check demo/src/app.js
node --test demo/tests/scenario.test.cjs
git diff --check
```

There is no dependency lockfile because the demo has no third-party dependencies.
There is no formatter or linter dependency; retain the existing plain HTML,
CSS and JavaScript conventions and use the syntax checks above.

## GitHub Pages

The repository's Pages publishing source is GitHub Actions.
`.github/workflows/deploy-demo.yml` publishes only the page and its `src/`
assets when those files or the publishing workflow change on `main`, or when
manually dispatched. It excludes the repository's automation configuration,
Vault files, documentation and test files from the deployment artifact.
The same workflow runs the focused Node checks before publishing.

The page uses generic labels and carries no controller endpoint, inventory
address, credential, authentication token or environment-specific hostname.
