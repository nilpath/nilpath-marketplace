import { build } from 'esbuild';
import { createHash } from 'node:crypto';
import { readFile, writeFile, mkdir, readdir } from 'node:fs/promises';
import { dirname, join, relative, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const tool = dirname(fileURLToPath(import.meta.url));
const root = resolve(tool, '../..');
const viewer = join(root, 'src/plugins/nstack/hooks/viewer');
const outputRoot = process.env.NSTACK_VIEWER_OUTPUT_DIR ? resolve(process.env.NSTACK_VIEWER_OUTPUT_DIR) : viewer;
const check = process.argv.includes('--check');
const hash = (value) => createHash('sha256').update(value).digest('hex');
const inputs = {};
async function collect(path) {
  for (const entry of (await readdir(path, { withFileTypes: true })).sort((a, b) => a.name.localeCompare(b.name))) {
    const name = join(path, entry.name);
    if (entry.isDirectory()) await collect(name);
    else inputs[relative(root, name)] = hash(await readFile(name));
  }
}
await collect(join(viewer, 'src'));
inputs['src/plugins/nstack/hooks/viewer/all-components.mdx'] = hash(await readFile(join(viewer, 'all-components.mdx')));
for (const file of ['package.json', 'package-lock.json', 'build.mjs']) inputs[`tools/visual-viewer/${file}`] = hash(await readFile(join(tool, file)));
const buildId = hash(JSON.stringify(inputs)).slice(0, 24);
const outputs = new Map();
const bundledPackages = new Set(['node_modules/esbuild']);
for (const [entry, outfile, platform] of [['cli.mjs', 'viewer.mjs', 'node'], ['browser.mjs', 'assets/browser.js', 'browser']]) {
  const result = await build({
    absWorkingDir: root,
    entryPoints: [join(viewer, 'src', entry)],
    outfile: join(viewer, outfile),
    bundle: true,
    write: false,
    format: 'esm',
    platform,
    target: platform === 'node' ? 'node20' : 'es2022',
    nodePaths: [join(tool, 'node_modules')],
    define: { __BUILD_ID__: JSON.stringify(buildId) },
    legalComments: 'eof',
    charset: 'utf8',
    metafile: true,
  });
  for (const output of result.outputFiles) outputs.set(relative(viewer, output.path), output.contents);
  for (const input of Object.keys(result.metafile.inputs)) {
    const packageName = input.match(/node_modules\/((?:@[^/]+\/)?[^/]+)\//)?.[1];
    if (packageName) bundledPackages.add(`node_modules/${packageName}`);
  }
}
outputs.set('assets/style.css', await readFile(join(viewer, 'src/style.css')));
const { componentReference } = await import(pathToFileURL(join(viewer, 'src/registry.mjs')));
outputs.set('components.json', Buffer.from(`${JSON.stringify(componentReference(), null, 2)}\n`));
const lock = JSON.parse(await readFile(join(tool, 'package-lock.json'), 'utf8'));
const notices = ['# Third-party licenses', '', 'These dependencies are bundled into the nstack viewer. esbuild produces the bundles.', ''];
for (const [path, pkg] of Object.entries(lock.packages).sort(([a], [b]) => a.localeCompare(b))) {
  if (!bundledPackages.has(path)) continue;
  const location = join(tool, path);
  const files = await readdir(location);
  const licenses = files.filter((name) => /^(licen[sc]e|copying|notice)([.-]|$)/i.test(name)).sort();
  if (!licenses.length) throw new Error(`Missing license text for ${path}`);
  notices.push(`## ${path.replace('node_modules/', '')} ${pkg.version}`, '');
  for (const file of licenses) notices.push(await readFile(join(location, file), 'utf8'), '');
}
outputs.set('THIRD-PARTY-NOTICES', Buffer.from(`${notices.join('\n').trimEnd()}\n`));
const hashes = Object.fromEntries([...outputs].map(([name, value]) => [name, hash(value)]));
outputs.set('manifest.json', Buffer.from(`${JSON.stringify({ version: 1, buildId, inputs, outputs: hashes }, null, 2)}\n`));
for (const [file, value] of outputs) {
  const path = join(outputRoot, file);
  if (check) {
    let existing;
    try { existing = await readFile(path); } catch (error) { if (error.code !== 'ENOENT') throw error; }
    if (!existing || !Buffer.from(value).equals(existing)) throw new Error(`${file} is stale. Run npm --prefix tools/visual-viewer run build.`);
  } else {
    await mkdir(dirname(path), { recursive: true });
    await writeFile(path, value);
  }
}
console.log(`${check ? 'Verified' : 'Built'} viewer ${buildId}.`);
