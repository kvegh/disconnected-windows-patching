# Windows demo with AAP orchestration

**[Open this visualization](https://kvegh.github.io/disconnected-windows-patching/demo-with-aap/)**

A browser walkthrough of the use case in eleven steps: infra, Windows basics
and activation, repository setup, external fill and export, internal import,
patch level, patching, baseline applications, upgrade and the proof report.
Each step names its stage snapshot and links to the real playbook.

The diagram shows a **proposed** topology with an AAP execution node inside
the isolated network. The deployed use case uses a shortcut instead (a second
NIC of the AAP VM in the isolated network, see `../README.md` and
`../TODO.md`). The page does not call AAP.

Each step can be opened directly; hovering a step previews its code, the
"Explore the Ansible" button pins the preview. Previous and Start over undo
the illustrated state.

## Files

- `index.html`: page and diagram.
- `src/scenario.js`: the eleven steps, their texts, code previews and source links.
- `src/orchestration.js`: phase planning and cancellable playback.
- `src/app.js`: controls, illustrated states, previews and server details.
- `src/styles.css`, `src/aap.css`: presentation.
- `tests/`: state model, source links (every linked playbook must exist),
  ordering, cancellation and UI handlers on a small Node DOM fixture.

## Local use

No dependencies. Open `index.html`, or serve it:

```bash
python3 -m http.server --directory demo-with-aap 8000
```

Source links need a Pages URL; locally add
`?site=https://OWNER.github.io/REPOSITORY/`.

Checks (Node.js 18 or newer):

```bash
node --check demo-with-aap/src/scenario.js
node --check demo-with-aap/src/orchestration.js
node --check demo-with-aap/src/app.js
node --test demo-with-aap/tests/*.test.cjs
```

The tests do not run a browser; rendered appearance is not verified.
`.github/workflows/deploy-demo.yml` runs these checks and publishes the page
to GitHub Pages (site root and `/demo-with-aap/`).
