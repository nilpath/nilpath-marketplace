import { fromMarkdown } from 'mdast-util-from-markdown';
import { mdxjs } from 'micromark-extension-mdxjs';
import { mdxFromMarkdown } from 'mdast-util-mdx';
import { components, validatePayload, digest, ID, ViewerError, questionDigest } from './model.mjs';

const allowedMarkdown = new Set(['heading', 'paragraph', 'list', 'listItem', 'blockquote', 'thematicBreak', 'break', 'text', 'emphasis', 'strong', 'inlineCode', 'code', 'link']);
const fail = (node, code, message, repair) => {
  throw new ViewerError(code, message, repair, { line: node.position?.start.line ?? 1, column: node.position?.start.column ?? 1 });
};

function attributes(node, allowed) {
  const attrs = {};
  for (const attr of node.attributes) {
    if (attr.type !== 'mdxJsxAttribute' || !allowed.includes(attr.name) || (attr.value !== null && typeof attr.value !== 'string') || Object.hasOwn(attrs, attr.name)) {
      fail(attr, 'unsafe_attribute', 'Only named, unique literal string attributes are allowed.', `Use ${allowed.join(', ')} with quoted string values. Do not use expressions or spreads.`);
    }
    attrs[attr.name] = attr.value === null ? true : attr.value;
  }
  return attrs;
}

function required(node, attrs, keys) {
  for (const key of keys) if (typeof attrs[key] !== 'string' || !attrs[key].trim()) fail(node, 'missing_attribute', `A nonempty ${key} string is required.`, `Add ${key}="..." to ${node.name}.`);
  if (!ID.test(attrs.id)) fail(node, 'invalid_id', 'IDs must be 1-96 ASCII letters, digits, underscores or hyphens, starting with a letter or digit.', 'Choose a stable, readable ID.');
}

function markdown(node) {
  if (!allowedMarkdown.has(node.type)) fail(node, 'unsafe_mdx', `Unsupported or executable MDX node "${node.type}".`, 'Use ordinary Markdown and the documented rich components. Remove imports, expressions, HTML, images, and inline JSX.');
  if (node.type === 'link' && !/^(https?:\/\/|#)/i.test(node.url)) fail(node, 'unsafe_link', 'Links must use http, https, or a local fragment.', 'Replace the URL with a safe link. Local files are not served.');
  const result = { type: node.type };
  for (const key of ['value', 'depth', 'ordered', 'start', 'lang', 'url', 'title']) if (node[key] !== undefined && node[key] !== null) result[key] = node[key];
  if (node.children) result.children = node.children.map(markdown);
  return result;
}

export function compile(source) {
  if (Buffer.byteLength(source) > 2_000_000) throw new ViewerError('source_too_large', 'The MDX source exceeds 2 MB.', 'Split the document into smaller documents.');
  let tree;
  try {
    tree = fromMarkdown(source, { extensions: [mdxjs()], mdastExtensions: [mdxFromMarkdown()] });
  } catch (error) {
    throw new ViewerError('mdx_syntax', error.message, 'Correct MDX syntax at the reported location. JSON payloads belong inside fenced json blocks.', { line: error.line ?? 1, column: error.column ?? 1 });
  }
  if (tree.children.length !== 1 || tree.children[0].type !== 'mdxJsxFlowElement' || tree.children[0].name !== 'Document') {
    fail(tree.children[0] ?? tree, 'document_required', 'The source must contain exactly one outer Document element.', 'Wrap the document in <Document id="..." kind="plan" title="..."> on its own lines.');
  }
  const root = tree.children[0];
  const attrs = attributes(root, ['id', 'kind', 'title']);
  required(root, attrs, ['id', 'kind', 'title']);
  if (!['plan', 'recap'].includes(attrs.kind)) fail(root, 'invalid_kind', 'Document kind must be plan or recap.', 'Set kind="plan" or kind="recap".');
  const ids = new Set([attrs.id]);
  const blocks = root.children.map((node) => {
    if (node.type !== 'mdxJsxFlowElement') return markdown(node);
    if (!Object.hasOwn(components, node.name)) fail(node, 'unknown_component', `Unknown component "${node.name}".`, 'Run "components" for the supported component names.');
    const props = attributes(node, ['id', 'title', 'status', 'evidence', 'reason']);
    required(node, props, ['id', 'title', 'status']);
    if (ids.has(props.id)) fail(node, 'duplicate_id', `Duplicate ID "${props.id}".`, 'Give every block a stable unique ID within the document.');
    ids.add(props.id);
    const statuses = attrs.kind === 'plan' ? ['proposed', 'context'] : ['implemented', 'inferred', 'context', 'proposed'];
    if (!statuses.includes(props.status)) fail(node, 'invalid_status', `"${props.status}" is not allowed in a ${attrs.kind}.`, `Use ${statuses.join(', ')}. Plans must not claim implementation.`);
    if (node.children.length !== 1 || node.children[0].type !== 'code' || node.children[0].lang !== 'json' || node.children[0].meta) {
      fail(node, 'payload_required', `${node.name} requires exactly one fenced json block.`, 'Move explanation outside the component and put only its JSON payload inside.');
    }
    let data;
    try {
      data = JSON.parse(node.children[0].value);
      validatePayload(node.name, data);
    } catch (error) {
      if (error instanceof SyntaxError) fail(node.children[0], 'invalid_json', error.message, 'Correct the fenced JSON payload. Use "components" for its schema.');
      if (error instanceof ViewerError) fail(node.children[0], error.code, error.message, error.repair);
      throw error;
    }
    if (props.status === 'implemented' && !(typeof props.evidence === 'string' && props.evidence.trim()) && !data.evidence?.some((item) => item.trim())) {
      fail(node, 'evidence_required', 'Implemented blocks require nonempty evidence.', 'Add evidence="test or source reference" or a payload evidence list.');
    }
    if (props.status === 'inferred' && !(typeof props.reason === 'string' && props.reason.trim())) fail(node, 'reason_required', 'Inferred blocks require a reason.', 'Add reason="why this is inferred rather than verified".');
    if (['evidence', 'reason'].some((key) => props[key] !== undefined && (typeof props[key] !== 'string' || !props[key].trim()))) fail(node, 'invalid_attribute', 'Evidence and reason must be nonempty strings.', 'Use a quoted, nonempty explanation.');
    return { type: 'component', name: node.name, ...props, data, ...(node.name === 'Question' ? { questionDigest: questionDigest(data) } : {}) };
  });
  return { version: 1, docId: attrs.id, title: attrs.title, kind: attrs.kind, revision: digest(source), blocks };
}
