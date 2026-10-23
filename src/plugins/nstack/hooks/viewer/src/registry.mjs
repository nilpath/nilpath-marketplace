import { answerSchema } from './answer.mjs';

const string = { type: 'string', minLength: 1, maxLength: 100000 };
const boolean = { type: 'boolean' };
const array = (items, minItems = 1) => ({ type: 'array', items, minItems, maxItems: 200 });
const object = (properties, required = Object.keys(properties)) => ({ type: 'object', properties, required, additionalProperties: false });
const optional = (properties, required) => object(properties, required);
const code = object({ label: string, code: string, language: string });
const regions = array(optional({ label: string, kind: { enum: ['header', 'navigation', 'content', 'sidebar', 'footer', 'control'] }, content: string }, ['label']));
const parameter = object({ name: string, in: { enum: ['path', 'query', 'header', 'cookie', 'body', 'argument', 'message', 'option'] }, type: string, required: boolean, description: string });
const example = optional({ kind: { enum: ['request', 'response', 'error'] }, status: { type: 'integer', minimum: 100, maximum: 599 }, body: {} }, ['kind', 'body']);
const commonApi = { auth: string, parameters: array(parameter, 0), schema: { type: 'object' }, examples: array(example) };
export const apiSchema = { oneOf: [
  object({ protocol: { enum: ['http'] }, method: { enum: ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS'] }, path: string, ...commonApi }),
  object({ protocol: { enum: ['function', 'rpc', 'event', 'cli'] }, name: string, signature: string, ...commonApi }),
] };
const evidence = array(string);
const payload = (properties, required = Object.keys(properties)) => optional({ ...properties, evidence }, required);

export const components = {
  Diagram: payload({ layout: { enum: ['flow', 'sequence'] }, nodes: array(object({ id: string, label: string })), edges: array(optional({ from: string, to: string, label: string }, ['from', 'to']), 0) }, ['nodes', 'edges']),
  AnnotatedCode: payload({ language: string, code: string, annotations: array(object({ line: { type: 'integer', minimum: 1 }, text: string }), 0) }),
  FileMap: payload({ files: array(object({ path: string, change: { enum: ['added', 'modified', 'deleted', 'context'] }, note: string })) }),
  BeforeAfter: payload({ before: code, after: code }),
  Decision: payload({ options: array(object({ label: string, reason: string, selected: boolean })) }),
  Question: payload({ prompt: string, options: array(answerSchema, 2) }, ['prompt']),
  Wireframe: payload({ regions }),
  StateSequence: payload({ states: array(optional({ name: string, description: string, regions }, ['name', 'description'])) }),
  ApiContract: { oneOf: apiSchema.oneOf.map((schema) => ({ ...schema, properties: { ...schema.properties, evidence } })) },
  ApiComparison: payload({ before: apiSchema, after: apiSchema, changes: array(string) }),
};

export const componentReference = () => ({
  ok: true,
  version: 1,
  source: 'MDX with exactly one fenced json payload per rich block. No ESM, expressions, HTML, or executable JSX.',
  document: { attributes: { id: 'stable unique ID, 1-96 ASCII letters, digits, underscore or hyphen', kind: ['plan', 'recap'], title: 'nonempty string' }, children: 'Markdown and rich blocks' },
  attributes: { required: ['id', 'title', 'status'], optional: ['evidence', 'reason'], statuses: { plan: ['proposed', 'context'], recap: ['implemented', 'inferred', 'context', 'proposed'] }, rules: ['implemented requires nonempty evidence attribute or payload evidence array', 'inferred requires nonempty reason attribute', 'proposed in a recap is an explicitly unimplemented follow-up'] },
  components,
  example: 'all-components.mdx',
});
