import { ANSWER_MAX_LENGTH, validAnswer } from './answer.mjs';

const root = () => document.getElementById('document');
const append = (node, children) => {
  for (const child of children.flat(Infinity)) if (child !== undefined && child !== null && child !== false) node.append(typeof child === 'string' || typeof child === 'number' ? document.createTextNode(String(child)) : child);
  return node;
};
export function element(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value === false || value === undefined || value === null) continue;
    if (key.startsWith('on')) node.addEventListener(key.slice(2).toLowerCase(), value);
    else if (key === 'className') node.className = value;
    else if (key === 'checked' || key === 'disabled') node[key] = value;
    else node.setAttribute(key, value === true ? '' : String(value));
  }
  return append(node, children);
}
const e = element;
const pretty = (value) => JSON.stringify(value, null, 2);
const code = (value, language) => e('figure', { className: 'code' }, language ? e('figcaption', {}, language) : null, e('pre', { tabindex: '0' }, e('code', {}, value)));
const list = (items) => e('ul', {}, items.map((item) => e('li', {}, item)));
const titleCase = (value) => value[0].toUpperCase() + value.slice(1);
const statusLabel = (status, kind) => ({ proposed: kind === 'recap' ? 'Proposed follow-up' : 'Proposed', context: 'Existing context', implemented: 'Implemented', inferred: 'Inferred' })[status];

async function api(path, body) {
  let response;
  try {
    response = await fetch(path, {
      credentials: 'same-origin',
      ...(body === undefined ? {} : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }),
      signal: AbortSignal.timeout(6000),
    });
  } catch (error) {
    throw new Error(`Cannot reach the local viewer. Run the viewer ensure command and reload. ${error.message}`);
  }
  const data = await response.json();
  if (!response.ok || !data.ok) {
    const failure = data.errors?.[0];
    throw new Error(`${failure?.message ?? `HTTP ${response.status}`}\n${failure?.repair ?? 'Reload the viewer and retry.'}`);
  }
  return data;
}

function markdown(node) {
  if (node.type === 'text') return document.createTextNode(node.value);
  if (node.type === 'code') return code(node.value, node.lang);
  if (node.type === 'inlineCode') return e('code', {}, node.value);
  if (node.type === 'link') return e('a', { href: node.url, rel: 'noreferrer noopener', ...(node.url.startsWith('#') ? {} : { target: '_blank' }) }, node.children.map(markdown));
  const tag = { heading: `h${Math.max(2, Math.min(6, node.depth ?? 2))}`, paragraph: 'p', list: node.ordered ? 'ol' : 'ul', listItem: 'li', blockquote: 'blockquote', thematicBreak: 'hr', break: 'br', emphasis: 'em', strong: 'strong' }[node.type];
  return e(tag, { ...(node.type === 'list' && node.ordered && node.start ? { start: node.start } : {}) }, node.children?.map(markdown) ?? []);
}

