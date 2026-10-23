import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
const require = createRequire(new URL('../tools/visual-viewer/package.json', import.meta.url));
const { parseHTML } = require('linkedom');
const viewerRoot = process.env.NSTACK_VIEWER_OUTPUT_DIR ?? fileURLToPath(new URL('../src/plugins/nstack/hooks/viewer', import.meta.url));
const viewer = join(viewerRoot, 'viewer.mjs');
const example = fileURLToPath(new URL('../src/plugins/nstack/hooks/viewer/all-components.mdx', import.meta.url));
const doc = JSON.parse(execFileSync(process.execPath, [viewer, 'check', example], { encoding: 'utf8' })).document;
globalThis.__NSTACK_TEST__ = true;
const bundle = readFileSync(join(viewerRoot, 'assets/browser.js'));
const { renderDocument, start } = await import(`data:text/javascript;base64,${bundle.toString('base64')}`);

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

test('schema properties named type render as fields rather than object type labels', () => {
  const fixture = structuredClone(doc);
  const contract = fixture.blocks.find((block) => block.name === 'ApiContract');
  contract.data.schema = { type: 'object', properties: { type: { type: 'string' }, count: { type: 'integer' } } };
  const dom = setup();
  renderDocument(fixture, { answers: [] });
  const schema = dom.querySelector('.component-ApiContract .schema-node');
  assert.equal(schema.querySelector('summary').textContent, 'Schema object');
  assert.match(schema.textContent, /properties 2 fields/);
  assert.match(schema.textContent, /type string/);
  assert.equal(schema.textContent.includes('[object Object]'), false);
});

test('flow edges avoid all node interiors across rows, back edges, skips and self loops', () => {
  const fixture = structuredClone(doc);
  const graph = fixture.blocks.find((block) => block.name === 'Diagram');
  graph.data = {
    layout: 'flow',
    nodes: Array.from({ length: 10 }, (_, index) => ({ id: String(index), label: `Node ${index}` })),
    edges: [{ from: '0', to: '9' }, { from: '9', to: '0' }, { from: '1', to: '3' }, { from: '4', to: '4' }, { from: '2', to: '5' }],
  };
  const dom = setup();
  renderDocument(fixture, { answers: [] });
  const svg = dom.querySelector('.component-Diagram svg');
  const boxes = [...svg.querySelectorAll('.graph-node')].map((node) => Object.fromEntries(['x', 'y', 'width', 'height'].map((key) => [key, Number(node.getAttribute(key))])));
  const paths = [...svg.querySelectorAll('.edge')];
  assert.equal(paths.length, 5);
  paths.forEach((path, index) => {
    const tokens = path.getAttribute('d').match(/[MLHVhv]|-?\d+(?:\.\d+)?/g);
    let x = 0, y = 0;
    const points = [];
    while (tokens.length) {
      const command = tokens.shift();
      if (command === 'M' || command === 'L') { x = Number(tokens.shift()); y = Number(tokens.shift()); }
      else if (command === 'H') x = Number(tokens.shift());
      else if (command === 'V') y = Number(tokens.shift());
      else if (command === 'h') x += Number(tokens.shift());
      else if (command === 'v') y += Number(tokens.shift());
      else assert.fail(`Unexpected path command ${command}`);
      points.push([x, y]);
    }
    const edge = graph.data.edges[index];
    for (const [point, id] of [[points[0], edge.from], [points.at(-1), edge.to]]) {
      const box = boxes[Number(id)];
      assert.equal(point[0] >= box.x && point[0] <= box.x + box.width && point[1] >= box.y && point[1] <= box.y + box.height, true, `${id} endpoint`);
    }
    for (let i = 1; i < points.length; i++) {
      const [ax, ay] = points[i - 1], [bx, by] = points[i];
      assert.equal(ax === bx || ay === by, true);
      for (const box of boxes) {
        const intersects = ax === bx
          ? ax > box.x && ax < box.x + box.width && Math.max(ay, by) > box.y && Math.min(ay, by) < box.y + box.height
          : ay > box.y && ay < box.y + box.height && Math.max(ax, bx) > box.x && Math.min(ax, bx) < box.x + box.width;
        assert.equal(intersects, false, `Edge ${edge.from} to ${edge.to} intersects ${JSON.stringify(box)}`);
      }
    }
    assert.match(path.getAttribute('marker-end'), /^url\(#arrow-/);
  });

});

test('browser reads and feedback use the same-origin cookie without requesting a token', async () => {
  const dom = setup();
  const connection = dom.createElement('span');
  connection.id = 'connection';
  dom.body.append(connection);
  const originalFetch = globalThis.fetch;
  const originalLocation = globalThis.location;
  const calls = [];
  globalThis.location = { pathname: '/documents/nstack-components-reference' };
  globalThis.fetch = async (path, options) => {
    calls.push({ path, options });
    let data;
    if (path === '/api/session') data = { ok: true, buildId: 'test' };
    else if (path.startsWith('/api/documents/')) data = { ok: true, ...doc };
    else if (options.method === 'POST') {
      const body = JSON.parse(options.body);
      data = { ok: true, answers: [{ blockId: 'review-notes', value: body.value, digest: body.digest, active: true, stale: false, savedAt: '2026-01-01T00:00:00Z' }] };
    } else data = { ok: true, answers: [] };
    return { ok: true, json: async () => data };
  };
  try {
    await start();
    assert.equal(connection.textContent, 'Local viewer');
    const notes = dom.querySelector('#block-review-notes');
    notes.querySelector('textarea').value = 'Cookie-authenticated feedback';
    notes.querySelector('form').dispatchEvent(new dom.defaultView.Event('submit', { cancelable: true }));
    await new Promise((resolve) => setImmediate(resolve));
    assert.deepEqual(calls.map((call) => call.path), [
      '/api/session', '/api/documents/nstack-components-reference', '/api/answers/nstack-components-reference', '/api/answers/nstack-components-reference/review-notes',
    ]);
    for (const { options } of calls) {
      assert.equal(options.credentials, 'same-origin');
      assert.equal(options.headers?.['X-Nstack-Token'], undefined);
    }
    assert.deepEqual(calls[3].options.headers, { 'Content-Type': 'application/json' });
    assert.match(notes.querySelector('.saved-answer').textContent, /Cookie-authenticated feedback/);
  } finally {
    globalThis.fetch = originalFetch;
    globalThis.location = originalLocation;
  }
});
