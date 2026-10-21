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
    if (internal && !meshConnected) phases.push({
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
      title: step.scope === 'hypervisor' ? 'Connected execution provisions the VMs' : internal ? 'The execution node runs the internal work' : 'Connected execution runs the external work',
      description: step.scope === 'hypervisor'
        ? 'An existing connected executor contacts the virtualization host over SSH before the Windows VMs appear.'
        : internal
          ? `The proposed Linux node runs the playbook and contacts internal Windows hosts through WinRM.${step.scope === 'both' ? ' Connected execution handles the external repository.' : ''}`
          : 'A connected executor runs the playbook against the external Windows repository through WinRM.'
    });
    return Object.freeze(phases.map(phase => Object.freeze({ ...phase, scope: step.scope, target: step.target })));
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
