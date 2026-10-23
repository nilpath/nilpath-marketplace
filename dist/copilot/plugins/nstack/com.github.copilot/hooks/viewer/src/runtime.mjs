import { createServer } from 'node:http';
import { spawn } from 'node:child_process';
import { randomBytes } from 'node:crypto';
import { mkdirSync, readFileSync, writeFileSync, renameSync, rmSync, rmdirSync, statSync, existsSync, linkSync, unlinkSync, readdirSync } from 'node:fs';
import { join, dirname, isAbsolute, resolve } from 'node:path';
import { homedir } from 'node:os';
import { fileURLToPath } from 'node:url';
import { compile } from './compiler.mjs';
import { ViewerError, ID, digest, boundedJSON } from './model.mjs';

const PROTOCOL = 1;
const START_MS = 6000;
const MAX_BODY = 2_100_000;
const random = () => randomBytes(24).toString('hex');
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
export const stateRoot = () => join(resolve(process.env.NSTACK_HOME || join(homedir(), '.nstack')), 'viewer');
const claimPath = (root) => join(root, 'runtime');
const readJSON = (file) => {
  try { return JSON.parse(readFileSync(file, 'utf8')); }
  catch (error) {
    if (error.code === 'ENOENT') return null;
    if (error instanceof SyntaxError) throw new ViewerError('corrupt_state', `Invalid JSON in ${file}.`, 'Move the corrupt state file aside, then retry. Preserve documents and answers you need.');
    throw error;
  }
};
const atomicJSON = (file, data) => {
  const tmp = `${file}.${process.pid}.${random()}.tmp`;
  writeFileSync(tmp, `${JSON.stringify(data)}\n`, { mode: 0o600, flag: 'wx' });
  renameSync(tmp, file);
};
function privateDir(path) {
  mkdirSync(path, { recursive: true, mode: 0o700 });
  const stat = statSync(path);
  if ((stat.mode & 0o077) !== 0 || (process.getuid && stat.uid !== process.getuid())) {
    throw new ViewerError('unsafe_state_permissions', `Viewer state directory ${path} must be owned by you and user-only.`, `Set its permissions to 0700 and ensure it belongs to your user.`);
  }
}
function alive(pid) {
  if (!Number.isInteger(pid) || pid <= 0) throw new ViewerError('invalid_owner', 'The runtime claim has an invalid process ID.', 'Inspect the viewer runtime claim before removing only the stale runtime directory.');
  try { process.kill(pid, 0); return true; }
  catch (error) { if (error.code === 'ESRCH') return false; if (error.code === 'EPERM') return true; throw error; }
}
function owner(root) {
  const value = readJSON(join(claimPath(root), 'owner.json'));
  if (value && (!Number.isInteger(value.pid) || value.pid <= 0 || !/^[a-f0-9]{48}$/.test(value.nonce ?? ''))) {
    throw new ViewerError('invalid_owner', 'The runtime claim has an invalid owner identity.', 'Inspect the viewer runtime claim before removing only a verified stale runtime directory.');
  }
  return value;
}
const record = (root) => readJSON(join(claimPath(root), 'ready.json'));
const owns = (root, nonce) => owner(root)?.nonce === nonce;
function release(root, nonce) {
  if (owns(root, nonce)) rmSync(claimPath(root), { recursive: true });
}
function reap(root, expected) {
  let tmp;
  try {
    const generations = readdirSync(claimPath(root)).map((file) => /^reaper-(\d+)\.json$/.exec(file)?.[1]).filter(Boolean).map(Number);
    const generation = generations.length ? Math.max(...generations) : -1;
    if (generation >= 0) {
      const reaper = readJSON(join(claimPath(root), `reaper-${generation}.json`));
      if (!reaper || alive(reaper.pid)) return;
    }
    tmp = join(claimPath(root), `reaper-${random()}.tmp`);
    writeFileSync(tmp, JSON.stringify({ pid: process.pid }), { flag: 'wx', mode: 0o600 });
    linkSync(tmp, join(claimPath(root), `reaper-${generation + 1}.json`));
    if (owns(root, expected.nonce) && !alive(owner(root).pid)) {
      const retired = join(root, `retired-${expected.nonce}-${random()}`);
      renameSync(claimPath(root), retired);
      rmSync(retired, { recursive: true });
    }
  } catch (error) {
    if (!['ENOENT', 'EEXIST'].includes(error.code)) throw error;
  } finally {
    if (tmp) {
      try { unlinkSync(tmp); } catch (error) { if (error.code !== 'ENOENT') throw error; }
    }
  }
}
function checkedRecord(value, root) {
  if (!value || value.protocol !== PROTOCOL || !Number.isInteger(value.port) || value.port < 1 || value.port > 65535 || !/^[a-f0-9]{48}$/.test(value.nonce ?? '') || !/^[a-f0-9]{48}$/.test(value.token ?? '') || value.rootHash !== digest(root) || !Number.isInteger(value.pid)) {
    throw new ViewerError('invalid_runtime', 'The viewer readiness record is invalid.', 'Inspect the viewer runtime state. Remove only a verified dead runtime claim, then retry ensure.');
  }
  return value;
}
async function probe(value, root) {
  checkedRecord(value, root);
  try {
    const response = await fetch(`http://127.0.0.1:${value.port}/health?nonce=${value.nonce}`, { signal: AbortSignal.timeout(350), redirect: 'error' });
    if (!response.ok) return false;
    const health = await response.json();
    return health.protocol === PROTOCOL && health.nonce === value.nonce && health.pid === value.pid && health.buildId === value.buildId && health.rootHash === digest(root);
  } catch (error) {
    if (error.name === 'TimeoutError' || error instanceof TypeError || error instanceof SyntaxError) return false;
    throw error;
  }
}
function readyResult(value) {
  return { ok: true, url: `http://127.0.0.1:${value.port}`, pid: value.pid, buildId: value.buildId, protocol: PROTOCOL };
}

