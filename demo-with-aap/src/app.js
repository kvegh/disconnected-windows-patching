(() => {
  'use strict';
  const { steps, stateAt, sourceUrl } = WindowsDemo;
  const { planFor, play } = WindowsOrchestration;
  const byId = id => document.getElementById(id);
  const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;
  let state = stateAt(0);
  let hoverTarget = null;
  let pinned = false;
  let restoringFocus = false;
  let hideTimer;
  let busy = false;
  let runGeneration = 0;
  let externalDeploymentReady = false;
  const popover = byId('code-popover');
  const list = byId('workflow-list');
  const diagram = document.querySelector('.architecture');

  function setText(id, text) { byId(id).textContent = text; }

  function scopeLabel(scope, target) {
    if (target === 'deployment') return 'External AAP → external repository · internal node → three VMs';
    if (scope === 'both') return 'Connected execution + proposed internal execution node';
    if (scope === 'internal') return 'Proposed internal execution node → Windows hosts (WinRM)';
    return 'Connected execution → external repository (WinRM)';
  }

  function positionPopover() {
    if (!hoverTarget || popover.hidden) return;
    const rect = hoverTarget.getBoundingClientRect();
    const width = popover.offsetWidth;
    const height = popover.offsetHeight;
    let left = rect.right + 12;
    if (left + width > innerWidth - 14) left = Math.max(14, rect.left - width - 12);
    if (innerWidth < 650) left = Math.max(14, (innerWidth - width) / 2);
    popover.style.left = `${Math.max(14, Math.min(left, innerWidth - width - 14))}px`;
    popover.style.top = `${Math.max(12, Math.min(rect.top, innerHeight - height - 12))}px`;
  }

  function hideCode(force = false) {
    if (pinned && !force) return;
    clearTimeout(hideTimer);
    const hadFocus = popover.contains(document.activeElement);
    popover.hidden = true;
    if (hoverTarget) hoverTarget.setAttribute('aria-expanded', 'false');
    if (hadFocus && hoverTarget?.isConnected) {
      restoringFocus = true;
      hoverTarget.focus();
      restoringFocus = false;
    }
    hoverTarget = null;
    pinned = false;
  }

  function showCode(step, target, pin = false) {
    clearTimeout(hideTimer);
    if (pinned && hoverTarget !== target && !pin) return;
    if (hoverTarget && hoverTarget !== target) hoverTarget.setAttribute('aria-expanded', 'false');
    hoverTarget = target;
    pinned = pin;
    target.setAttribute('aria-expanded', 'true');
    setText('code-title', step.title);
    setText('code-example', step.example);
    setText('code-executor', scopeLabel(step.scope, step.target));
    setText('source-filename', step.source);
    const link = sourceUrl(step.source, location.href);
    const anchor = byId('code-link');
    if (link) {
      anchor.href = link;
      anchor.removeAttribute('aria-disabled');
      anchor.textContent = 'Click here for the real code ↗';
    } else {
      anchor.removeAttribute('href');
      anchor.setAttribute('aria-disabled', 'true');
      anchor.textContent = 'Source links are available on the GitHub Pages site';
    }
    popover.hidden = false;
    positionPopover();
  }

  function scheduleHide() { clearTimeout(hideTimer); hideTimer = setTimeout(() => hideCode(), 260); }

  function createEntry(step, animate) {
    const li = document.createElement('li');
    if (animate && !reducedMotion) li.classList.add('arrive');
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'workflow-entry';
    button.setAttribute('aria-haspopup', 'dialog');
    button.setAttribute('aria-controls', 'code-popover');
    button.setAttribute('aria-expanded', 'false');
    const number = document.createElement('span');
    number.className = 'step-number';
    number.textContent = String(step.number).padStart(2, '0');
    const content = document.createElement('span');
    const title = document.createElement('span');
    title.className = 'step-title'; title.textContent = step.title;
    const description = document.createElement('span');
    description.className = 'step-description'; description.textContent = step.short;
    const hint = document.createElement('span');
    hint.className = 'step-code-hint'; hint.textContent = '{ } Explore the Ansible';
    content.append(title, description, hint); button.append(number, content); li.append(button);
    button.addEventListener('pointerenter', () => showCode(step, button));
    button.addEventListener('pointerleave', scheduleHide);
    button.addEventListener('focus', () => { if (!restoringFocus) showCode(step, button); });
    button.addEventListener('blur', event => { if (!popover.contains(event.relatedTarget)) scheduleHide(); });
    button.addEventListener('click', event => {
      if (pinned && hoverTarget === button) { hideCode(true); return; }
      showCode(step, button, true);
      if (event.detail === 0) byId('close-code').focus();
    });
    return li;
  }

  function render(stage) {
    externalDeploymentReady = false;
    diagram.dataset.externalDeployed = 'false';
    const previous = state;
    state = stateAt(stage);
    hideCode(true);
    const rewind = state.stage < previous.stage;
    diagram.classList.toggle('rewinding', rewind);
    while (list.children.length > state.stage) list.lastElementChild.remove();
    while (list.children.length < state.stage) list.append(createEntry(steps[list.children.length], !rewind));
    [...list.children].forEach((li, index) => {
      const button = li.firstElementChild;
      const current = index === state.stage - 1;
      button.classList.toggle('current', current);
      if (current) button.setAttribute('aria-current', 'step');
      else button.removeAttribute('aria-current');
    });
    byId('workflow-empty').hidden = state.stage !== 0;
    // Flex display on the placeholder must not override the HTML hidden state.
    byId('workflow-empty').style.display = state.stage ? 'none' : '';
    setText('workflow-count', `${state.stage} ${state.stage === 1 ? 'action' : 'actions'}`);
    setText('action-count', state.stage ? `Action ${String(state.stage).padStart(2, '0')} / ${steps.length}` : 'Getting started');
    setText('current-title', state.current?.title || 'AAP is ready. Let’s build the datacenter.');
    setText('current-description', state.current?.description || 'Watch AAP dispatch each job before the Windows environment changes. You set the pace.');
    setText('next-label', state.next?.title || 'All actions complete');
    byId('previous').disabled = state.stage === 0;
    byId('next').disabled = !state.next;
    byId('progress-fill').style.width = `${state.stage / steps.length * 100}%`;
    byId('architecture-empty').classList.toggle('is-hidden', state.servers);
    setText('architecture-summary', state.servers ? '4 Windows · AAP + execution' : 'AAP + proposed execution');
    setText('flow-caption', state.current?.flow || 'The architecture grows with the workflow.');
    diagram.dataset.phase = state.stage ? 'complete' : 'idle';
    diagram.dataset.scope = state.current?.scope || '';
    diagram.dataset.target = state.current?.target || '';
    diagram.classList.toggle('mesh-visible', state.stage >= 1);
    setText('controller-status', 'Ready to schedule jobs');
    setText('execution-status', state.stage >= 1 ? 'Mesh connected · ready for work' : 'Ready to initiate outbound mesh');
    setText('execution-caption', state.current ? `Job complete · ${scopeLabel(state.current.scope, state.current.target)}` : 'AAP schedules. The execution node runs locally.');
    byId('execution-pending').hidden = true;

    document.querySelectorAll('[data-at]').forEach(element => {
      const visible = state.stage >= Number(element.dataset.at);
      element.classList.toggle('is-visible', visible);
      if (element.classList.contains('server-node')) element.setAttribute('tabindex', visible ? '0' : '-1');
    });
    document.querySelectorAll('[data-flow]').forEach(element => {
      element.classList.toggle('flow-active', element.dataset.flow.split(',').map(Number).includes(state.stage));
    });
    diagram.classList.toggle('flow-running', state.stage === 4);
    diagram.classList.toggle('transfer-running', state.stage === 6);
    diagram.classList.toggle('transfer-shown', state.imported);
    diagram.classList.toggle('client-running', [8, 9, 10].includes(state.stage));

    setText('external-status', state.exported ? 'Export published' : state.acquired ? 'Selected content downloaded' : state.services ? 'Repository services ready' : state.configured ? 'Windows configured' : 'Freshly deployed');
    setText('external-detail', state.exported ? 'Management-only HTTP publication' : state.acquired ? 'OS · .NET · 7-Zip · Git' : 'Prepared Windows base image');
    setText('internal-status', state.baseline ? 'April 2026 baseline selected' : state.imported ? 'Pulled, verified and imported' : state.services ? 'Ready to pull external exports' : state.configured ? 'Windows configured' : 'Freshly deployed');
    setText('internal-detail', state.imported ? 'Autonomous WSUS · internal package feeds' : state.configured ? 'Management NIC + isolated client NIC' : 'Prepared Windows base image');
    for (const year of ['2022', '2025']) {
      setText(`server${year}-status`, state.verified ? 'Final checks passed' : state.patched ? 'April OS + .NET baseline' : state.configured ? 'Internal sources configured' : 'Freshly deployed');
      setText(`server${year}-detail`, state.verified ? 'Expected versions · no pending reboot' : state.patched ? (year === '2022' ? 'Build 20348.5020' : 'Build 26100.32690') : 'Managed Windows endpoint');
      for (const [prefix, value] of [['zip', state.versions?.zip || '26.03'], ['git', state.versions?.git || '2.55']]) {
        const element = byId(`${prefix}${year}`);
        const changed = element.textContent !== value;
        element.textContent = value;
        element.classList.remove('version-pop');
        if (changed && !rewind && !reducedMotion) { void element.getBoundingClientRect(); element.classList.add('version-pop'); }
      }
    }
    setText('announcer', state.current ? `Action ${state.stage}: ${state.current.title}. ${state.current.short}` : 'Walkthrough reset. The datacenter is empty.');
    if (state.stage) requestAnimationFrame(() => {
      const last = list.lastElementChild;
      const scroll = byId('workflow-scroll');
      if (last) scroll.scrollTo({ top: Math.max(0, last.offsetTop - scroll.offsetTop - scroll.clientHeight + last.offsetHeight + 20), behavior: reducedMotion || rewind ? 'instant' : 'smooth' });
    });
  }

  function navigateTo(stage) {
    runGeneration++;
    busy = false;
    render(stage);
  }

  async function advance() {
    if (busy || !state.next) return;
    const targetStage = state.stage + 1;
    const selected = state.next;
    const generation = ++runGeneration;
    busy = true;
    hideCode(true);
    diagram.classList.remove('flow-running', 'transfer-running', 'client-running');
    document.querySelectorAll('[data-flow]').forEach(element => element.classList.remove('flow-active'));
    byId('next').disabled = true;
    byId('previous').disabled = true;
    setText('action-count', `Launching action ${String(targetStage).padStart(2, '0')} / ${steps.length}`);
    setText('current-title', selected.title);
    setText('current-description', selected.description);
    setText('next-label', 'AAP is running this action');
    byId('execution-pending').hidden = false;
    try {
      await play(planFor(targetStage, state.stage >= 1), {
        isCancelled: () => generation !== runGeneration,
        wait: milliseconds => reducedMotion ? Promise.resolve() : new Promise(resolve => setTimeout(resolve, milliseconds)),
        onPhase: phase => {
          diagram.dataset.phase = phase.key;
          diagram.dataset.scope = phase.scope;
          diagram.dataset.target = phase.target;
          diagram.classList.toggle('mesh-visible', state.stage >= 1 || ['connect', 'outbound', 'dispatch'].includes(phase.key) || (phase.key === 'execute' && ['internal', 'both'].includes(phase.scope)));
          if (targetStage === 1 && ['connect', 'dispatch'].includes(phase.key)) {
            externalDeploymentReady = true;
            diagram.dataset.externalDeployed = 'true';
            const external = document.querySelector('[data-node="external"]');
            external.classList.add('is-visible');
            external.setAttribute('tabindex', '0');
            byId('architecture-empty').classList.add('is-hidden');
          }
          setText('pending-title', phase.title);
          setText('pending-description', phase.description);
          setText('execution-caption', phase.title);
          setText('flow-caption', phase.description);
          setText('controller-status', phase.key === 'schedule' ? 'Scheduling the next job' : phase.key === 'connect' ? 'Awaiting outbound mesh' : phase.key === 'outbound' ? 'Established mesh · inside → out' : phase.key === 'dispatch' ? 'Dispatching over the mesh' : 'Job running on its executor');
          setText('execution-status', phase.key === 'connect' ? 'Opening outbound mesh' : phase.key === 'outbound' ? 'Reusing outbound mesh' : phase.key === 'dispatch' ? 'Receiving the job over mesh' : phase.key === 'execute' && phase.target === 'deploy-internal' ? 'Deploying three internal VMs' : phase.key === 'execute' && ['internal', 'both'].includes(phase.scope) ? 'Running the internal playbook' : state.stage >= 1 ? 'Mesh connected · ready for work' : 'Ready to initiate outbound mesh');
          setText('announcer', `${phase.title}. ${phase.description}`);
          const scroll = byId('workflow-scroll');
          scroll.scrollTo({ top: scroll.scrollHeight, behavior: reducedMotion ? 'instant' : 'smooth' });
          if (phase.key === 'execute' && !reducedMotion) requestAnimationFrame(() => {
            if (generation !== runGeneration) return;
            document.querySelectorAll('[data-job-motion]').forEach(motion => motion.beginElement?.());
          });
        },
        onComplete: () => { busy = false; render(targetStage); }
      });
    } finally {
      if (generation === runGeneration) {
        busy = false;
        byId('previous').disabled = state.stage === 0;
        byId('next').disabled = !state.next;
      }
    }
  }

  function showServer(id) {
    if (id === 'controller' || id === 'execution') {
      const controller = id === 'controller';
      setText('server-dialog-title', controller ? 'AAP in the connected network' : 'Proposed internal execution node');
      setText('server-dialog-description', controller ? 'AAP schedules the workflow and selects where each job runs. This card groups the controller and connected execution for clarity.' : 'A Linux execution node inside the secure network initiates outbound mesh connectivity, receives dispatched jobs and runs playbooks locally. This node is proposed and is not deployed in the current lab.');
      const rows = controller
        ? [['Network', 'Connected'], ['Role', 'Schedule and dispatch jobs'], ['Connected work', 'Existing connected executor'], ['Internal work', 'Proposed remote execution node']]
        : [['Status', 'Proposed; not deployed'], ['Operating system', 'Linux'], ['Connection initiation', 'Internal → connected AAP'], ['Job delivery', 'Over established Receptor mesh'], ['Windows management', 'WinRM from this node'], ['Export downloads', 'Internal repository initiates HTTP pull']];
      const details = byId('server-dialog-details'); details.replaceChildren();
      rows.forEach(([key, value]) => {
        const row = document.createElement('div'); row.className = 'detail-row';
        const dt = document.createElement('dt'); dt.textContent = key;
        const dd = document.createElement('dd'); dd.textContent = value;
        row.append(dt, dd); details.append(row);
      });
      byId('server-dialog').showModal();
      return;
    }
    if (!state.servers && !(id === 'external' && externalDeploymentReady)) return;
    hideCode(true);
    const external = id === 'external';
    const repository = external || id === 'internal';
    const year = id === 'server2025' ? '2025' : '2022';
    setText('server-dialog-title', repository ? `${external ? 'External' : 'Internal'} repository` : `Windows Server ${year}`);
    setText('server-dialog-description', repository ? (external ? 'Acquires selected content on the connected network and serves exports requested by the internal repository.' : 'Initiates downloads over its management NIC, verifies the exports and serves the isolated client network.') : 'Receives OS updates and application packages from the internal repository.');
    const rows = [['Operating system', `Windows Server ${year}`], ['Configuration', state.configured ? 'Windows configured' : 'Fresh base image']];
    if (repository) {
      rows.push(['Services', state.services ? `WSUS + Nexus${external && state.exported ? ' + IIS export' : ''}` : 'Not configured yet']);
      rows.push(['Content', external ? (state.acquired ? 'Selected downloads present' : 'Not acquired yet') : (state.imported ? 'Imported and verified' : 'Not imported yet')]);
      if (state.imported) rows.push(['Export transfer', external ? 'Serves internal HTTP GET requests' : 'Initiates the HTTP pull']);
      if (external && state.exported) rows.push(['WSUS export', '.xml.gz metadata + separate files']);
      if (!external && state.baseline) rows.push(['Patch policy', 'April 2026 ceiling']);
    } else {
      rows.push(['OS baseline', state.patched ? 'April 2026' : 'Base image']);
      if (state.patched) rows.push(['OS build', year === '2022' ? '20348.5020' : '26100.32690']);
      rows.push(['7-Zip', state.versions?.zip || 'Not installed yet']);
      rows.push(['Git for Windows', state.versions?.gitFull || 'Not installed yet']);
      rows.push(['Application feed', state.applications === 'current' ? 'Internal current' : state.applications === 'baseline' ? 'Internal baseline' : 'Not used yet']);
      rows.push(['Final verification', state.verified ? 'Passed; no pending reboot' : 'Not performed yet']);
    }
    const details = byId('server-dialog-details'); details.replaceChildren();
    rows.forEach(([key, value]) => {
      const row = document.createElement('div'); row.className = 'detail-row';
      const dt = document.createElement('dt'); dt.textContent = key;
      const dd = document.createElement('dd'); dd.textContent = value;
      row.append(dt, dd); details.append(row);
    });
    byId('server-dialog').showModal();
  }

  byId('next').addEventListener('click', advance);
  byId('previous').addEventListener('click', () => { if (!busy) navigateTo(state.stage - 1); });
  byId('reset').addEventListener('click', () => navigateTo(0));
  byId('close-code').addEventListener('click', () => hideCode(true));
  popover.addEventListener('pointerenter', () => clearTimeout(hideTimer));
  popover.addEventListener('pointerleave', scheduleHide);
  popover.addEventListener('focusin', () => clearTimeout(hideTimer));
  popover.addEventListener('focusout', event => { if (!popover.contains(event.relatedTarget) && event.relatedTarget !== hoverTarget) scheduleHide(); });
  byId('close-server').addEventListener('click', () => byId('server-dialog').close());
  byId('server-dialog').addEventListener('click', event => { if (event.target === event.currentTarget) { const rect = event.currentTarget.getBoundingClientRect(); if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) event.currentTarget.close(); } });
  document.querySelectorAll('[data-node]').forEach(node => {
    node.addEventListener('click', () => showServer(node.dataset.node));
    node.addEventListener('keydown', event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); showServer(node.dataset.node); } });
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape') { hideCode(true); return; }
    if (byId('server-dialog').open || !popover.hidden || event.altKey || event.ctrlKey || event.metaKey) return;
    if (event.target.closest('button,a,input,textarea,select,[contenteditable],[role="button"]')) return;
    if (event.key === 'ArrowRight') { event.preventDefault(); advance(); }
    if (event.key === 'ArrowLeft') { event.preventDefault(); if (!busy) navigateTo(state.stage - 1); }
    if (event.key.toLowerCase() === 'r') navigateTo(0);
  });
  document.addEventListener('pointerdown', event => { if (!popover.hidden && !popover.contains(event.target) && !hoverTarget?.contains(event.target)) hideCode(true); });
  addEventListener('resize', positionPopover);
  byId('workflow-scroll').addEventListener('scroll', () => { if (pinned) positionPopover(); else hideCode(); });
  render(0);
})();
