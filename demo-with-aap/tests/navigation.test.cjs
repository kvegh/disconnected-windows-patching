// Execute the real UI handlers with a small DOM fixture; no browser package is required.
// Scope and limitations: ../../tests/README.md#javascript-walkthrough-tests
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const WindowsDemo = require('../src/scenario.js');
const WindowsOrchestration = require('../src/orchestration.js');

function loadUi() {
  let document;
  const timers = new Map();
  let timerId = 0;
  class Element {
    constructor(tagName) {
      this.tagName = tagName.toUpperCase();
      this.children = [];
      this.attributes = new Map();
      this.dataset = {};
      this.style = {};
      this.listeners = new Map();
      this.className = '';
      this.hidden = false;
      this.disabled = false;
      this.scrollTop = 0;
      this.clientHeight = 400;
      this.offsetWidth = 300;
      this.offsetHeight = 100;
      this._text = '';
      this.classList = {
        contains: name => this.className.split(/\s+/).includes(name),
        add: (...names) => { this.className = [...new Set(this.className.split(/\s+/).filter(Boolean).concat(names))].join(' '); },
        remove: (...names) => { this.className = this.className.split(/\s+/).filter(name => !names.includes(name)).join(' '); },
        toggle: (name, force) => {
          const on = force === undefined ? !this.classList.contains(name) : force;
          this.classList[on ? 'add' : 'remove'](name);
          return on;
        }
      };
    }
    set textContent(value) { this._text = String(value); this.replaceChildren(); }
    get textContent() { return this._text + this.children.map(child => child.textContent).join(''); }
    get firstElementChild() { return this.children[0] || null; }
    get lastElementChild() { return this.children.at(-1) || null; }
    get isConnected() { return this === document.root || Boolean(this.parentNode?.isConnected); }
    get offsetTop() { return this.tagName === 'LI' ? this.parentNode.children.indexOf(this) * 130 : 0; }
    get scrollHeight() { return 1600; }
    append(...children) { children.forEach(child => { child.parentNode = this; this.children.push(child); }); }
    replaceChildren(...children) { this.children.forEach(child => { child.parentNode = null; }); this.children = []; this.append(...children); }
    remove() { if (this.parentNode) this.parentNode.children.splice(this.parentNode.children.indexOf(this), 1); this.parentNode = null; }
    setAttribute(name, value) {
      this.attributes.set(name, String(value));
      if (name === 'class') this.className = String(value);
      if (name.startsWith('data-')) this.dataset[name.slice(5).replace(/-([a-z])/g, (_, letter) => letter.toUpperCase())] = String(value);
    }
    getAttribute(name) { return name === 'class' ? this.className : (this.attributes.get(name) ?? null); }
    removeAttribute(name) { this.attributes.delete(name); }
    matches(selector) {
      return selector.split(',').some(part => {
        const item = part.trim();
        if (item.startsWith('.')) return this.classList.contains(item.slice(1));
        const attr = item.match(/^\[([^=\]]+)(?:="([^"]*)")?\]$/);
        if (attr) return attr[2] === undefined ? this.getAttribute(attr[1]) !== null : this.getAttribute(attr[1]) === attr[2];
        return this.tagName.toLowerCase() === item;
      });
    }
    querySelectorAll(selector) { return this.children.flatMap(child => (child.matches(selector) ? [child] : []).concat(child.querySelectorAll(selector))); }
    querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
    closest(selector) { return this.matches(selector) ? this : (this.parentNode?.closest(selector) || null); }
    contains(node) { return node === this || this.children.some(child => child.contains(node)); }
    addEventListener(type, callback) { const entries = this.listeners.get(type) || []; entries.push(callback); this.listeners.set(type, entries); }
    fire(type, properties = {}) {
      const event = { target: this, currentTarget: this, detail: 1, preventDefault() {}, ...properties };
      let result;
      for (const callback of this.listeners.get(type) || []) result = callback(event);
      return result;
    }
    focus() { document.activeElement = this; this.fire('focus'); }
    getBoundingClientRect() {
      const row = this.closest('li');
      const top = row ? row.offsetTop - document.getElementById('workflow-scroll').scrollTop : 0;
      const height = row ? 120 : 400;
      return { left: 0, right: 300, top, bottom: top + height, width: 300, height };
    }
    scrollTo({ top }) { this.scrollTop = top; }
    showModal() { this.open = true; }
    close() { this.open = false; }
  }
  const root = new Element('main');
  document = {
    root, activeElement: null,
    createElement: tag => new Element(tag),
    getElementById: id => root.querySelectorAll('[id]').find(element => element.getAttribute('id') === id),
    querySelector: selector => root.querySelector(selector),
    querySelectorAll: selector => root.querySelectorAll(selector),
    addEventListener(type, callback) { root.addEventListener(type, callback); }
  };
  // Only static nodes addressed by the UI are needed; workflow entries form a real fixture tree.
  const html = fs.readFileSync(path.join(__dirname, '../index.html'), 'utf8');
  for (const [, tag, source] of html.matchAll(/<([a-z][\w-]*)\b([^>]*)>/gi)) {
    const attrs = new Map([...source.matchAll(/([\w-]+)="([^"]*)"/g)].map(match => [match[1], match[2]]));
    if (![...attrs.keys()].some(name => name === 'id' || name.startsWith('data-')) && !attrs.get('class')?.split(' ').includes('architecture')) continue;
    const element = new Element(tag);
    attrs.forEach((value, name) => element.setAttribute(name, value));
    if (/\bhidden\b/.test(source)) element.hidden = true;
    root.append(element);
  }
  const context = {
    document, WindowsDemo, WindowsOrchestration,
    location: { href: 'https://example.github.io/windows-demo/demo-with-aap/' },
    matchMedia: () => ({ matches: false }),
    innerWidth: 1920, innerHeight: 1200,
    setTimeout: callback => { const id = ++timerId; timers.set(id, callback); return id; },
    clearTimeout: id => timers.delete(id),
    requestAnimationFrame: callback => { callback(); return 0; },
    addEventListener() {}
  };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../src/app.js'), 'utf8'), context);
  return {
    document,
    get: id => document.getElementById(id),
    rows: () => document.getElementById('workflow-list').children,
    flushTimers() { const pending = [...timers.values()]; timers.clear(); pending.forEach(callback => callback()); }
  };
}

test('all stages stay available for forward/backward clicks without losing the selected button', () => {
  const ui = loadUi();
  assert.equal(ui.rows().length, 11);
  const future = ui.rows()[9].querySelector('.workflow-step');
  assert.equal(future.tagName, 'BUTTON');
  assert.equal(future.querySelector('button'), null);
  future.focus();
  future.fire('click', { detail: 0 }); // Native keyboard button activation also dispatches click.
  assert.equal(ui.get('current-title').textContent, WindowsDemo.steps[9].title);
  assert.equal(ui.get('zip2022').textContent, '26.04');
  assert.equal(future.getAttribute('aria-current'), 'step');
  assert.equal(ui.rows()[0].firstElementChild.classList.contains('completed'), true);
  assert.equal(ui.rows()[9].firstElementChild.classList.contains('current'), true);
  assert.equal(ui.rows()[10].firstElementChild.classList.contains('future'), true);
  assert.equal(ui.get('workflow-count').textContent, '10 / 11 actions');
  assert.equal(ui.document.activeElement, future);
  assert.equal(ui.rows().length, 11);
  ui.rows()[3].querySelector('.workflow-step').fire('click');
  assert.equal(ui.get('current-title').textContent, WindowsDemo.steps[3].title);
  assert.equal(ui.get('zip2022').textContent, '26.03');
  assert.equal(future.getAttribute('aria-current'), null);
  assert.equal(ui.rows().length, 11);
  assert.equal(ui.document.querySelector('[data-at="6"]').classList.contains('is-visible'), false);
  const selected = ui.rows()[3].getBoundingClientRect();
  assert.ok(selected.top >= 0 && selected.bottom <= 400);
});

test('hover preview and the separate code pin remain usable without changing stages', () => {
  const ui = loadUi();
  const row = ui.rows()[2].querySelector('.workflow-entry');
  const hint = row.querySelector('.step-code-hint');
  row.fire('pointerenter');
  assert.equal(ui.get('code-popover').hidden, false);
  assert.equal(ui.get('code-title').textContent, WindowsDemo.steps[2].title);
  const stage = ui.get('current-title').textContent;
  hint.fire('click');
  row.fire('pointerleave');
  row.fire('pointerenter');
  row.fire('pointerleave');
  ui.flushTimers();
  assert.equal(ui.get('code-popover').hidden, false);
  assert.equal(ui.get('current-title').textContent, stage);
  hint.fire('click');
  assert.equal(ui.get('code-popover').hidden, true);
});

test('clicking a stage cancels an unfinished Next animation and reset retains navigation', async () => {
  const ui = loadUi();
  const running = ui.get('next').fire('click');
  ui.rows()[8].querySelector('.workflow-step').fire('click');
  ui.flushTimers();
  await running;
  assert.equal(ui.get('current-title').textContent, WindowsDemo.steps[8].title);
  assert.equal(ui.get('zip2022').textContent, '26.03');
  assert.equal(ui.get('next').disabled, false);
  ui.get('reset').fire('click');
  assert.equal(ui.rows().length, 11);
  assert.equal(ui.get('action-count').textContent, 'Getting started');
  ui.rows()[10].querySelector('.workflow-step').fire('click');
  assert.equal(ui.get('current-title').textContent, WindowsDemo.steps[10].title);
  assert.equal(ui.get('next').disabled, true);
});