export async function ensure(buildId, entry) {
  const root = stateRoot();
  privateDir(root);
  privateDir(join(root, 'documents'));
  privateDir(join(root, 'answers'));
  const deadline = Date.now() + START_MS;
  let mine;
  while (Date.now() < deadline) {
    try {
      mkdirSync(claimPath(root), { mode: 0o700 });
      mine = random();
      atomicJSON(join(claimPath(root), 'owner.json'), { nonce: mine, pid: process.pid, createdAt: Date.now(), buildId });
      const child = spawn(process.execPath, [entry, '_serve', mine], { detached: true, stdio: 'ignore', env: process.env });
      if (child.pid) atomicJSON(join(claimPath(root), 'owner.json'), { nonce: mine, pid: child.pid, createdAt: Date.now(), buildId });
      child.on('error', (error) => {
        if (owns(root, mine)) atomicJSON(join(claimPath(root), 'failure.json'), { code: 'spawn_failed', message: error.message, repair: 'Check the Node executable and retry ensure.' });
      });
      child.unref();
    } catch (error) {
      if (error.code !== 'EEXIST') throw error;
    }
    const currentOwner = owner(root);
    const current = record(root);
    const failure = readJSON(join(claimPath(root), 'failure.json'));
    if (failure && currentOwner?.nonce === mine) {
      release(root, mine);
      throw new ViewerError(failure.code, failure.message, failure.repair);
    }
    if (current && currentOwner?.nonce === current.nonce && await probe(current, root)) {
      if (current.buildId !== buildId) throw new ViewerError('build_mismatch', 'A viewer from another build is running.', 'Run stop using the installed viewer, then run ensure with the new build. Documents and answers are retained.');
      return readyResult(current);
    }
    if (currentOwner && !alive(currentOwner.pid)) {
      reap(root, currentOwner);
      await sleep(20);
      continue;
    }
    if (!currentOwner && existsSync(claimPath(root)) && Date.now() - statSync(claimPath(root)).mtimeMs > 2000) {
      try { rmdirSync(claimPath(root)); } catch (error) { if (!['ENOENT', 'ENOTEMPTY', 'EEXIST'].includes(error.code)) throw error; }
      continue;
    }
    await sleep(70);
  }
  throw new ViewerError('startup_timeout', 'The runtime claim did not prove viewer readiness within six seconds.', 'Retry ensure. If it remains unresponsive, inspect the recorded owner. Do not kill an unrelated process or remove a live owner claim.');
}

