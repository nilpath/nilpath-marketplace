import { createHash } from 'node:crypto';
import { Validator } from 'jsonschema';
import { components } from './registry.mjs';
export { components, apiSchema, componentReference } from './registry.mjs';

export class ViewerError extends Error {
  constructor(code, message, repair, extra = {}) {
    super(message);
    Object.assign(this, { code, repair, ...extra });
  }
  toJSON() {
    return { code: this.code, message: this.message, repair: this.repair, ...(this.line ? { line: this.line, column: this.column } : {}) };
  }
}

export const digest = (value) => createHash('sha256').update(value).digest('hex');
export const ID = /^[a-zA-Z0-9][a-zA-Z0-9_-]{0,95}$/;
const validator = new Validator();
export function boundedJSON(value, depth = 0) {
  if (depth > 18) throw new ViewerError('too_deep', 'JSON nesting exceeds 18 levels.', 'Flatten nested schemas or examples.');
  if (value && typeof value === 'object') {
    if (Object.keys(value).length > 1000) throw new ViewerError('too_large', 'A JSON object or array has too many entries.', 'Split it into smaller blocks.');
    for (const child of Object.values(value)) boundedJSON(child, depth + 1);
  }
}

export function validatePayload(name, value) {
  boundedJSON(value);
  const result = validator.validate(value, components[name]);
  if (!result.valid) throw new ViewerError('invalid_payload', `${name}: ${result.errors.map((error) => error.stack).join('; ')}`, `Use "components" for the ${name} JSON schema and examples.`);
  if (name === 'Diagram') {
    const ids = value.nodes.map((node) => node.id);
    if (new Set(ids).size !== ids.length || value.edges.some((edge) => !ids.includes(edge.from) || !ids.includes(edge.to))) {
      throw new ViewerError('invalid_graph', 'Diagram node IDs must be unique and every edge must name existing nodes.', 'Correct the nodes and edge endpoints.');
    }
  }
  if (name === 'AnnotatedCode' && value.annotations.some((note) => note.line > value.code.split('\n').length)) {
    throw new ViewerError('invalid_annotation', 'An annotation names a line outside the code block.', 'Use one-based line numbers within the code.');
  }
  if (name === 'Question' && value.options && new Set(value.options).size !== value.options.length) {
    throw new ViewerError('invalid_options', 'Question options must be distinct.', 'Give each option a unique label.');
  }
  return value;
}

export const questionDigest = (data) => digest(JSON.stringify([data.prompt, data.options ?? null]));