function svgNode(tag, attrs, ...children) {
  const node = document.createElementNS('http://www.w3.org/2000/svg', tag);
  for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, String(value));
  return append(node, children);
}
function diagram(data, block) {
  const sequence = data.layout === 'sequence';
  const cols = sequence ? data.nodes.length : Math.min(4, data.nodes.length);
  const nodeIndex = new Map(data.nodes.map((node, index) => [node.id, index]));
  const rowEdges = new Map();
  const nextLane = (row) => {
    const lane = rowEdges.get(row) ?? 0;
    rowEdges.set(row, lane + 1);
    return lane;
  };
  let exteriorChannels = 0;
  const lanes = data.edges.map((edge) => {
    const fromRow = Math.floor(nodeIndex.get(edge.from) / cols);
    const toRow = Math.floor(nodeIndex.get(edge.to) / cols);
    const from = nextLane(fromRow);
    return { from, to: fromRow === toRow ? from : nextLane(toRow), channel: fromRow === toRow ? null : exteriorChannels++ };
  });
  const rowGap = Math.max(145, 100 + Math.max(0, ...rowEdges.values()) * 24);
  const width = Math.max(620, cols * 190 + 30 + (sequence ? 0 : exteriorChannels * 18));
  const height = sequence ? 150 + data.edges.length * 65 : 65 + Math.ceil(data.nodes.length / cols) * rowGap;
  const markerId = `arrow-${block.id}`;
  const svg = svgNode('svg', { viewBox: `0 0 ${width} ${height}`, width, height, role: 'img', 'aria-labelledby': `diagram-title-${block.id}` },
    svgNode('title', { id: `diagram-title-${block.id}` }, block.title),
    svgNode('desc', {}, `${data.nodes.length} nodes. ${data.edges.map((edge) => `${edge.from} to ${edge.to}${edge.label ? `: ${edge.label}` : ''}`).join('. ')}`),
    svgNode('defs', {}, svgNode('marker', { id: markerId, markerWidth: 8, markerHeight: 8, refX: 7, refY: 4, orient: 'auto' }, svgNode('path', { d: 'M0,0 L8,4 L0,8 Z', class: 'arrowhead' }))),
  );
  const positions = new Map(data.nodes.map((node, index) => [node.id, { x: 30 + (index % cols) * 190, y: sequence ? 20 : 25 + Math.floor(index / cols) * rowGap }]));
  if (sequence) for (const point of positions.values()) svg.append(svgNode('line', { x1: point.x + 80, y1: 76, x2: point.x + 80, y2: height - 20, class: 'lifeline' }));
  data.edges.forEach((edge, index) => {
    const from = positions.get(edge.from);
    const to = positions.get(edge.to);
    const y = sequence ? 115 + index * 65 : from.y + 80 + lanes[index].from * 24;
    const startX = from.x + 80;
    const endX = to.x + 80;
    const exteriorX = cols * 190 + 15 + (lanes[index].channel ?? 0) * 18;
    const targetY = to.y + 80 + lanes[index].to * 24;
    let path;
    if (sequence && edge.from === edge.to) path = `M ${startX} ${y} h 45 v 25 h -45`;
    else if (sequence) path = `M ${startX} ${y} L ${endX} ${y}`;
    else if (edge.from === edge.to) path = `M ${startX} ${from.y + 56} V ${y} H ${from.x + 175} V ${from.y + 28} H ${from.x + 160}`;
    else if (from.y === to.y) path = `M ${startX} ${from.y + 56} V ${y} H ${endX} V ${to.y + 56}`;
    else path = `M ${startX} ${from.y + 56} V ${y} H ${exteriorX} V ${targetY} H ${endX} V ${to.y + 56}`;
    svg.append(svgNode('path', { d: path, class: 'edge', 'marker-end': `url(#${markerId})` }));
    if (edge.label) svg.append(svgNode('text', { x: (startX + (!sequence && from.y !== to.y ? exteriorX : endX)) / 2, y: y - 9, class: 'edge-label', 'text-anchor': 'middle' }, svgNode('title', {}, edge.label), edge.label.length > 35 ? `${edge.label.slice(0, 32)}...` : edge.label));
  });
  data.nodes.forEach((node) => {
    const { x, y } = positions.get(node.id);
    const group = svgNode('g', {}, svgNode('rect', { x, y, width: 160, height: 56, rx: 4, class: 'graph-node' }), svgNode('title', {}, node.label));
    const text = svgNode('text', { x: x + 80, y: y + 32, 'text-anchor': 'middle', class: 'node-label' }, node.label.length > 22 ? `${node.label.slice(0, 19)}...` : node.label);
    group.append(text);
    svg.append(group);
  });
  const viewport = e('div', { className: 'diagram-scroll', 'data-view': 'fit', tabindex: '0', 'aria-label': `${block.title}. Switch to actual size to scroll and inspect labels.` }, svg);
  const fit = e('button', { type: 'button', 'aria-pressed': 'true', onclick: () => setView('fit') }, 'Fit width');
  const actual = e('button', { type: 'button', 'aria-pressed': 'false', onclick: () => setView('actual') }, 'Actual size');
  function setView(view) {
    viewport.setAttribute('data-view', view);
    fit.setAttribute('aria-pressed', String(view === 'fit'));
    actual.setAttribute('aria-pressed', String(view === 'actual'));
  }
  return e('div', { className: 'diagram' },
    e('div', { className: 'diagram-toolbar' },
      e('p', { className: 'diagram-summary' }, `${data.nodes.length} nodes · ${data.edges.length} connections`),
      e('div', { className: 'diagram-actions', role: 'group', 'aria-label': `${block.title} diagram view` }, fit, actual),
    ),
    viewport,
    e('p', { className: 'diagram-hint' }, 'Fit width shows the whole diagram. Use actual size to inspect labels and scroll.'),
  );
}

