import test from 'node:test';
import assert from 'node:assert/strict';
import { pathToFileURL } from 'node:url';
import { join } from 'node:path';
const { compile } = await import(process.env.NSTACK_VIEWER_OUTPUT_DIR ? pathToFileURL(join(process.env.NSTACK_VIEWER_OUTPUT_DIR, 'viewer.mjs')) : '../src/plugins/nstack/hooks/viewer/viewer.mjs');

const wrap = (body, kind = 'plan') => `<Document id="test" title="Test" kind="${kind}">\n\n${body}\n\n</Document>\n`;
const rich = (name, data, extra = '') => `<${name} id="block" title="Block" status="proposed" ${extra}>\n\n\`\`\`json\n${JSON.stringify(data)}\n\`\`\`\n\n</${name}>`;

test('parses Markdown and structured graph through the MDX AST', () => {
  const doc = compile(wrap(`## A heading\n\nA **strong** idea.\n\n${rich('Diagram', { nodes: [{ id: 'a', label: 'Client' }], edges: [] })}`));
  assert.equal(doc.docId, 'test');
  assert.equal(doc.blocks[0].children[0].value, 'A heading');
  assert.equal(doc.blocks[2].data.nodes[0].label, 'Client');
  assert.match(doc.revision, /^[a-f0-9]{64}$/);
});

test('rejects expressions, ESM, HTML, arbitrary attributes, unsafe links and unknown tags', () => {
  const bad = ['{globalThis.process.exit()}', '<script>no</script>', '<img src="https://example.com/a" />', '<Unknown />', '[bad](javascript:alert%281%29)', '<Question {...props} />', rich('Question', { prompt: 'test' }, 'onClick="alert()"')];
  for (const source of bad) assert.throws(() => compile(wrap(source)), (error) => Boolean(error.code && error.repair && error.line), source);
  assert.throws(() => compile(`import x from "node:fs"\n\n${wrap('Hello')}`), { code: 'document_required' });
  assert.throws(() => compile(wrap('<Question id={process.exit()} title="x" status="proposed" />')), { code: 'unsafe_attribute' });
});

test('validates payloads, evidence, uniqueness and graph endpoints', () => {
  assert.throws(() => compile(wrap(rich('Question', { prompt: 2 }))), { code: 'invalid_payload' });
  assert.throws(() => compile(wrap(rich('Diagram', { nodes: [{ id: 'a', label: 'A' }], edges: [{ from: 'a', to: 'missing' }] }))), { code: 'invalid_graph' });
  assert.throws(() => compile(wrap(`${rich('Question', { prompt: 'First' })}\n\n${rich('Question', { prompt: 'Second' })}`)), { code: 'duplicate_id' });
  assert.throws(() => compile(wrap(rich('Question', { prompt: 'Done?' }).replace('proposed', 'implemented'), 'recap')), { code: 'evidence_required' });
  assert.throws(() => compile(wrap(rich('Question', { prompt: 'Likely?' }).replace('proposed', 'inferred'), 'recap')), { code: 'reason_required' });
});

test('Question options obey the same nonblank 10000-character limit as saved answers', () => {
  for (const option of [' \n\t', 'x'.repeat(10001), '😀'.repeat(5001)]) {
    assert.throws(() => compile(wrap(rich('Question', { prompt: 'Choose?', options: ['Other', option] }))), (error) => {
      assert.equal(error.code, 'invalid_payload');
      assert.equal(typeof error.line, 'number');
      assert.match(error.repair, /Question/);
      return true;
    });
  }
  const doc = compile(wrap(rich('Question', { prompt: 'Choose?', options: ['x', 'y'.repeat(10000)] })));
  assert.equal(doc.blocks[0].data.options[1], 'y'.repeat(10000));
});
