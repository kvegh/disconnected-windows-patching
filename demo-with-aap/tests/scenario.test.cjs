const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { steps, stateAt, sourceUrl } = require('../src/scenario.js');

test('previous removes later features and restores the baseline application versions', () => {
  assert.equal(stateAt(10).versions.zip, '26.04');
  assert.equal(stateAt(9).versions.zip, '26.03');
  assert.equal(stateAt(8).versions, null);
  assert.equal(stateAt(7).patched, false);
  assert.equal(stateAt(5).imported, false);
  assert.equal(stateAt(0).servers, false);
  assert.deepEqual(stateAt(0).history, []);
});

test('content publication precedes import, policy, patching and verification', () => {
  for (let stage = 0; stage <= steps.length; stage++) {
    const state = stateAt(stage);
    assert.equal(state.history.length, stage);
    if (state.imported) assert.ok(state.exported && state.acquired);
    if (state.patched) assert.ok(state.imported && state.baseline);
    if (state.verified) assert.equal(state.applications, 'current');
    assert.equal(state.next?.number || null, stage < steps.length ? stage + 1 : null);
  }
  assert.equal(stateAt(-1).stage, 0);
  assert.equal(stateAt(100).stage, steps.length);
});

test('every code preview links to an existing real playbook in the repository', () => {
  const root = path.resolve(__dirname, '../..');
  for (const step of steps) {
    assert.ok(fs.existsSync(path.join(root, step.source)), step.source);
    assert.ok(step.example.startsWith('- name:'));
    const url = new URL(sourceUrl(step.source, 'https://example.github.io/windows-demo/'));
    assert.equal(url.hostname, 'github.com');
    assert.equal(url.pathname, `/example/windows-demo/blob/main/${step.source}`);
  }
  assert.equal(sourceUrl(steps[0].source, 'http://localhost/'), null);
  assert.match(sourceUrl(steps[0].source, 'http://localhost/?site=https://example.github.io/windows-demo/'), /github\.com\/example\/windows-demo\/blob/);
  assert.equal(sourceUrl(steps[0].source, 'http://localhost/?site=invalid'), null);
  assert.throws(() => sourceUrl('../secrets', 'https://example.github.io/windows-demo/'));
});

test('the page has no missing local assets or duplicate IDs', () => {
  const root = path.resolve(__dirname, '..');
  const html = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
  const ids = [...html.matchAll(/\bid="([^"]+)"/g)].map(match => match[1]);
  assert.equal(new Set(ids).size, ids.length);
  for (const [, asset] of html.matchAll(/(?:src|href)="(src\/[^"#]+)"/g)) assert.ok(fs.existsSync(path.join(root, asset)), asset);
  const script = fs.readFileSync(path.join(root, 'src/app.js'), 'utf8');
  for (const [, id] of script.matchAll(/(?:byId|setText)\('([^']+)'/g)) assert.ok(ids.includes(id), id);
});
