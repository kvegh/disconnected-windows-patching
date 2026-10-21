/* Illustrative scheduling only. No platform or infrastructure requests. */
(() => {
  'use strict';
  const scenario = typeof module !== 'undefined' && module.exports ? require('./scenario.js') : globalThis.WindowsDemo;

  function planFor(number, meshConnected = false) {
    const step = scenario.steps[number - 1];
    if (!Number.isInteger(number) || !step) throw new RangeError('Unknown walkthrough action');
    const internal = step.scope === 'internal' || step.scope === 'both';
    const phases = [{
      key: 'schedule', duration: 280,
      title: 'AAP schedules the job',
      description: `Select the workflow job and its execution location: ${step.title.toLowerCase()}.`
    }];
    if (number === 1) phases.push({
      key: 'execute', duration: 600, scope: 'connected', target: 'deploy-external',
      title: 'External AAP deploys the external repository',
      description: 'The deployment arrow leads from external AAP to the external repository. That server appears first.'
    });
    if (internal) phases.push(meshConnected ? {
      key: 'outbound', duration: 550,
      title: 'Inside → out over the established mesh',
      description: 'The outward arrow highlights the connection initiated by the internal node. The mesh is already connected and will carry this job back to the node.'
    } : {
      key: 'connect', duration: 550,
      title: 'The execution node opens the connection',
      description: 'The proposed internal node initiates an outbound, authenticated Receptor mesh connection. It is reused for later jobs.'
    });
    if (internal) phases.push({
      key: 'dispatch', duration: 450,
      title: 'AAP dispatches the job over the mesh',
      description: 'The job travels to the execution node over the established bidirectional connection.'
    });
    phases.push({
      key: 'execute', duration: 450,
      title: number === 1 ? 'The internal execution node deploys its three VMs' : internal ? 'The execution node runs the internal work' : 'Connected execution runs the external work',
      description: number === 1
        ? 'Three deployment arrows lead to the internal repository and the Windows Server 2022 and 2025 VMs. These three servers appear together.'
        : internal
          ? `The proposed Linux node runs the playbook and contacts internal Windows hosts through WinRM.${step.scope === 'both' ? ' Connected execution handles the external repository.' : ''}`
          : 'A connected executor runs the playbook against the external Windows repository through WinRM.'
    });
    if (number === 1) Object.assign(phases.at(-1), { duration: 600, scope: 'internal', target: 'deploy-internal' });
    return Object.freeze(phases.map(phase => Object.freeze({ scope: step.scope, target: step.target, ...phase })));
  }

  async function play(plan, { onPhase, onComplete, isCancelled = () => false, wait = milliseconds => new Promise(resolve => setTimeout(resolve, milliseconds)) }) {
    for (const phase of plan) {
      if (isCancelled()) return false;
      onPhase(phase);
      await wait(phase.duration);
      if (isCancelled()) return false;
    }
    onComplete();
    return true;
  }

  const api = Object.freeze({ planFor, play });
  globalThis.WindowsOrchestration = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})();
