const { test } = require('node:test');
const assert = require('node:assert/strict');
const { planFor, play } = require('../src/orchestration.js');
const { steps } = require('../src/scenario.js');

test('external AAP deploys one repository before internal execution deploys three VMs', () => {
  const plan = planFor(1);
  assert.deepEqual(plan.map(phase => phase.key), ['schedule', 'execute', 'connect', 'dispatch', 'execute']);
  const execution = plan.filter(phase => phase.key === 'execute');
  assert.deepEqual(execution.map(phase => phase.scope), ['connected', 'internal']);
  assert.deepEqual(execution.map(phase => phase.target), ['deploy-external', 'deploy-internal']);
  assert.match(execution[1].description, /Three deployment arrows/);
});

test('every internal action shows inside-out mesh before dispatch and local execution', () => {
  for (const step of steps.filter(step => step.scope !== 'connected')) {
    for (const connected of [false, true]) {
      const plan = planFor(step.number, connected);
      const executeIndex = plan.findLastIndex(phase => phase.key === 'execute');
      assert.deepEqual(plan.slice(executeIndex - 2, executeIndex + 1).map(phase => phase.key),
        [connected ? 'outbound' : 'connect', 'dispatch', 'execute'], `action ${step.number}, mesh connected: ${connected}`);
      if (connected) {
        assert.equal(plan.some(phase => phase.key === 'connect'), false);
        assert.match(plan[executeIndex - 2].description, /already connected/);
      } else {
        assert.match(plan[executeIndex - 2].description, /initiates an outbound/);
      }
    }
  }
  for (const stage of [8, 9, 10, 11]) {
    assert.equal(planFor(stage, true).at(-1).target, 'clients');
    assert.equal(planFor(stage, true).at(-1).scope, 'internal');
  }
  assert.throws(() => planFor(0), RangeError);
});

test('connected-only actions leave the internal mesh idle', () => {
  for (const step of steps.filter(step => step.scope === 'connected')) {
    for (const connected of [false, true]) {
      const plan = planFor(step.number, connected);
      assert.deepEqual(plan.map(phase => phase.key), ['schedule', 'execute']);
      assert.equal(plan.at(-1).scope, 'connected');
    }
  }
});

test('complete deployment waits for both network-specific execution phases', async () => {
  const phases = [];
  const releases = [];
  let changed = false;
  const plan = planFor(1, false);
  const running = play(plan, {
    onPhase: phase => phases.push(phase.key),
    onComplete: () => { changed = true; },
    wait: () => new Promise(resolve => releases.push(resolve))
  });
  for (let index = 0; index < plan.length; index++) {
    assert.equal(changed, false);
    assert.equal(phases.at(-1), plan[index].key);
    releases.shift()();
    await Promise.resolve();
  }
  assert.equal(await running, true);
  assert.equal(changed, true);
  assert.deepEqual(phases, ['schedule', 'execute', 'connect', 'dispatch', 'execute']);
});

test('reset cancels a pending action without applying a later infrastructure result', async () => {
  let cancelled = false;
  let changed = false;
  let release;
  const phases = [];
  const running = play(planFor(1, false), {
    isCancelled: () => cancelled,
    onPhase: phase => phases.push(phase.key),
    onComplete: () => { changed = true; },
    wait: () => new Promise(resolve => { release = resolve; })
  });
  release();
  await Promise.resolve();
  release();
  await Promise.resolve();
  assert.deepEqual(phases, ['schedule', 'execute', 'connect']);
  cancelled = true;
  release();
  assert.equal(await running, false);
  assert.equal(changed, false);
  assert.deepEqual(phases, ['schedule', 'execute', 'connect']);
});

test('reset during a repeated outward cue prevents job dispatch and execution', async () => {
  let cancelled = false;
  let changed = false;
  let release;
  const phases = [];
  const running = play(planFor(6, true), {
    isCancelled: () => cancelled,
    onPhase: phase => phases.push(phase.key),
    onComplete: () => { changed = true; },
    wait: () => new Promise(resolve => { release = resolve; })
  });
  release();
  await Promise.resolve();
  assert.deepEqual(phases, ['schedule', 'outbound']);
  cancelled = true;
  release();
  assert.equal(await running, false);
  assert.equal(changed, false);
  assert.deepEqual(phases, ['schedule', 'outbound']);
});