async function request(value, route, body) {
  const response = await fetch(`http://127.0.0.1:${value.port}${route}`, {
    method: body === undefined ? 'GET' : 'POST',
    headers: body === undefined ? {} : { Origin: `http://127.0.0.1:${value.port}`, 'Content-Type': 'application/json', 'X-Nstack-Token': value.token },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    signal: AbortSignal.timeout(2000), redirect: 'error',
  });
  const result = await response.json();
  if (!response.ok || !result.ok) {
    const error = result.errors?.[0];
    throw new ViewerError(error?.code ?? 'http_failure', error?.message ?? `Viewer HTTP ${response.status}.`, error?.repair ?? 'Run ensure, then retry.');
  }
  return result;
}
export async function publish(buildId, entry, sourcePath, source) {
  const document = compile(source);
  await ensure(buildId, entry);
  const result = await request(checkedRecord(record(stateRoot()), stateRoot()), '/api/publish', { sourcePath, source });
  return { ok: true, docId: document.docId, title: document.title, url: `${result.url}/documents/${document.docId}`, revision: document.revision };
}
export async function getAnswers(buildId, entry, id) {
  if (!ID.test(id ?? '')) throw new ViewerError('invalid_id', 'A valid document ID is required.', 'Use the document ID returned by open.');
  await ensure(buildId, entry);
  return request(checkedRecord(record(stateRoot()), stateRoot()), `/api/answers/${id}`);
}
export async function stop() {
  const root = stateRoot();
  const current = record(root);
  const currentOwner = owner(root);
  if (!current && !currentOwner) return { ok: true, stopped: false };
  if (!current || currentOwner?.nonce !== current.nonce || !await probe(current, root)) {
    throw new ViewerError('unverified_owner', 'The runtime owner could not be verified. No process was signalled.', 'Use ensure to recover a dead claim. Inspect a live unresponsive owner manually.');
  }
  await request(current, '/api/stop', {});
  const deadline = Date.now() + 2500;
  while (Date.now() < deadline) {
    if (!owns(root, current.nonce)) return { ok: true, stopped: true };
    await sleep(40);
  }
  throw new ViewerError('stop_timeout', 'The verified viewer did not finish shutting down.', 'Wait briefly and retry stop. No foreign process will be signalled.');
}

const html = `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>nstack viewer</title><link rel="stylesheet" href="/assets/style.css"><script type="module" src="/assets/browser.js"></script></head>
<body><a class="skip" href="#document">Skip to document</a><header class="topbar"><a href="/" class="brand">nstack <span>visual review</span></a><span id="connection" role="status">Connecting</span></header>
<div class="layout"><nav id="outline" aria-label="Document outline"></nav><main id="document" tabindex="-1"><p>Loading document...</p></main></div></body></html>`;
const securityHeaders = {
  'Content-Security-Policy': "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'; object-src 'none'",
  'X-Content-Type-Options': 'nosniff',
  'Referrer-Policy': 'no-referrer',
  'Cache-Control': 'no-store',
  'Cross-Origin-Resource-Policy': 'same-origin',
};
function send(res, status, value, type = 'application/json; charset=utf-8') {
  res.writeHead(status, { ...securityHeaders, 'Content-Type': type });
  res.end(type.startsWith('application/json') ? JSON.stringify(value) : value);
}
const httpError = (code, message, repair, status = 400) => Object.assign(new ViewerError(code, message, repair), { status });
function documentPath(root, id) { return join(root, 'documents', `${id}.json`); }
function readDocument(root, id) {
  const value = readJSON(documentPath(root, id));
  if (!value) throw httpError('document_not_found', `No published document "${id}".`, 'Run open with the source MDX path.', 404);
  return value;
}
function answersFor(root, id) {
  const { document } = readDocument(root, id);
  const answers = readJSON(join(root, 'answers', `${id}.json`)) ?? {};
  return {
    ok: true, docId: id, revision: document.revision,
    answers: Object.entries(answers).map(([blockId, answer]) => {
      const question = document.blocks.find((block) => block.type === 'component' && block.name === 'Question' && block.id === blockId);
      const stale = !question || answer.digest !== question.questionDigest;
      return { blockId, ...answer, stale, active: !stale, removed: !question };
    }),
  };
}
async function readBody(req) {
  if (!/^application\/json(?:\s*;\s*charset=utf-8)?$/i.test(req.headers['content-type'] ?? '')) throw httpError('content_type', 'Writes require application/json.', 'Send JSON with Content-Type: application/json.', 415);
  let size = 0;
  let oversized = Number(req.headers['content-length']) > MAX_BODY;
  const chunks = [];
  for await (const chunk of req) {
    size += chunk.length;
    if (size > MAX_BODY) oversized = true;
    if (!oversized) chunks.push(chunk);
  }
  if (oversized) throw httpError('body_too_large', 'The request body exceeds 2.1 MB.', 'Split the document into smaller documents.', 413);
  let value;
  try { value = JSON.parse(Buffer.concat(chunks).toString('utf8')); }
  catch (error) { if (error instanceof SyntaxError) throw httpError('invalid_json', error.message, 'Send a valid JSON object.'); throw error; }
  boundedJSON(value);
  if (!value || Array.isArray(value) || typeof value !== 'object') throw httpError('invalid_body', 'The request body must be a JSON object.', 'Send the documented request object.');
  return value;
}