function annotatedCode(data) {
  const notes = new Map();
  for (const note of data.annotations) notes.set(note.line, [...(notes.get(note.line) ?? []), note.text]);
  return e('figure', { className: 'annotated-code' }, e('figcaption', {}, data.language), e('ol', { className: 'code-lines' },
    data.code.split('\n').map((line, index) => e('li', {}, e('code', {}, line || ' '), (notes.get(index + 1) ?? []).map((note) => e('span', { className: 'line-note' }, note)))),
  ));
}
function wireframe(regions) {
  return e('div', { className: 'wireframe', 'aria-label': 'Interface wireframe' }, regions.map((region) => e('section', { className: `region region-${region.kind ?? 'content'}` }, e('h4', {}, region.label), region.content ? e('p', {}, region.content) : e('p', { className: 'muted' }, 'No content specified.'))));
}
function stateSequence(data) {
  let index = 0;
  const content = e('div', { className: 'state-content', 'aria-live': 'polite' });
  const progress = e('span', { className: 'state-progress', role: 'status' });
  const previous = e('button', { type: 'button', className: 'secondary-button', onclick: () => { index--; update(); } }, 'Previous state');
  const next = e('button', { type: 'button', className: 'secondary-button', onclick: () => { index++; update(); } }, 'Next state');
  function update() {
    const state = data.states[index];
    previous.disabled = index === 0;
    next.disabled = index === data.states.length - 1;
    progress.textContent = `State ${index + 1} of ${data.states.length}`;
    content.replaceChildren(e('h3', {}, state.name), e('p', {}, state.description), ...(state.regions ? [wireframe(state.regions)] : []));
  }
  update();
  return e('div', { className: 'state-sequence' }, e('div', { className: 'state-controls' }, previous, progress, next), content);
}

function jsonTree(value, label, depth = 0) {
  if (value === null || typeof value !== 'object') return e('div', { className: 'schema-leaf' }, e('span', {}, `${label} `), e('code', {}, pretty(value)));
  const entries = Object.entries(value);
  return e('details', { className: 'schema-node', ...(depth === 0 ? { open: true } : {}) },
    e('summary', {}, label, e('span', { className: 'schema-type' }, Array.isArray(value) ? ` array, ${entries.length} ${entries.length === 1 ? 'item' : 'items'}` : typeof value.type === 'string' ? ` ${value.type}` : ` ${entries.length} ${entries.length === 1 ? 'field' : 'fields'}`)),
    e('div', { className: 'schema-children' }, entries.length ? entries.map(([key, child]) => jsonTree(child, key, depth + 1)) : e('p', { className: 'muted' }, 'No schema fields specified.')),
  );
}
function apiContract(data) {
  const endpoint = data.protocol === 'http' ? `${data.method} ${data.path}` : data.signature;
  const params = data.parameters.length ? e('div', { className: 'table-scroll', tabindex: '0', 'aria-label': 'Parameters table' },
    e('table', { className: 'responsive-table parameter-table', role: 'table' }, e('caption', {}, 'Parameters'), e('thead', { role: 'rowgroup' }, e('tr', { role: 'row' }, ['Name', 'Location', 'Type', 'Required', 'Description'].map((label) => e('th', { scope: 'col', role: 'columnheader' }, label)))),
      e('tbody', { role: 'rowgroup' }, data.parameters.map((param) => e('tr', { role: 'row' }, e('th', { scope: 'row', role: 'rowheader' }, e('code', {}, param.name)), e('td', { 'data-label': 'Location', role: 'cell' }, param.in), e('td', { 'data-label': 'Type', role: 'cell' }, e('code', {}, param.type)), e('td', { 'data-label': 'Required', role: 'cell' }, param.required ? 'Required' : 'Optional'), e('td', { 'data-label': 'Description', role: 'cell' }, param.description)))),
    ),
  ) : e('p', { className: 'muted' }, 'No parameters.');
  return e('div', { className: 'api-contract' },
    e('p', { className: 'contract-protocol' }, ({ http: 'HTTP', rpc: 'RPC', cli: 'CLI', function: 'Function', event: 'Event' })[data.protocol], data.protocol === 'http' ? ' contract' : ` contract · ${data.name}`),
    e('pre', { className: 'endpoint', tabindex: '0' }, e('code', {}, endpoint)),
    e('p', { className: 'auth' }, e('strong', {}, 'Authentication. '), data.auth),
    params,
    jsonTree(data.schema, 'Schema'),
    e('h4', {}, 'Examples'),
    data.examples.map((example) => e('details', { className: 'example' }, e('summary', {}, `${titleCase(example.kind)}${example.status ? ` · ${example.status}` : ''}`), code(pretty(example.body), 'json'))),
  );
}

