import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { readFileSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
const require = createRequire(new URL('../tools/visual-viewer/package.json', import.meta.url));
const { parseHTML } = require('linkedom');
const viewer = fileURLToPath(new URL('../src/plugins/nstack/hooks/viewer/viewer.mjs', import.meta.url));
const example = fileURLToPath(new URL('../src/plugins/nstack/hooks/viewer/all-components.mdx', import.meta.url));
const doc = JSON.parse(execFileSync(process.execPath, [viewer, 'check', example], { encoding: 'utf8' })).document;
globalThis.__NSTACK_TEST__ = true;
const bundle = readFileSync(new URL('../src/plugins/nstack/hooks/viewer/assets/browser.js', import.meta.url));
const { renderDocument } = await import(`data:text/javascript;base64,${bundle.toString('base64')}`);

function setup(answers = [], save = async () => ({ answers: [] })) {
  const { document } = parseHTML('<html><head></head><body><nav id="outline"></nav><main id="document"></main></body></html>');
  globalThis.document = document;
  renderDocument(doc, { answers, save });
  return document;
}

test('renders all ten components using text nodes and native controls', () => {
  const dom = setup();
  for (const name of new Set(doc.blocks.filter((block) => block.type === 'component').map((block) => block.name))) {
    assert.ok(dom.querySelector(`.component-${name}`), name);
  }
  assert.equal(dom.querySelector('h1').textContent, 'Token refresh review');
  assert.equal(dom.querySelector('.diagram-scroll svg').getAttribute('role'), 'img');
  assert.match(dom.querySelector('.code-lines').textContent, /Reject an expired/);
  assert.equal(dom.querySelectorAll('.api-comparison .api-contract').length, 2);
  assert.match(dom.querySelector('.component-ApiContract').textContent, /Authentication/);
  assert.ok(dom.querySelector('.schema-children details summary'));
  assert.ok(dom.querySelector('.example summary'));
  assert.equal(dom.querySelectorAll('button').some((node) => /send|execute request/i.test(node.textContent)), false);
  assert.equal(dom.querySelectorAll('script, iframe, img').length, 0);
  assert.ok(dom.querySelector('#outline a[href="#block-refresh-http"]'));
  assert.equal(dom.querySelectorAll('.line-note').length, 2);
});

test('state previous/next controls change the actual visible content and endpoints', () => {
  const dom = setup();
  const state = dom.querySelector('.state-sequence');
  const [previous, next] = state.querySelectorAll('button');
  assert.equal(previous.disabled, true);
  assert.match(state.querySelector('.state-content').textContent, /The session is valid/);
  next.click();
  assert.equal(previous.disabled, false);
  assert.match(state.querySelector('.state-content').textContent, /Duplicate requests wait/);
  assert.equal(state.querySelector('.state-progress').textContent, 'State 2 of 3');
  next.click();
  assert.equal(next.disabled, true);
  assert.match(state.querySelector('.state-content').textContent, /Sign in again/);
  previous.click();
  assert.equal(next.disabled, false);
  assert.match(state.querySelector('.state-content').textContent, /Refreshing session/);
});

test('stale feedback is visible without silently selecting it and text answers save by block and digest', async () => {
  const calls = [];
  const dom = setup([{ blockId: 'token-ttl', value: '1 hour', stale: true, active: false, savedAt: '2026-01-01T00:00:00Z' }], async (blockId, body) => {
    calls.push({ blockId, body });
    return { answers: [{ blockId, value: body.value, digest: body.digest, stale: false, active: true, savedAt: '2026-01-01T00:00:00Z' }] };
  });
  assert.match(dom.querySelector('.saved-answer.stale').textContent, /not an active answer/);
  assert.ok([...dom.querySelectorAll('.component-Question input')].every((input) => !input.checked));
  const notes = dom.querySelector('#block-review-notes');
  notes.querySelector('textarea').value = '<script>alert("not executable")</script>';
  notes.querySelector('form').dispatchEvent(new dom.defaultView.Event('submit', { cancelable: true }));
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(calls[0].blockId, 'review-notes');
  assert.equal(calls[0].body.digest, doc.blocks.find((block) => block.id === 'review-notes').questionDigest);
  assert.equal(calls[0].body.value, '<script>alert("not executable")</script>');
  assert.match(notes.querySelector('.saved-answer').textContent, /<script>/);
  assert.equal(notes.querySelector('script'), null);
  assert.match(notes.querySelector('[role="status"]').textContent, /Answer saved/);
});

test('failed feedback displays the actionable error and restores the save control', async () => {
  const dom = setup([], async () => { throw new Error('Question changed. Reload the page and answer the current question.'); });
  const notes = dom.querySelector('#block-review-notes');
  notes.querySelector('textarea').value = 'Retry later';
  notes.querySelector('form').dispatchEvent(new dom.defaultView.Event('submit', { cancelable: true }));
  await new Promise((resolve) => setImmediate(resolve));
  assert.match(notes.querySelector('.answer-feedback.error').textContent, /Reload the page/);
  assert.equal(notes.querySelector('button').disabled, false);
});