export async function serve(buildId, nonce) {
  const root = stateRoot();
  if (!/^[a-f0-9]{48}$/.test(nonce ?? '') || !owns(root, nonce)) throw new ViewerError('lost_claim', 'The viewer no longer owns its startup claim.', 'Run ensure again.');
  const deadline = Date.now() + 1500;
  while (owns(root, nonce) && owner(root).pid !== process.pid && alive(owner(root).pid) && Date.now() < deadline) await sleep(15);
  if (!owns(root, nonce) || owner(root).pid !== process.pid) throw new ViewerError('lost_claim', 'The parent did not transfer the startup claim to this viewer.', 'Run ensure again. A child cannot take over a dead parent claim.');
  const token = random();
  let current;
  let lastActivity = Date.now();
  let closing = false;
  const assetRoot = join(dirname(fileURLToPath(import.meta.url)), 'assets');
  async function handle(req, res) {
    const origin = `http://127.0.0.1:${current.port}`;
    if (req.headers.host !== `127.0.0.1:${current.port}`) throw httpError('host_rejected', 'The Host header is not the literal viewer address.', 'Use the exact 127.0.0.1 URL returned by ensure.', 403);
    if (req.headers.origin && req.headers.origin !== origin) throw httpError('origin_rejected', 'Cross-origin access is not allowed.', 'Open the viewer directly at its returned URL.', 403);
    if (!req.url || req.url.length > 500) throw httpError('invalid_route', 'The request URL is invalid.', 'Use a known viewer route.', 404);
    const url = new URL(req.url, origin);
    const path = url.pathname;
    if (req.method === 'POST') {
      if (req.headers.origin !== origin) throw httpError('origin_required', 'Writes require the exact same Origin.', 'Send the viewer Origin header.', 403);
      if (req.headers['x-nstack-token'] !== token) throw httpError('token_rejected', 'The mutation token is missing or invalid.', 'Reload the viewer to obtain a fresh session.', 403);
    } else if (req.method !== 'GET') throw httpError('method_rejected', 'Only GET and guarded POST are supported.', 'Use the documented viewer operations.', 405);
    lastActivity = Date.now();
    if (req.method === 'GET' && path === '/health' && url.searchParams.get('nonce') === nonce) return send(res, 200, { protocol: PROTOCOL, nonce, buildId, pid: process.pid, rootHash: digest(root) });
    if (req.method === 'GET' && path === '/api/session') return send(res, 200, { ok: true, token, buildId });
    if (req.method === 'GET' && path === '/api/documents') {
      const documents = readdirSync(join(root, 'documents')).filter((file) => /^[a-zA-Z0-9][a-zA-Z0-9_-]{0,95}\.json$/.test(file)).map((file) => {
        const value = readJSON(join(root, 'documents', file));
        return { docId: value.document.docId, title: value.document.title, kind: value.document.kind, publishedAt: value.publishedAt };
      });
      return send(res, 200, { ok: true, documents });
    }
    if (req.method === 'GET' && (path === '/' || /^\/documents\/[a-zA-Z0-9][a-zA-Z0-9_-]{0,95}$/.test(path))) {
      if (path !== '/') readDocument(root, path.split('/')[2]);
      return send(res, 200, html, 'text/html; charset=utf-8');
    }
    if (req.method === 'GET' && ['/assets/browser.js', '/assets/style.css'].includes(path)) return send(res, 200, readFileSync(join(assetRoot, path.split('/')[2])), path.endsWith('.js') ? 'text/javascript; charset=utf-8' : 'text/css; charset=utf-8');
    const docMatch = /^\/api\/documents\/([a-zA-Z0-9][a-zA-Z0-9_-]{0,95})$/.exec(path);
    if (req.method === 'GET' && docMatch) {
      const value = readDocument(root, docMatch[1]);
      return send(res, 200, { ok: true, ...value.document, publishedAt: value.publishedAt, sourcePath: value.sourcePath, sourceSnapshot: true });
    }
    const answersMatch = /^\/api\/answers\/([a-zA-Z0-9][a-zA-Z0-9_-]{0,95})(?:\/([a-zA-Z0-9][a-zA-Z0-9_-]{0,95}))?$/.exec(path);
    if (req.method === 'GET' && answersMatch && !answersMatch[2]) return send(res, 200, answersFor(root, answersMatch[1]));
    if (req.method === 'POST' && path === '/api/publish') {
      const body = await readBody(req);
      if (Object.keys(body).some((key) => !['source', 'sourcePath'].includes(key)) || typeof body.source !== 'string' || typeof body.sourcePath !== 'string' || !isAbsolute(body.sourcePath) || body.sourcePath.length > 4096) throw httpError('invalid_publish', 'Publication requires source and an absolute sourcePath.', 'Use the open CLI command with an absolute MDX path.');
      const document = compile(body.source);
      const previous = readJSON(documentPath(root, document.docId));
      if (previous && previous.sourcePath !== body.sourcePath) throw httpError('source_conflict', `Document ID "${document.docId}" already belongs to ${previous.sourcePath}.`, 'Use a distinct Document ID for another source. To move a document, deliberately migrate its stored source identity.', 409);
      atomicJSON(documentPath(root, document.docId), { sourcePath: body.sourcePath, source: body.source, publishedAt: new Date().toISOString(), document });
      return send(res, 200, { ok: true, url: origin, docId: document.docId, revision: document.revision });
    }
    if (req.method === 'POST' && answersMatch?.[2]) {
      const body = await readBody(req);
      const { document } = readDocument(root, answersMatch[1]);
      const question = document.blocks.find((block) => block.type === 'component' && block.name === 'Question' && block.id === answersMatch[2]);
      if (!question) throw httpError('question_not_found', 'The question no longer exists in this published document.', 'Reload the document before answering.', 404);
      if (body.digest !== question.questionDigest) throw httpError('stale_question', 'The question changed after this page loaded.', 'Reload the page and answer the current question.', 409);
      if (Object.keys(body).some((key) => !['value', 'digest'].includes(key)) || typeof body.value !== 'string' || !body.value.trim() || body.value.length > 10000 || (question.data.options && !question.data.options.includes(body.value))) throw httpError('invalid_answer', 'The answer must be a nonempty string or one of the current options.', 'Choose a current option or enter up to 10000 characters.');
      const file = join(root, 'answers', `${document.docId}.json`);
      const answers = readJSON(file) ?? {};
      answers[question.id] = { value: body.value, digest: question.questionDigest, savedAt: new Date().toISOString() };
      atomicJSON(file, answers);
      return send(res, 200, answersFor(root, document.docId));
    }
    if (req.method === 'POST' && path === '/api/stop') {
      await readBody(req);
      send(res, 200, { ok: true });
      setImmediate(shutdown);
      return;
    }
    throw httpError('not_found', 'No such viewer route or document.', 'Use the exact document URL returned by open.', 404);
  }
  const server = createServer((req, res) => {
    handle(req, res).catch((error) => {
      const failure = error instanceof ViewerError ? error : new ViewerError('server_error', error.message, 'Inspect viewer state permissions and retry. Run ensure if the server stopped.');
      if (!res.headersSent && !res.destroyed) send(res, error.status ?? (error instanceof ViewerError ? 400 : 500), { ok: false, errors: [failure.toJSON()] });
      else res.destroy();
    });
  });
  server.requestTimeout = 5000;
  server.headersTimeout = 5000;
  server.keepAliveTimeout = 1000;
  server.maxHeadersCount = 32;
  function shutdown() {
    if (closing) return;
    closing = true;
    clearInterval(idle);
    server.close(() => { release(root, nonce); process.exit(0); });
    server.closeAllConnections();
    setTimeout(() => { release(root, nonce); process.exit(0); }, 1000).unref();
  }
  const idle = setInterval(() => { if (Date.now() - lastActivity > 12 * 60 * 60 * 1000) shutdown(); }, 60000);
  idle.unref();
  process.once('SIGTERM', shutdown);
  process.once('SIGINT', shutdown);
  try {
    await new Promise((resolve, reject) => { server.once('error', reject); server.listen(0, '127.0.0.1', resolve); });
    if (!owns(root, nonce)) throw new ViewerError('lost_claim', 'The startup claim changed before readiness.', 'Run ensure again.');
    current = { protocol: PROTOCOL, nonce, token, pid: process.pid, buildId, port: server.address().port, rootHash: digest(root) };
    atomicJSON(join(claimPath(root), 'ready.json'), current);
  } catch (error) {
    clearInterval(idle);
    server.close();
    if (owns(root, nonce)) atomicJSON(join(claimPath(root), 'failure.json'), { code: error.code ?? 'listen_failed', message: error.message, repair: 'Check loopback availability and state permissions, then retry ensure.' });
    throw error;
  }
}