function question(data, block, context) {
  const inputId = `answer-${block.id}`;
  const saved = e('div', { className: 'answer-history' });
  const feedback = e('p', { className: 'answer-feedback', role: 'status', 'aria-live': 'polite' });
  const answer = context.answers.find((item) => item.blockId === block.id);
  const selected = answer?.active ? answer.value : '';
  const field = data.options
    ? e('fieldset', {}, e('legend', {}, data.prompt), data.options.map((option, index) => e('label', { className: 'option', for: `${inputId}-${index}` }, e('input', { type: 'radio', id: `${inputId}-${index}`, name: inputId, value: option, checked: selected === option, required: true }), e('span', {}, option))))
    : e('div', {}, e('label', { for: inputId, className: 'question-prompt' }, data.prompt), e('textarea', { id: inputId, name: inputId, rows: '4', maxlength: ANSWER_MAX_LENGTH, required: true }, selected));
  const button = e('button', { type: 'submit' }, 'Save answer');
  function showSaved(value) {
    saved.replaceChildren();
    if (value) saved.append(e('div', { className: `saved-answer${value.stale ? ' stale' : ''}` }, e('strong', {}, value.stale ? 'Stale answer. The question changed.' : 'Saved answer'), e('p', {}, value.value), e('small', {}, value.stale ? 'This answer is retained for reference. It is not an active answer to the current question.' : `Saved ${new Date(value.savedAt).toLocaleString()} on this device.`)));
  }
  showSaved(answer);
  const form = e('form', { onsubmit: async (event) => {
    event.preventDefault();
    const choice = data.options ? form.querySelector('input:checked')?.value : form.querySelector('textarea').value;
    if (!validAnswer(choice)) { feedback.textContent = `Enter a nonblank answer of up to ${ANSWER_MAX_LENGTH} characters or choose an option before saving.`; feedback.className = 'answer-feedback error'; return; }
    button.disabled = true;
    button.textContent = 'Saving...';
    feedback.className = 'answer-feedback';
    feedback.textContent = 'Saving on this device...';
    try {
      const result = await context.save(block.id, { value: choice, digest: block.questionDigest });
      context.answers = result.answers;
      showSaved(result.answers.find((item) => item.blockId === block.id));
      feedback.textContent = 'Answer saved on this device.';
    } catch (error) {
      feedback.textContent = error.message;
      feedback.className = 'answer-feedback error';
    } finally {
      button.disabled = false;
      button.textContent = 'Save answer';
    }
  } }, field, e('div', { className: 'answer-actions' }, button, e('small', {}, 'Local feedback only. No application requests are sent.')), feedback);
  return e('div', { className: 'question' }, saved, form);
}

const renderers = {
  Diagram: diagram,
  AnnotatedCode: annotatedCode,
  FileMap: (data) => e('div', { className: 'table-scroll', tabindex: '0', 'aria-label': 'Changed files' }, e('table', { className: 'responsive-table file-map-table', role: 'table' }, e('caption', { className: 'visually-hidden' }, 'Files and changes'), e('thead', { role: 'rowgroup' }, e('tr', { role: 'row' }, ['File', 'Change', 'Note'].map((label) => e('th', { scope: 'col', role: 'columnheader' }, label)))), e('tbody', { role: 'rowgroup' }, data.files.map((file) => e('tr', { role: 'row' }, e('th', { scope: 'row', role: 'rowheader' }, e('code', {}, file.path)), e('td', { 'data-label': 'Change', role: 'cell' }, file.change), e('td', { 'data-label': 'Note', role: 'cell' }, file.note)))))),
  BeforeAfter: (data) => e('div', { className: 'comparison' }, ['before', 'after'].map((side) => e('section', {}, e('h3', {}, data[side].label), code(data[side].code, data[side].language)))),
  Decision: (data) => e('ul', { className: 'decisions' }, data.options.map((option) => e('li', {}, e('p', {}, e('strong', {}, option.label), e('span', { className: `selection${option.selected ? ' selected' : ''}` }, option.selected ? 'Selected' : 'Not selected')), e('p', {}, option.reason)))),
  Question: question,
  Wireframe: (data) => wireframe(data.regions),
  StateSequence: stateSequence,
  ApiContract: apiContract,
  ApiComparison: (data) => e('div', {}, e('div', { className: 'comparison api-comparison' }, e('section', {}, e('h3', {}, 'Before'), apiContract(data.before)), e('section', {}, e('h3', {}, 'After'), apiContract(data.after))), e('h3', {}, 'Contract changes'), list(data.changes)),
};

