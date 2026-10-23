import { readFile, realpath } from 'node:fs/promises';
import { isAbsolute } from 'node:path';
import { fileURLToPath } from 'node:url';
import { compile } from './compiler.mjs';
import { componentReference, ViewerError } from './model.mjs';
import { ensure, publish, getAnswers, stop, serve } from './runtime.mjs';

export { compile };
export const BUILD_ID = __BUILD_ID__;

async function main(args) {
  args = args.filter((arg) => arg !== '--json');
  const [command, target] = args;
  if (process.platform === 'win32') throw new ViewerError('unsupported_platform', 'The local viewer requires a POSIX platform with user-only state permissions.', 'Run the viewer in WSL, Linux, or macOS. Native Windows viewer support is not available.');
  if (Number(process.versions.node.split('.')[0]) < 20) throw new ViewerError('unsupported_node', 'The viewer requires Node 20 or newer.', 'Install Node >=20 and retry.');
  if (command === 'components' && args.length === 1) return componentReference();
  if (['open', 'check'].includes(command) && args.length === 2) {
    if (!isAbsolute(target)) throw new ViewerError('absolute_path_required', 'The source path must be absolute.', 'Pass the absolute path to an MDX document.');
    const sourcePath = await realpath(target);
    const source = await readFile(sourcePath, 'utf8');
    if (command === 'open') return publish(BUILD_ID, fileURLToPath(import.meta.url), sourcePath, source);
    const document = compile(source);
    return { ok: true, docId: document.docId, title: document.title, revision: document.revision, document };
  }
  if (command === 'ensure' && args.length === 1) return ensure(BUILD_ID, fileURLToPath(import.meta.url));
  if (command === 'answers' && args.length === 2) return getAnswers(target);
  if (command === 'stop' && args.length === 1) return stop();
  if (command === '_serve' && args.length === 2) { await serve(BUILD_ID, target); return null; }
  throw new ViewerError('usage', 'Unknown command or invalid arguments.', 'Use check/open /absolute/document.mdx, ensure, answers DOCUMENT_ID, components, or stop.');
}

if (process.argv[1] && await realpath(process.argv[1]) === await realpath(fileURLToPath(import.meta.url))) {
  try {
    const result = await main(process.argv.slice(2));
    if (result) process.stdout.write(`${JSON.stringify(result)}\n`);
  } catch (error) {
    const failure = error instanceof ViewerError ? error : new ViewerError(error.code ?? 'runtime_error', error.message, 'Check the source path and state directory permissions, then retry.');
    process.stdout.write(`${JSON.stringify({ ok: false, errors: [failure.toJSON()] })}\n`);
    process.exitCode = 1;
  }
}
