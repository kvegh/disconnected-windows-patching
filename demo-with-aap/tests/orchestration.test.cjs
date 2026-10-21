const { test } = require('node:test');
const assert = require('node:assert/strict');
const { planFor, play } = require('../src/orchestration.js');

test('VM creation uses connected execution and the hypervisor before guests exist', () => {
  const plan = planFor(1);
  assert.deepEqual(plan.map(phase => phase.key), ['schedule', 'execute']);
  assert.ok(plan.every(phase => phase.scope === 'hypervisor' && phase.target === 'hypervisor'));
  assert.match(plan.at(-1).description, /SSH/);
});

test('the first internal job opens outbound mesh before dispatch and local execution', () => {
  assert.deepEqual(planFor(2, false).map(phase => phase.key), ['schedule', 'connect', 'dispatch', 'execute']);
  assert.match(planFor(2, false)[1].description, /initiates an outbound/);
  assert.deepEqual(planFor(6, true).map(phase => phase.key), ['schedule', 'dispatch', 'execute']);
  assert.equal(planFor(6, true).at(-1).scope, 'internal');
  for (const stage of [8, 9, 10, 11]) {
    assert.equal(planFor(stage, true).at(-1).target, 'clients');
    assert.equal(planFor(stage, true).at(-1).scope, 'internal');
  }
  for (const stage of [4, 5]) assert.equal(planFor(stage, true).at(-1).scope, 'connected');
  assert.throws(() => planFor(0), RangeError);
});

test('infrastructure changes wait until every orchestration phase completes', async () => {
  const phases = [];
  const releases = [];
  let changed = false;
  const plan = planFor(2, false);
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
  assert.deepEqual(phases, ['schedule', 'connect', 'dispatch', 'execute']);
});

test('reset cancels a pending action without applying a later infrastructure result', async () => {
  let cancelled = false;
  let changed = false;
  let release;
  const phases = [];
  const running = play(planFor(2, false), {
    isCancelled: () => cancelled,
    onPhase: phase => phases.push(phase.key),
    onComplete: () => { changed = true; },
    wait: () => new Promise(resolve => { release = resolve; })
  });
  cancelled = true;
  release();
  assert.equal(await running, false);
  assert.equal(changed, false);
  assert.deepEqual(phases, ['schedule']);
});