export function renderDocument(doc, context) {
  const outline = e('ul', { className: 'outline-list' });
  const body = e('article', {},
    e('div', { className: 'document-heading' }, e('h1', {}, doc.title), e('p', { className: 'document-meta' }, e('span', { className: 'kind' }, titleCase(doc.kind)), ' · Published snapshot')),
    e('p', { className: 'snapshot-note' }, 'Reopen the MDX source after editing to publish changes. ', e('button', { type: 'button', className: 'text-button', onclick: () => location.reload() }, 'Reload published version')),
    doc.sourcePath ? e('details', { className: 'source-info' }, e('summary', {}, 'Source and revision'), e('p', {}, doc.sourcePath), e('p', {}, `Revision ${doc.revision}`), e('p', {}, `Published ${new Date(doc.publishedAt).toLocaleString()}`)) : null,
  );
  let heading = 0;
  for (const block of doc.blocks) {
    if (block.type !== 'component') {
      const node = markdown(block);
      if (block.type === 'heading') {
        node.id = `heading-${heading++}`;
        outline.append(e('li', { className: 'outline-heading' }, e('a', { href: `#${node.id}` }, node.textContent)));
      }
      body.append(node);
      continue;
    }
    const id = `block-${block.id}`;
    outline.append(e('li', {}, e('a', { href: `#${id}` }, block.title)));
    const section = e('section', { id, className: `rich-block component-${block.name}`, 'aria-labelledby': `${id}-title` },
      e('header', { className: 'block-heading' }, e('h2', { id: `${id}-title` }, block.title), e('span', { className: `status status-${block.status}` }, statusLabel(block.status, doc.kind))),
      block.reason ? e('p', { className: 'inference' }, e('strong', {}, 'Inference. '), block.reason) : null,
      renderers[block.name](block.data, block, context),
    );
    const evidence = [...(block.evidence ? [block.evidence] : []), ...(block.data.evidence ?? [])];
    if (evidence.length) section.append(e('details', { className: 'evidence' }, e('summary', {}, 'Evidence'), list(evidence)));
    body.append(section);
  }
  const removed = context.answers.filter((answer) => answer.removed);
  if (removed.length) body.append(e('section', { className: 'removed-answers' }, e('h2', {}, 'Answers to removed questions'), e('p', {}, 'Retained for reference only. These answers are stale and inactive.'), list(removed.map((answer) => `${answer.blockId}: ${answer.value}`))));
  root().replaceChildren(body);
  const expanded = typeof matchMedia !== 'function' || matchMedia('(min-width: 701px)').matches;
  document.getElementById('outline').replaceChildren(e('details', { open: expanded }, e('summary', {}, 'On this page'), outline));
  document.title = `${doc.title} · nstack`;
}

export async function start() {
  root().setAttribute('aria-busy', 'true');
  try {
    await api('/api/session');
    const id = /^\/documents\/([a-zA-Z0-9][a-zA-Z0-9_-]{0,95})$/.exec(location.pathname)?.[1];
    if (!id) {
      const result = await api('/api/documents');
      root().replaceChildren(e('h1', {}, 'Visual review'), e('p', {}, 'Published documents stay on this device. Open a document to read its current snapshot and save feedback.'), result.documents.length ? e('ul', { className: 'document-list' }, result.documents.map((doc) => e('li', {}, e('a', { href: `/documents/${doc.docId}` }, doc.title), e('span', {}, titleCase(doc.kind))))) : e('p', { className: 'empty' }, 'No documents yet. Run the viewer open command with an absolute MDX source path.'));
      document.getElementById('outline').replaceChildren();
    } else {
      const [doc, answers] = await Promise.all([api(`/api/documents/${id}`), api(`/api/answers/${id}`)]);
      renderDocument(doc, { answers: answers.answers, save: (blockId, body) => api(`/api/answers/${id}/${blockId}`, body) });
    }
    document.getElementById('connection').textContent = 'Local viewer';
  } catch (error) {
    document.getElementById('connection').textContent = 'Unavailable';
    root().replaceChildren(e('h1', {}, 'Unable to load the viewer'), e('p', { className: 'error', role: 'alert' }, error.message), e('button', { type: 'button', onclick: () => location.reload() }, 'Retry loading'));
  } finally {
    root().setAttribute('aria-busy', 'false');
  }
}

if (typeof document !== 'undefined' && !globalThis.__NSTACK_TEST__) start();
